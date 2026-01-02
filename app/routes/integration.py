"""
Роутер для интеграции с внешними сервисами
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_admin
from ..database import get_db
from ..dependencies import verify_api_key
from ..payment import payment_service

router = APIRouter(prefix="/api/integration", tags=["integration"])
logger = logging.getLogger(__name__)

# Публичные эндпоинты для интеграции
@router.get("/public/order/{order_number}/status")
async def get_order_status_public(
    order_number: str,
    db: Session = Depends(get_db)
):
    """
    Публичный эндпоинт для получения статуса заказа по номеру
    (для интеграции с внешними системами)
    """
    order = crud.get_order_by_number(db, order_number)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Возвращаем ограниченную информацию для публичного доступа
    return {
        "order_number": order.order_number,
        "status": order.status.value,
        "from_address": order.from_address,
        "to_address": order.to_address,
        "cargo_type": order.cargo_type,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "estimated_delivery": order.delivery_date.isoformat() if order.delivery_date else None
    }

@router.get("/mobile/driver/{driver_id}/dashboard")
async def get_mobile_driver_dashboard(
    driver_id: int,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Дашборд для мобильного приложения водителя
    """
    if api_key != "mobile_app_key":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key for this endpoint"
        )
    
    driver = crud.get_user_by_id(db, driver_id)
    if not driver or driver.role != models.UserRole.DRIVER:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Водитель не найден"
        )
    
    profile = crud.get_driver_profile(db, driver_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль водителя не найден"
        )
    
    # Активные заказы
    active_orders = crud.get_orders(
        db,
        driver_id=driver_id,
        status=models.OrderStatus.DRIVER_ASSIGNED.value
    )
    
    # Доступные заказы
    available_orders = crud.get_available_orders(db, driver_id=driver_id, limit=20)
    
    # Статистика
    stats = {
        "total_orders": profile.total_orders,
        "total_distance": profile.total_distance,
        "rating": profile.rating,
        "balance": driver.balance,
        "is_online": profile.is_online,
        "verification_status": profile.verification_status.value
    }
    
    # Уведомления
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == driver_id,
        models.Notification.is_read == False
    ).order_by(models.Notification.created_at.desc()).limit(10).all()
    
    return {
        "driver": {
            "id": driver.id,
            "name": driver.full_name,
            "email": driver.email,
            "phone": driver.phone,
            "vehicle": {
                "type": profile.vehicle_type,
                "model": profile.vehicle_model,
                "number": profile.vehicle_number,
                "capacity": profile.carrying_capacity,
                "volume": profile.volume
            }
        },
        "stats": stats,
        "active_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "from_address": order.from_address,
                "to_address": order.to_address,
                "status": order.status.value,
                "price": order.final_price or order.desired_price,
                "pickup_date": order.pickup_date.isoformat() if order.pickup_date else None
            }
            for order in active_orders
        ],
        "available_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "from_address": order.from_address,
                "to_address": order.to_address,
                "distance": order.distance_km,
                "price": order.desired_price,
                "cargo": {
                    "type": order.cargo_type,
                    "weight": order.cargo_weight,
                    "volume": order.cargo_volume,
                    "description": order.cargo_description
                },
                "created_at": order.created_at.isoformat()
            }
            for order in available_orders
        ],
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "created_at": n.created_at.isoformat()
            }
            for n in notifications
        ]
    }

