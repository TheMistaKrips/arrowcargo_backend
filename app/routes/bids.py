"""
Роутер для работы со ставками
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_driver, get_current_client_or_admin
from ..database import get_db
from ..dependencies import PaginationParams
from ..notifications import notification_service

router = APIRouter(prefix="/api/bids", tags=["bids"])
logger = logging.getLogger(__name__)

@router.post("/order/{order_id}", response_model=schemas.BidResponse)
async def create_bid(
    order_id: int,
    bid: schemas.BidCreate,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Создание ставки на заказ
    """
    # Проверка верификации водителя
    profile = crud.get_driver_profile(db, current_user.id)
    if not profile or profile.verification_status != models.VerificationStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Профиль водителя не верифицирован"
        )
    
    # Проверка заказа
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Проверка статуса заказа
    if order.status != models.OrderStatus.SEARCHING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заказ не доступен для ставок"
        )
    
    # Проверка, не делает ли водитель ставку на свой же заказ
    if order.client_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя делать ставку на свой собственный заказ"
        )
    
    # Проверка, не делал ли уже водитель ставку на этот заказ
    existing_bid = db.query(models.Bid).filter(
        models.Bid.order_id == order_id,
        models.Bid.driver_id == current_user.id
    ).first()
    
    if existing_bid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже сделали ставку на этот заказ"
        )
    
    # Проверка, подходит ли водитель по параметрам груза
    if (order.cargo_weight > profile.carrying_capacity or 
        order.cargo_volume > profile.volume):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ваш транспорт не подходит для этого груза. "
                  f"Требуется: до {order.cargo_weight}т, {order.cargo_volume}м³. "
                  f"Ваши возможности: {profile.carrying_capacity}т, {profile.volume}м³"
        )
    
    try:
        # Создаем ставку
        created_bid = crud.create_bid(db, bid, order_id, current_user.id)
        
        # Уведомляем клиента о новой ставке
        background_tasks.add_task(
            notify_client_about_new_bid,
            db,
            order_id,
            created_bid.id
        )
        
        logger.info(f"Bid created: ID {created_bid.id} for order {order_id} by driver {current_user.email}")
        
        return created_bid
        
    except ValueError as e:
        logger.error(f"Error creating bid: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating bid: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании ставки: {str(e)}"
        )

