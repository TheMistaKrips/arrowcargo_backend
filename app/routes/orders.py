"""
Роутер для работы с заказами
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_client, get_current_admin, get_current_client_or_admin, get_current_driver
from ..database import get_db
from ..dependencies import PaginationParams, OrderFilterParams
from ..file_storage import file_storage
from ..notifications import notification_service
from ..payment import payment_service

router = APIRouter(prefix="/api/orders", tags=["orders"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=schemas.OrderResponse)
async def create_order(
    order: schemas.OrderCreate,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Создание нового заказа
    """
    try:
        created_order = crud.create_order(db, order, current_user.id)
        
        # Уведомление администраторов о новом заказе
        background_tasks.add_task(
            notify_admins_about_new_order,
            db,
            created_order.id
        )
        
        logger.info(f"Order created: {created_order.order_number} by user: {current_user.email}")
        
        return created_order
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании заказа: {str(e)}"
        )

@router.get("/", response_model=List[schemas.OrderResponse])
async def get_my_orders(
    pagination: PaginationParams = Depends(),
    filters: OrderFilterParams = Depends(),
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение списка заказов текущего пользователя
    """
    if current_user.role == models.UserRole.CLIENT:
        orders = crud.get_orders(
            db,
            skip=pagination.skip,
            limit=pagination.limit,
            client_id=current_user.id,
            status=filters.status,
            min_price=filters.min_price,
            max_price=filters.max_price,
            cargo_type=filters.cargo_type
        )
    elif current_user.role == models.UserRole.DRIVER:
        orders = crud.get_orders(
            db,
            skip=pagination.skip,
            limit=pagination.limit,
            driver_id=current_user.id,
            status=filters.status,
            min_price=filters.min_price,
            max_price=filters.max_price,
            cargo_type=filters.cargo_type
        )
    else:  # Admin
        orders = crud.get_orders(
            db,
            skip=pagination.skip,
            limit=pagination.limit,
            status=filters.status,
            min_price=filters.min_price,
            max_price=filters.max_price,
            cargo_type=filters.cargo_type
        )
    
    return orders

@router.get("/available", response_model=List[schemas.OrderResponse])
async def get_available_orders(
    pagination: PaginationParams = Depends(),
    filters: OrderFilterParams = Depends(),
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение списка доступных заказов (для водителей)
    """
    if current_user.role != models.UserRole.DRIVER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только водители могут просматривать доступные заказы"
        )
    
    # Проверка верификации водителя
    profile = crud.get_driver_profile(db, current_user.id)
    if not profile or profile.verification_status != models.VerificationStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Профиль водителя не верифицирован"
        )
    
    orders = crud.get_available_orders(
        db,
        driver_id=current_user.id,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    # Применяем дополнительные фильтры
    if filters.status:
        orders = [o for o in orders if o.status == filters.status]
    if filters.min_price:
        orders = [o for o in orders if o.desired_price >= filters.min_price]
    if filters.max_price:
        orders = [o for o in orders if o.desired_price <= filters.max_price]
    if filters.cargo_type:
        orders = [o for o in orders if o.cargo_type == filters.cargo_type]
    
    return orders

@router.get("/{order_id}", response_model=schemas.OrderWithRelations)
async def get_order(
    order_id: int,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение информации о заказе
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
    elif current_user.role == models.UserRole.DRIVER:
        # Проверяем, делал ли водитель ставку на этот заказ
        bid = db.query(models.Bid).filter(
            models.Bid.order_id == order_id,
            models.Bid.driver_id == current_user.id
        ).first()
        has_access = bool(bid)
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к заказу запрещен"
        )
    
    return order

@router.put("/{order_id}", response_model=schemas.OrderResponse)
async def update_order(
    order_id: int,
    order_update: schemas.OrderUpdate,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Обновление заказа
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
            detail="Доступ к заказу запрещен"
        )
    
    # Только администратор может назначать водителя или устанавливать финальную цену
    if current_user.role != models.UserRole.ADMIN:
        if "driver_id" in order_update.model_dump(exclude_unset=True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только администратор может назначать водителя"
            )
        if "final_price" in order_update.model_dump(exclude_unset=True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только администратор может устанавливать финальную цену"
            )
    
    updated_order = crud.update_order(db, order_id, order_update)
    
    # Если изменился статус, отправляем уведомления
    if order_update.status and order_update.status != order.status:
        background_tasks.add_task(
            notify_order_status_change,
            db,
            order_id,
            order.status,
            order_update.status
        )
    
    logger.info(f"Order updated: {updated_order.order_number}")
    
    return updated_order

@router.post("/{order_id}/publish")
async def publish_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Публикация заказа (перевод в статус поиска водителя)
    """
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    if order.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к заказу запрещен"
        )
    
    if order.status != models.OrderStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заказ уже опубликован"
        )
    
    # Публикуем заказ
    order.status = models.OrderStatus.SEARCHING
    db.commit()
    db.refresh(order)
    
    # Уведомляем водителей о новом заказе
    background_tasks.add_task(
        notification_service.notify_new_order,
        db,
        order_id
    )
    
    logger.info(f"Order published: {order.order_number}")
    
    return {"message": "Заказ опубликован", "order": order}

@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Отмена заказа
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
            detail="Доступ к заказу запрещен"
        )
    
    if current_user.role == models.UserRole.DRIVER and order.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к заказу запрещен"
        )
    
    if order.status in [models.OrderStatus.COMPLETED, models.OrderStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно отменить завершенный или уже отмененный заказ"
        )
    
    # Отменяем заказ
    cancelled_order = crud.cancel_order(db, order_id)
    
    # Отправляем уведомления
    background_tasks.add_task(
        notify_order_cancelled,
        db,
        order_id,
        current_user.id
    )
    
    logger.info(f"Order cancelled: {order.order_number} by user: {current_user.email}")
    
    return {"message": "Заказ отменен", "order": cancelled_order}

@router.post("/{order_id}/complete")
async def complete_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Завершение заказа (для водителей)
    """
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    if order.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к заказу запрещен"
        )
    
    if order.status not in [models.OrderStatus.EN_ROUTE, models.OrderStatus.UNLOADING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно завершить заказ в текущем статусе"
        )
    
    # Завершаем заказ
    completed_order = crud.complete_order(db, order_id)
    
    # Отправляем уведомления
    background_tasks.add_task(
        notification_service.notify_order_completed,
        db,
        order_id
    )
    
    logger.info(f"Order completed: {order.order_number} by driver: {current_user.email}")
    
    return {"message": "Заказ завершен", "order": completed_order}