@router.get("/admin/dashboard")
async def get_admin_dashboard(
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Дашборд для админ-панели
    """
    if api_key != "admin_panel_key":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key for this endpoint"
        )
    
    stats = crud.get_system_stats(db)
    
    # Последние заказы
    recent_orders = db.query(models.Order)\
        .order_by(models.Order.created_at.desc())\
        .limit(10)\
        .all()
    
    # Последние регистрации
    recent_users = db.query(models.User)\
        .order_by(models.User.created_at.desc())\
        .limit(10)\
        .all()
    
    # Ожидающие верификации
    pending_verifications = db.query(models.DriverProfile)\
        .filter(models.DriverProfile.verification_status == models.VerificationStatus.PENDING)\
        .order_by(models.DriverProfile.created_at.desc())\
        .limit(10)\
        .all()
    
    return {
        "stats": stats,
        "recent_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "client_email": order.client.email,
                "status": order.status.value,
                "price": order.final_price or order.desired_price,
                "created_at": order.created_at.isoformat()
            }
            for order in recent_orders
        ],
        "recent_users": [
            {
                "id": user.id,
                "email": user.email,
                "role": user.role.value,
                "created_at": user.created_at.isoformat()
            }
            for user in recent_users
        ],
        "pending_verifications": [
            {
                "driver_id": profile.user_id,
                "driver_email": profile.user.email,
                "vehicle_number": profile.vehicle_number,
                "created_at": profile.created_at.isoformat(),
                "documents": {
                    "license": bool(profile.license_path),
                    "passport": bool(profile.passport_path),
                    "registration": bool(profile.vehicle_registration_path)
                }
            }
            for profile in pending_verifications
        ]
    }

@router.get("/website/order-tracking/{order_number}")
async def get_website_order_tracking(
    order_number: str,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Отслеживание заказа для основного сайта
    """
    if api_key != "website_key":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key for this endpoint"
        )
    
    order = crud.get_order_by_number(db, order_number)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Информация о заказе
    order_info = {
        "order_number": order.order_number,
        "status": order.status.value,
        "status_description": get_status_description(order.status),
        "from_address": order.from_address,
        "to_address": order.to_address,
        "cargo_type": order.cargo_type,
        "cargo_weight": order.cargo_weight,
        "cargo_volume": order.cargo_volume,
        "created_at": order.created_at.isoformat(),
        "pickup_date": order.pickup_date.isoformat() if order.pickup_date else None,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "distance": order.distance_km
    }
    
    # Информация о водителе (если назначен)
    driver_info = None
    if order.driver_id:
        driver = crud.get_user_by_id(db, order.driver_id)
        driver_profile = crud.get_driver_profile(db, order.driver_id)
        
        if driver and driver_profile:
            driver_info = {
                "name": driver.full_name,
                "phone": driver.phone,
                "vehicle": {
                    "type": driver_profile.vehicle_type,
                    "model": driver_profile.vehicle_model,
                    "number": driver_profile.vehicle_number
                },
                "rating": driver_profile.rating,
                "total_orders": driver_profile.total_orders
            }
    
    # Текущее местоположение водителя (если есть)
    current_location = None
    if order.driver_id:
        location = db.query(models.LocationUpdate)\
            .filter(models.LocationUpdate.driver_id == order.driver_id)\
            .order_by(models.LocationUpdate.timestamp.desc())\
            .first()
        
        if location:
            current_location = {
                "lat": location.lat,
                "lng": location.lng,
                "timestamp": location.timestamp.isoformat(),
                "accuracy": location.accuracy
            }
    
    # История статусов
    status_history = [
        {
            "status": "created",
            "timestamp": order.created_at.isoformat(),
            "description": "Заказ создан"
        }
    ]
    
    if order.pickup_date:
        status_history.append({
            "status": "pickup_scheduled",
            "timestamp": order.pickup_date.isoformat(),
            "description": "Запланирована погрузка"
        })
    
    if order.delivery_date:
        status_history.append({
            "status": "delivery_scheduled",
            "timestamp": order.delivery_date.isoformat(),
            "description": "Запланирована доставка"
        })
    
    if order.completed_at:
        status_history.append({
            "status": "completed",
            "timestamp": order.completed_at.isoformat(),
            "description": "Заказ завершен"
        })
    
    return {
        "order": order_info,
        "driver": driver_info,
        "current_location": current_location,
        "status_history": status_history,
        "estimated_progress": calculate_order_progress(order)
    }

@router.post("/payment/webhook")
async def payment_webhook(
    webhook_data: dict,
    x_webhook_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Вебхук для обработки платежей от внешних платежных систем
    """
    # В реальном приложении здесь должна быть проверка подписи
    logger.info(f"Payment webhook received: {webhook_data}")
    
    try:
        # Извлекаем данные из вебхука
        payment_id = webhook_data.get("payment_id")
        status = webhook_data.get("status")
        metadata = webhook_data.get("metadata", {})
        
        if not payment_id or not status:
            return {"status": "error", "message": "Missing required fields"}
        
        # Обработка вебхука
        success, message = await payment_service.process_payment_webhook(
            db, payment_id, status, metadata
        )
        
        if success:
            return {"status": "success", "message": message}
        else:
            return {"status": "error", "message": message}
            
    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/payment/methods")
async def get_payment_methods_integration(
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Получение доступных методов оплаты для интеграции
    """
    methods = payment_service.get_supported_payment_methods()
    
    return {
        "methods": methods,
        "currency": "RUB",
        "platform_fee_percent": 5.0
    }

# Вспомогательные функции
def get_status_description(status: models.OrderStatus) -> str:
    """Получение описания статуса заказа"""
    descriptions = {
        models.OrderStatus.DRAFT: "Черновик",
        models.OrderStatus.SEARCHING: "Поиск водителя",
        models.OrderStatus.DRIVER_ASSIGNED: "Водитель назначен",
        models.OrderStatus.LOADING: "Погрузка",
        models.OrderStatus.EN_ROUTE: "В пути",
        models.OrderStatus.UNLOADING: "Разгрузка",
        models.OrderStatus.COMPLETED: "Завершен",
        models.OrderStatus.CANCELLED: "Отменен",
        models.OrderStatus.PAID: "Оплачен"
    }
    return descriptions.get(status, "Неизвестный статус")

def calculate_order_progress(order: models.Order) -> float:
    """Расчет прогресса выполнения заказа"""
    progress_map = {
        models.OrderStatus.DRAFT: 0,
        models.OrderStatus.SEARCHING: 10,
        models.OrderStatus.DRIVER_ASSIGNED: 30,
        models.OrderStatus.LOADING: 50,
        models.OrderStatus.EN_ROUTE: 75,
        models.OrderStatus.UNLOADING: 90,
        models.OrderStatus.COMPLETED: 100,
        models.OrderStatus.CANCELLED: 0,
        models.OrderStatus.PAID: 100
    }
    return progress_map.get(order.status, 0)