@router.get("/order/{order_id}", response_model=List[schemas.BidResponse])
async def get_order_bids(
    order_id: int,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение списка ставок для заказа
    """
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Проверка прав доступа
    has_access = False
    
    if current_user.role == models.UserRole.ADMIN:
        has_access = True
    elif current_user.role == models.UserRole.CLIENT and order.client_id == current_user.id:
        has_access = True
    elif current_user.role == models.UserRole.DRIVER and order.driver_id == current_user.id:
        has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к ставкам запрещен"
        )
    
    # Получаем ставки
    bids = crud.get_bids_by_order(db, order_id)
    
    # Если это водитель, показываем только его ставки
    if current_user.role == models.UserRole.DRIVER and order.client_id != current_user.id:
        bids = [bid for bid in bids if bid.driver_id == current_user.id]
    
    return bids

@router.get("/my", response_model=List[schemas.BidResponse])
async def get_my_bids(
    pagination: PaginationParams = Depends(),
    status: str = Query(None, description="Фильтр по статусу"),
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Получение списка ставок текущего водителя
    """
    query = db.query(models.Bid).filter(
        models.Bid.driver_id == current_user.id
    )
    
    if status:
        query = query.filter(models.Bid.status == status)
    
    bids = query.order_by(models.Bid.created_at.desc())\
               .offset(pagination.skip)\
               .limit(pagination.limit)\
               .all()
    
    return bids

@router.get("/{bid_id}", response_model=schemas.BidResponse)
async def get_bid(
    bid_id: int,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение информации о ставке
    """
    bid = crud.get_bid(db, bid_id)
    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ставка не найдена"
        )
    
    # Проверка прав доступа
    has_access = False
    
    if current_user.role == models.UserRole.ADMIN:
        has_access = True
    elif current_user.role == models.UserRole.CLIENT and bid.order.client_id == current_user.id:
        has_access = True
    elif current_user.role == models.UserRole.DRIVER and bid.driver_id == current_user.id:
        has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к ставке запрещен"
        )
    
    return bid

@router.post("/{bid_id}/accept", response_model=schemas.BidResponse)
async def accept_bid(
    bid_id: int,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_client_or_admin),
    db: Session = Depends(get_db)
):
    """
    Принятие ставки (для клиента или администратора)
    """
    bid = crud.get_bid(db, bid_id)
    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ставка не найдена"
        )
    
    order = crud.get_order(db, bid.order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Проверка прав доступа
    if current_user.role == models.UserRole.CLIENT and order.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец заказа может принимать ставки"
        )
    
    if bid.status != models.BidStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно принять эту ставку"
        )
    
    if order.status != models.OrderStatus.SEARCHING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заказ не доступен для принятия ставок"
        )
    
    try:
        # Принимаем ставку
        accepted_bid = crud.accept_bid(db, bid_id)
        
        if not accepted_bid:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при принятии ставки"
            )
        
        # Уведомляем водителя о принятии ставки
        background_tasks.add_task(
            notification_service.notify_bid_accepted,
            db,
            bid_id
        )
        
        logger.info(f"Bid accepted: ID {bid_id} for order {order.id}")
        
        return accepted_bid
        
    except Exception as e:
        logger.error(f"Error accepting bid: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при принятии ставки: {str(e)}"
        )

@router.post("/{bid_id}/reject")
async def reject_bid(
    bid_id: int,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_client_or_admin),
    db: Session = Depends(get_db)
):
    """
    Отклонение ставки (для клиента или администратора)
    """
    bid = crud.get_bid(db, bid_id)
    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ставка не найдена"
        )
    
    order = crud.get_order(db, bid.order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Проверка прав доступа
    if current_user.role == models.UserRole.CLIENT and order.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только владелец заказа может отклонять ставки"
        )
    
    if bid.status != models.BidStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно отклонить эту ставку"
        )
    
    # Отклоняем ставку
    rejected_bid = crud.reject_bid(db, bid_id)
    
    # Уведомляем водителя об отклонении ставки
    background_tasks.add_task(
        notify_driver_about_bid_rejection,
        db,
        bid_id
    )
    
    logger.info(f"Bid rejected: ID {bid_id} by user {current_user.email}")
    
    return {"message": "Ставка отклонена", "bid": rejected_bid}

@router.post("/{bid_id}/cancel")
async def cancel_bid(
    bid_id: int,
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Отмена ставки (для водителя)
    """
    bid = crud.get_bid(db, bid_id)
    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ставка не найдена"
        )
    
    if bid.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только автор ставки может ее отменить"
        )
    
    if bid.status != models.BidStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно отменить эту ставку"
        )
    
    # Отменяем ставку
    bid.status = models.BidStatus.CANCELLED
    db.commit()
    db.refresh(bid)
    
    logger.info(f"Bid cancelled: ID {bid_id} by driver {current_user.email}")
    
    return {"message": "Ставка отменена", "bid": bid}