@router.post("/{order_id}/upload-image")
async def upload_order_image(
    order_id: int,
    file: UploadFile = File(...),
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Загрузка изображения для заказа
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
            detail="Доступ к заказу запрещен"
        )
    
    if current_user.role == models.UserRole.DRIVER and order.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к заказу запрещен"
        )
    
    try:
        # Сохраняем файл
        file_path = await file_storage.save_order_image(file, current_user.id, order_id)
        
        # Обновляем информацию о заказе
        if not order.cargo_images:
            order.cargo_images = []
        
        order.cargo_images.append(file_path)
        db.commit()
        
        logger.info(f"Image uploaded for order: {order.order_number}")
        
        return {
            "message": "Изображение успешно загружено",
            "file_path": file_path,
            "order_id": order_id
        }
        
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке изображения: {str(e)}"
        )

@router.post("/calculate-price")
async def calculate_order_price(
    request: schemas.PriceCalculationRequest,
    current_user: schemas.UserResponse = Depends(get_current_active_user)
):
    """
    Расчет стоимости перевозки
    """
    try:
        # Расчет расстояния
        distance_km = crud.utils.calculate_distance(
            request.from_lat, request.from_lng,
            request.to_lat, request.to_lng
        )
        
        # Расчет цены
        final_price, platform_fee, driver_amount = crud.utils.calculate_price(
            distance_km, request.weight, request.volume
        )
        
        # Базовые расчеты для информации
        base_price = distance_km * 15.0
        weight_multiplier = request.weight * 10.0
        volume_multiplier = request.volume * 5.0
        
        # Предлагаемая цена (желаемая цена клиента)
        suggested_price = final_price * 1.1  # +10% для торга
        
        result = schemas.PriceCalculation(
            distance_km=round(distance_km, 2),
            base_price=round(base_price, 2),
            weight_multiplier=round(weight_multiplier, 2),
            volume_multiplier=round(volume_multiplier, 2),
            suggested_price=round(suggested_price, 2),
            platform_fee=round(platform_fee, 2),
            driver_amount=round(driver_amount, 2)
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating price: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при расчете стоимости: {str(e)}"
        )

