"""
Роутер для административных функций
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime, timedelta

from .. import schemas, crud, models
from ..auth import get_current_admin
from ..database import get_db
from ..dependencies import PaginationParams
from ..notifications import notification_service

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

@router.get("/stats", response_model=schemas.AdminStats)
async def get_admin_stats(
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение статистики для админ-панели
    """
    stats = crud.get_system_stats(db)
    
    return schemas.AdminStats(
        total_users=stats["total_users"],
        total_drivers=stats["total_drivers"],
        total_clients=stats["total_clients"],
        total_orders=stats["total_orders"],
        total_revenue=stats["total_revenue"],
        pending_verifications=stats["pending_verifications"],
        active_orders=stats["active_orders"]
    )

@router.get("/stats/detailed")
async def get_detailed_stats(
    period: str = Query("7d", description="Период: 1d, 7d, 30d"),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение детальной статистики
    """
    # Определяем период
    if period == "1d":
        days = 1
    elif period == "30d":
        days = 30
    else:  # 7d по умолчанию
        days = 7
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Статистика пользователей
    new_users = db.query(models.User).filter(
        models.User.created_at >= start_date
    ).count()
    
    new_drivers = db.query(models.User).filter(
        models.User.role == models.UserRole.DRIVER,
        models.User.created_at >= start_date
    ).count()
    
    new_clients = db.query(models.User).filter(
        models.User.role == models.UserRole.CLIENT,
        models.User.created_at >= start_date
    ).count()
    
    # Статистика заказов
    new_orders = db.query(models.Order).filter(
        models.Order.created_at >= start_date
    ).count()
    
    completed_orders = db.query(models.Order).filter(
        models.Order.status == models.OrderStatus.COMPLETED,
        models.Order.updated_at >= start_date
    ).count()
    
    cancelled_orders = db.query(models.Order).filter(
        models.Order.status == models.OrderStatus.CANCELLED,
        models.Order.updated_at >= start_date
    ).count()
    
    # Финансовая статистика
    revenue = db.query(models.Order).filter(
        models.Order.status.in_([models.OrderStatus.COMPLETED, models.OrderStatus.PAID]),
        models.Order.updated_at >= start_date
    ).all()
    
    total_revenue = sum(order.platform_fee or 0 for order in revenue)
    total_order_amount = sum(order.final_price or 0 for order in revenue)
    
    # Статистика по дням
    daily_stats = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        next_day = day + timedelta(days=1)
        
        daily_orders = db.query(models.Order).filter(
            models.Order.created_at >= day,
            models.Order.created_at < next_day
        ).count()
        
        daily_revenue = db.query(models.Order).filter(
            models.Order.status.in_([models.OrderStatus.COMPLETED, models.OrderStatus.PAID]),
            models.Order.updated_at >= day,
            models.Order.updated_at < next_day
        ).all()
        
        daily_total_revenue = sum(order.platform_fee or 0 for order in daily_revenue)
        
        daily_stats.append({
            "date": day.strftime("%Y-%m-%d"),
            "orders": daily_orders,
            "revenue": daily_total_revenue
        })
    
    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": datetime.utcnow().isoformat(),
        "users": {
            "new_users": new_users,
            "new_drivers": new_drivers,
            "new_clients": new_clients,
            "total_users": stats["total_users"]
        },
        "orders": {
            "new_orders": new_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": cancelled_orders,
            "active_orders": stats["active_orders"],
            "total_orders": stats["total_orders"]
        },
        "financial": {
            "total_revenue": total_revenue,
            "total_order_amount": total_order_amount,
            "avg_order_value": total_order_amount / len(revenue) if revenue else 0,
            "platform_fee_percentage": 5.0  # 5% комиссия
        },
        "daily_stats": daily_stats
    }

@router.get("/verifications/pending")
async def get_pending_verifications(
    pagination: PaginationParams = Depends(),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение списка водителей, ожидающих верификации
    """
    profiles = crud.get_driver_profiles(
        db,
        skip=pagination.skip,
        limit=pagination.limit,
        verification_status=models.VerificationStatus.PENDING.value
    )
    
    result = []
    for profile in profiles:
        result.append({
            "user": schemas.UserResponse.model_validate(profile.user),
            "profile": schemas.DriverProfileResponse.model_validate(profile),
            "documents": {
                "license": bool(profile.license_path),
                "passport": bool(profile.passport_path),
                "vehicle_registration": bool(profile.vehicle_registration_path),
                "insurance": bool(profile.insurance_path)
            },
            "days_waiting": (datetime.utcnow() - profile.created_at).days
        })
    
    return result

@router.post("/verifications/{driver_id}")
async def verify_driver(
    driver_id: int,
    verification: schemas.VerificationRequest,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Верификация профиля водителя
    """
    profile = crud.get_driver_profile(db, driver_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль водителя не найден"
        )
    
    if profile.verification_status != models.VerificationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Профиль водителя уже верифицирован или отклонен"
        )
    
    # Обновление статуса верификации
    profile.verification_status = verification.status
    db.commit()
    db.refresh(profile)
    
    # Обновление статуса пользователя
    user = crud.get_user_by_id(db, driver_id)
    if user:
        user.is_verified = (verification.status == models.VerificationStatus.VERIFIED)
        db.commit()
    
    # Отправка уведомления водителю
    background_tasks.add_task(
        notify_driver_about_verification,
        db,
        driver_id,
        verification.status,
        verification.notes
    )
    
    logger.info(f"Driver {driver_id} verification updated to {verification.status} by admin {current_user.email}")
    
    return {
        "message": f"Статус верификации обновлен на {verification.status.value}",
        "driver_id": driver_id,
        "status": verification.status.value,
        "verified_by": current_user.email
    }

@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = Query(50, ge=1, le=200, description="Количество записей"),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение недавней активности в системе
    """
    activities = []
    
    # Недавние заказы
    recent_orders = db.query(models.Order)\
        .order_by(models.Order.created_at.desc())\
        .limit(limit // 3)\
        .all()
    
    for order in recent_orders:
        activities.append({
            "type": "order_created",
            "timestamp": order.created_at,
            "data": {
                "order_id": order.id,
                "order_number": order.order_number,
                "client_id": order.client_id,
                "client_email": order.client.email,
                "status": order.status.value,
                "price": order.desired_price
            }
        })
    
    # Недавние регистрации
    recent_users = db.query(models.User)\
        .order_by(models.User.created_at.desc())\
        .limit(limit // 3)\
        .all()
    
    for user in recent_users:
        activities.append({
            "type": "user_registered",
            "timestamp": user.created_at,
            "data": {
                "user_id": user.id,
                "email": user.email,
                "role": user.role.value,
                "phone": user.phone
            }
        })
    
    # Недавние платежи
    recent_payments = db.query(models.Payment)\
        .order_by(models.Payment.created_at.desc())\
        .limit(limit // 3)\
        .all()
    
    for payment in recent_payments:
        activities.append({
            "type": "payment_processed",
            "timestamp": payment.created_at,
            "data": {
                "payment_id": payment.id,
                "user_id": payment.user_id,
                "user_email": payment.user.email,
                "amount": payment.amount,
                "status": payment.status.value,
                "order_id": payment.order_id
            }
        })
    
    # Сортировка по времени
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Ограничение количества
    activities = activities[:limit]
    
    return activities

@router.get("/financial/transactions")
async def get_financial_transactions(
    start_date: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Статус платежа"),
    pagination: PaginationParams = Depends(),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение финансовых транзакций
    """
    query = db.query(models.Payment)
    
    # Фильтрация по дате
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(models.Payment.created_at >= start)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты начала"
            )
    
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(models.Payment.created_at < end)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты окончания"
            )
    
    # Фильтрация по статусу
    if status:
        query = query.filter(models.Payment.status == status)
    
    # Получение транзакций
    payments = query.order_by(models.Payment.created_at.desc())\
                   .offset(pagination.skip)\
                   .limit(pagination.limit)\
                   .all()
    
    # Расчет статистики
    total_amount = sum(p.amount for p in payments)
    completed_amount = sum(p.amount for p in payments if p.status == models.PaymentStatus.COMPLETED)
    pending_amount = sum(p.amount for p in payments if p.status == models.PaymentStatus.PENDING)
    
    return {
        "transactions": payments,
        "statistics": {
            "total_count": len(payments),
            "total_amount": total_amount,
            "completed_amount": completed_amount,
            "pending_amount": pending_amount,
            "completed_count": len([p for p in payments if p.status == models.PaymentStatus.COMPLETED]),
            "pending_count": len([p for p in payments if p.status == models.PaymentStatus.PENDING])
        }
    }

@router.get("/orders/analytics")
async def get_orders_analytics(
    period: str = Query("30d", description="Период: 7d, 30d, 90d"),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Аналитика по заказам
    """
    # Определяем период
    if period == "7d":
        days = 7
    elif period == "90d":
        days = 90
    else:  # 30d по умолчанию
        days = 30
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Получаем все заказы за период
    orders = db.query(models.Order).filter(
        models.Order.created_at >= start_date
    ).all()
    
    if not orders:
        return {
            "period": period,
            "total_orders": 0,
            "analytics": {}
        }
    
    # Аналитика по статусам
    status_counts = {}
    for status in models.OrderStatus:
        status_counts[status.value] = len([o for o in orders if o.status == status])
    
    # Аналитика по типам груза
    cargo_types = {}
    for order in orders:
        cargo_type = order.cargo_type
        if cargo_type not in cargo_types:
            cargo_types[cargo_type] = 0
        cargo_types[cargo_type] += 1
    
    # Аналитика по ценам
    prices = [o.final_price or o.desired_price for o in orders if o.final_price or o.desired_price]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0
    
    # Аналитика по расстояниям
    distances = [o.distance_km for o in orders if o.distance_km]
    avg_distance = sum(distances) / len(distances) if distances else 0
    
    # Топ клиентов
    client_orders = {}
    for order in orders:
        client_id = order.client_id
        if client_id not in client_orders:
            client_orders[client_id] = 0
        client_orders[client_id] += 1
    
    top_clients = sorted(client_orders.items(), key=lambda x: x[1], reverse=True)[:10]
    top_clients_details = []
    for client_id, order_count in top_clients:
        client = crud.get_user_by_id(db, client_id)
        if client:
            top_clients_details.append({
                "client_id": client_id,
                "email": client.email,
                "full_name": client.full_name,
                "order_count": order_count
            })
    
    # Топ водителей
    driver_orders = {}
    for order in orders:
        if order.driver_id:
            driver_id = order.driver_id
            if driver_id not in driver_orders:
                driver_orders[driver_id] = 0
            driver_orders[driver_id] += 1
    
    top_drivers = sorted(driver_orders.items(), key=lambda x: x[1], reverse=True)[:10]
    top_drivers_details = []
    for driver_id, order_count in top_drivers:
        driver = crud.get_user_by_id(db, driver_id)
        driver_profile = crud.get_driver_profile(db, driver_id)
        if driver:
            top_drivers_details.append({
                "driver_id": driver_id,
                "email": driver.email,
                "full_name": driver.full_name,
                "vehicle_number": driver_profile.vehicle_number if driver_profile else None,
                "order_count": order_count
            })
    
    return {
        "period": period,
        "total_orders": len(orders),
        "analytics": {
            "by_status": status_counts,
            "by_cargo_type": cargo_types,
            "price_statistics": {
                "average": round(avg_price, 2),
                "minimum": round(min_price, 2),
                "maximum": round(max_price, 2),
                "total_revenue": sum([o.platform_fee or 0 for o in orders])
            },
            "distance_statistics": {
                "average_km": round(avg_distance, 2),
                "total_km": sum(distances)
            },
            "top_clients": top_clients_details,
            "top_drivers": top_drivers_details
        }
    }

@router.post("/system/announcement")
async def create_system_announcement(
    announcement: dict,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Создание системного объявления
    """
    title = announcement.get("title", "")
    message = announcement.get("message", "")
    target = announcement.get("target", "all")  # all, clients, drivers
    
    if not title or not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заголовок и сообщение обязательны"
        )
    
    # Определяем целевых пользователей
    if target == "clients":
        users = crud.get_users(db, role=models.UserRole.CLIENT.value, is_active=True)
    elif target == "drivers":
        users = crud.get_users(db, role=models.UserRole.DRIVER.value, is_active=True)
    else:  # all
        users = crud.get_users(db, is_active=True)
    
    # Отправляем уведомления
    user_ids = [user.id for user in users]
    
    background_tasks.add_task(
        send_bulk_notifications,
        db,
        user_ids,
        "system_announcement",
        {"title": title, "message": message, "from_admin": current_user.email}
    )
    
    logger.info(f"System announcement created by {current_user.email}: {title}")
    
    return {
        "message": "Объявление отправлено",
        "recipients_count": len(user_ids),
        "target": target,
        "title": title
    }

@router.get("/system/logs")
async def get_system_logs(
    level: Optional[str] = Query(None, description="Уровень логирования: INFO, WARNING, ERROR"),
    search: Optional[str] = Query(None, description="Поиск по сообщению"),
    pagination: PaginationParams = Depends(),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение системных логов (симуляция - в реальном приложении нужно использовать ELK или подобное)
    """
    # В реальном приложении здесь должен быть запрос к системе логирования
    # Для примера возвращаем mock данные
    
    mock_logs = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "message": "Система запущена",
            "source": "system"
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "level": "INFO",
            "message": "Новый пользователь зарегистрирован",
            "source": "auth",
            "user_id": 1
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "level": "WARNING",
            "message": "Попытка входа с неверным паролем",
            "source": "auth",
            "user_email": "test@example.com"
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
            "level": "ERROR",
            "message": "Ошибка при обработке платежа",
            "source": "payment",
            "payment_id": 123
        }
    ]
    
    # Фильтрация
    if level:
        mock_logs = [log for log in mock_logs if log["level"] == level]
    
    if search:
        mock_logs = [log for log in mock_logs if search.lower() in log["message"].lower()]
    
    # Пагинация
    total = len(mock_logs)
    logs = mock_logs[pagination.skip:pagination.skip + pagination.limit]
    
    return {
        "logs": logs,
        "total": total,
        "page": pagination.skip // pagination.limit + 1,
        "pages": (total + pagination.limit - 1) // pagination.limit
    }

# Вспомогательные функции
async def notify_driver_about_verification(
    db: Session,
    driver_id: int,
    status: str,
    notes: Optional[str] = None
):
    """Уведомление водителя о результате верификации"""
    try:
        notification_type = "driver_verified" if status == models.VerificationStatus.VERIFIED else "driver_rejected"
        
        await notification_service.send_notification(
            db,
            driver_id,
            notification_type,
            {
                "status": status,
                "notes": notes,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error notifying driver about verification: {e}")

async def send_bulk_notifications(
    db: Session,
    user_ids: List[int],
    notification_type: str,
    data: dict
):
    """Массовая отправка уведомлений"""
    try:
        await notification_service.send_bulk_notifications(
            db,
            user_ids,
            notification_type,
            data
        )
        logger.info(f"Bulk notifications sent to {len(user_ids)} users: {notification_type}")
    except Exception as e:
        logger.error(f"Error sending bulk notifications: {e}")