@router.get("/stats/my")
async def get_my_bids_stats(
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Получение статистики по ставкам текущего водителя
    """
    bids = crud.get_bids_by_driver(db, current_user.id)
    
    total_bids = len(bids)
    accepted_bids = len([b for b in bids if b.status == models.BidStatus.ACCEPTED])
    pending_bids = len([b for b in bids if b.status == models.BidStatus.PENDING])
    rejected_bids = len([b for b in bids if b.status == models.BidStatus.REJECTED])
    
    # Рассчитываем успешность ставок
    success_rate = (accepted_bids / total_bids * 100) if total_bids > 0 else 0
    
    # Средняя предложенная цена
    accepted_prices = [b.proposed_price for b in bids if b.status == models.BidStatus.ACCEPTED]
    avg_accepted_price = sum(accepted_prices) / len(accepted_prices) if accepted_prices else 0
    
    stats = {
        "total_bids": total_bids,
        "accepted_bids": accepted_bids,
        "pending_bids": pending_bids,
        "rejected_bids": rejected_bids,
        "success_rate": round(success_rate, 2),
        "avg_accepted_price": round(avg_accepted_price, 2),
        "total_earnings": sum(accepted_prices) if accepted_prices else 0
    }
    
    return stats

@router.get("/order/{order_id}/best")
async def get_best_bids(
    order_id: int,
    limit: int = Query(5, ge=1, le=20, description="Количество лучших ставок"),
    current_user: schemas.UserResponse = Depends(get_current_client_or_admin),
    db: Session = Depends(get_db)
):
    """
    Получение лучших ставок для заказа (по цене и рейтингу водителя)
    """
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Проверка прав доступа
    if current_user.role == models.UserRole.CLIENT and order.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к ставкам запрещен"
        )
    
    # Получаем все ставки для заказа
    bids = crud.get_bids_by_order(db, order_id)
    
    if not bids:
        return {"bids": [], "count": 0}
    
    # Фильтруем только pending ставки
    pending_bids = [b for b in bids if b.status == models.BidStatus.PENDING]
    
    if not pending_bids:
        return {"bids": [], "count": 0}
    
    # Получаем информацию о водителях
    best_bids = []
    for bid in pending_bids:
        driver_profile = crud.get_driver_profile(db, bid.driver_id)
        if driver_profile:
            # Рассчитываем скоринг ставки (ниже цена + выше рейтинг = лучше)
            price_score = 1 / bid.proposed_price  # Чем ниже цена, тем выше скоринг
            rating_score = driver_profile.rating / 5.0  # Нормализованный рейтинг
            
            # Комбинированный скоринг (70% цена, 30% рейтинг)
            total_score = price_score * 0.7 + rating_score * 0.3
            
            best_bids.append({
                "bid": schemas.BidResponse.model_validate(bid),
                "driver_rating": driver_profile.rating,
                "driver_total_orders": driver_profile.total_orders,
                "driver_verification_status": driver_profile.verification_status.value,
                "score": total_score
            })
    
    # Сортируем по скорингу
    best_bids.sort(key=lambda x: x["score"], reverse=True)
    
    # Ограничиваем количество
    best_bids = best_bids[:limit]
    
    return {
        "bids": best_bids,
        "count": len(best_bids),
        "order_price": order.desired_price,
        "cheapest_bid": min([b["bid"].proposed_price for b in best_bids]) if best_bids else None,
        "avg_bid": sum([b["bid"].proposed_price for b in best_bids]) / len(best_bids) if best_bids else None
    }

# Вспомогательные функции
async def notify_client_about_new_bid(db: Session, order_id: int, bid_id: int):
    """Уведомление клиента о новой ставке"""
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return
        
        bid = crud.get_bid(db, bid_id)
        if not bid:
            return
        
        await notification_service.send_notification(
            db,
            order.client_id,
            "new_bid_received",
            {
                "order_id": order_id,
                "order_number": order.order_number,
                "bid_id": bid_id,
                "driver_id": bid.driver_id,
                "proposed_price": bid.proposed_price,
                "driver_name": bid.driver.full_name if bid.driver else None
            }
        )
    except Exception as e:
        logger.error(f"Error notifying client about new bid: {e}")

async def notify_driver_about_bid_rejection(db: Session, bid_id: int):
    """Уведомление водителя об отклонении ставки"""
    try:
        bid = crud.get_bid(db, bid_id)
        if not bid or not bid.driver_id:
            return
        
        await notification_service.send_notification(
            db,
            bid.driver_id,
            "bid_rejected",
            {
                "bid_id": bid_id,
                "order_id": bid.order_id,
                "proposed_price": bid.proposed_price
            }
        )
    except Exception as e:
        logger.error(f"Error notifying driver about bid rejection: {e}")