@router.get("/{order_number}/track")
async def track_order_by_number(
    order_number: str,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Отслеживание заказа по номеру (публичный доступ)
    """
    order = crud.get_order_by_number(db, order_number)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Для публичного отслеживания возвращаем ограниченную информацию
    response = {
        "order_number": order.order_number,
        "status": order.status.value,
        "from_address": order.from_address,
        "to_address": order.to_address,
        "cargo_type": order.cargo_type,
        "created_at": order.created_at,
        "updated_at": order.updated_at
    }
    
    # Если пользователь авторизован и имеет доступ, добавляем больше информации
    if current_user:
        has_access = False
        if current_user.role == models.UserRole.ADMIN:
            has_access = True
        elif current_user.role == models.UserRole.CLIENT and order.client_id == current_user.id:
            has_access = True
        elif current_user.role == models.UserRole.DRIVER and order.driver_id == current_user.id:
            has_access = True
        
        if has_access:
            response.update({
                "driver_id": order.driver_id,
                "client_id": order.client_id,
                "final_price": order.final_price,
                "distance_km": order.distance_km,
                "pickup_date": order.pickup_date,
                "delivery_date": order.delivery_date
            })
    
    return response

# Вспомогательные функции
async def notify_admins_about_new_order(db: Session, order_id: int):
    """Уведомление администраторов о новом заказе"""
    try:
        admins = crud.get_users(db, role="admin", is_active=True)
        for admin in admins:
            await notification_service.send_notification(
                db,
                admin.id,
                "new_order_created",
                {"order_id": order_id}
            )
    except Exception as e:
        logger.error(f"Error notifying admins about new order: {e}")

async def notify_order_status_change(
    db: Session,
    order_id: int,
    old_status: str,
    new_status: str
):
    """Уведомление об изменении статуса заказа"""
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return
        
        # Уведомляем клиента
        await notification_service.send_notification(
            db,
            order.client_id,
            "order_updated",
            {
                "order_id": order_id,
                "order_number": order.order_number,
                "old_status": old_status,
                "new_status": new_status
            }
        )
        
        # Уведомляем водителя, если он назначен
        if order.driver_id:
            await notification_service.send_notification(
                db,
                order.driver_id,
                "order_updated",
                {
                    "order_id": order_id,
                    "order_number": order.order_number,
                    "old_status": old_status,
                    "new_status": new_status
                }
            )
    except Exception as e:
        logger.error(f"Error notifying about order status change: {e}")

async def notify_order_cancelled(
    db: Session,
    order_id: int,
    cancelled_by_user_id: int
):
    """Уведомление об отмене заказа"""
    try:
        order = crud.get_order(db, order_id)
        if not order:
            return
        
        # Уведомляем всех участников
        participants = [order.client_id]
        if order.driver_id:
            participants.append(order.driver_id)
        
        for user_id in participants:
            if user_id != cancelled_by_user_id:  # Не уведомляем того, кто отменил
                await notification_service.send_notification(
                    db,
                    user_id,
                    "order_cancelled",
                    {
                        "order_id": order_id,
                        "order_number": order.order_number,
                        "cancelled_by": cancelled_by_user_id
                    }
                )
    except Exception as e:
        logger.error(f"Error notifying about order cancellation: {e}")