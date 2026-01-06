"""
Дополнительные эндпоинты для админ-панели
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .. import schemas, crud, models
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin-dashboard"])
logger = logging.getLogger(__name__)

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение статистики для дашборда админ-панели
    """
    stats = crud.get_system_stats(db)
    
    return {
        "totalUsers": stats["total_users"],
        "totalOrders": stats["total_orders"],
        "totalDrivers": stats["total_drivers"],
        "pendingVerifications": stats["pending_verifications"],
        "activeOrders": stats["active_orders"],
        "totalRevenue": stats["total_revenue"],
        "newUsersWeek": stats["new_users_week"],
        "newOrdersWeek": stats["new_orders_week"],
        "revenueWeek": stats["revenue_week"]
    }

@router.get("/users")
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение списка всех пользователей
    """
    users = crud.get_users(db, skip=skip, limit=limit, role=role, is_active=is_active)
    return [schemas.UserResponse.model_validate(user) for user in users]

@router.get("/drivers")
async def get_all_drivers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    verification_status: Optional[str] = Query(None),
    is_online: Optional[bool] = Query(None),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение списка всех водителей
    """
    profiles = crud.get_driver_profiles(
        db,
        skip=skip,
        limit=limit,
        verification_status=verification_status,
        is_online=is_online
    )
    
    result = []
    for profile in profiles:
        result.append({
            "id": profile.user.id,
            "firstName": profile.user.full_name.split()[0] if profile.user.full_name else "",
            "lastName": " ".join(profile.user.full_name.split()[1:]) if profile.user.full_name else "",
            "email": profile.user.email,
            "phone": profile.user.phone,
            "vehicleType": profile.vehicle_type,
            "licensePlate": profile.vehicle_number,
            "verificationStatus": profile.verification_status.value,
            "rating": profile.rating,
            "totalOrders": profile.total_orders,
            "isOnline": profile.is_online,
            "createdAt": profile.user.created_at.isoformat()
        })
    
    return result

@router.get("/drivers/active")
async def get_active_drivers(
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение списка активных водителей
    """
    profiles = crud.get_driver_profiles(db, is_online=True, limit=50)
    
    result = []
    for profile in profiles:
        result.append({
            "id": profile.user.id,
            "firstName": profile.user.full_name.split()[0] if profile.user.full_name else "",
            "lastName": " ".join(profile.user.full_name.split()[1:]) if profile.user.full_name else "",
            "email": profile.user.email,
            "phone": profile.user.phone,
            "vehicleType": profile.vehicle_type,
            "vehicleModel": profile.vehicle_model,
            "licensePlate": profile.vehicle_number,
            "verificationStatus": profile.verification_status.value,
            "rating": profile.rating,
            "location": {
                "latitude": profile.current_location_lat,
                "longitude": profile.current_location_lng
            } if profile.current_location_lat and profile.current_location_lng else None,
            "lastUpdate": profile.updated_at.isoformat() if profile.updated_at else profile.created_at.isoformat()
        })
    
    return result

@router.get("/drivers/{driver_id}")
async def get_driver_by_id(
    driver_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение детальной информации о водителе
    """
    user = crud.get_user_by_id(db, driver_id)
    if not user or user.role != models.UserRole.DRIVER:
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
    
    # Получаем заказы водителя
    orders = crud.get_orders(db, driver_id=driver_id, limit=10)
    
    return {
        "id": user.id,
        "firstName": user.full_name.split()[0] if user.full_name else "",
        "lastName": " ".join(user.full_name.split()[1:]) if user.full_name else "",
        "email": user.email,
        "phone": user.phone,
        "dateOfBirth": None,  # В будущем можно добавить
        "vehicleType": profile.vehicle_type,
        "vehicleModel": profile.vehicle_model,
        "vehicleColor": None,  # В будущем можно добавить
        "licensePlate": profile.vehicle_number,
        "verificationStatus": profile.verification_status.value,
        "rating": profile.rating,
        "totalOrders": profile.total_orders,
        "completedOrders": len([o for o in orders if o.status == models.OrderStatus.COMPLETED]),
        "cancelledOrders": len([o for o in orders if o.status == models.OrderStatus.CANCELLED]),
        "isOnline": profile.is_online,
        "documents": [
            {"type": "license", "url": f"/uploads/{profile.license_path}", "uploadedAt": profile.created_at.isoformat()} if profile.license_path else None,
            {"type": "passport", "url": f"/uploads/{profile.passport_path}", "uploadedAt": profile.created_at.isoformat()} if profile.passport_path else None,
            {"type": "registration", "url": f"/uploads/{profile.vehicle_registration_path}", "uploadedAt": profile.created_at.isoformat()} if profile.vehicle_registration_path else None,
        ],
        "createdAt": user.created_at.isoformat()
    }

@router.patch("/drivers/{driver_id}/verify")
async def verify_driver(
    driver_id: int,
    status: str,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Верификация водителя
    """
    if status not in ["verified", "rejected", "pending"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный статус"
        )
    
    profile = crud.get_driver_profile(db, driver_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль водителя не найден"
        )
    
    profile.verification_status = models.VerificationStatus(status)
    
    # Обновляем статус пользователя
    user = crud.get_user_by_id(db, driver_id)
    if user:
        user.is_verified = (status == "verified")
    
    db.commit()
    
    return {"message": f"Статус водителя обновлен на {status}", "driverId": driver_id}

@router.get("/orders")
async def get_all_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение списка всех заказов
    """
    orders = crud.get_orders(db, skip=skip, limit=limit, status=status)
    
    result = []
    for order in orders:
        result.append({
            "id": order.id,
            "orderNumber": order.order_number,
            "customer": {
                "id": order.client.id,
                "name": order.client.full_name,
                "email": order.client.email,
                "phone": order.client.phone
            } if order.client else None,
            "driver": {
                "id": order.driver.id,
                "name": order.driver.full_name,
                "phone": order.driver.phone,
                "vehicleType": order.driver.driver_profile.vehicle_type if order.driver.driver_profile else None
            } if order.driver else None,
            "pickupAddress": order.from_address,
            "deliveryAddress": order.to_address,
            "pickupInstructions": None,  # В будущем можно добавить
            "deliveryInstructions": None,  # В будущем можно добавить
            "packageType": order.cargo_type,
            "weight": order.cargo_weight,
            "dimensions": {
                "length": order.cargo_volume ** (1/3),
                "width": order.cargo_volume ** (1/3),
                "height": order.cargo_volume ** (1/3)
            },
            "totalAmount": order.final_price or order.desired_price,
            "status": order.status.value,
            "createdAt": order.created_at.isoformat(),
            "timeline": [
                {
                    "status": "created",
                    "timestamp": order.created_at.isoformat()
                }
            ] + ([
                {
                    "status": "pickup_scheduled",
                    "timestamp": order.pickup_date.isoformat()
                }
            ] if order.pickup_date else []) + ([
                {
                    "status": "delivered",
                    "timestamp": order.completed_at.isoformat()
                }
            ] if order.completed_at else [])
        })
    
    return result

@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    status: str,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Обновление статуса заказа
    """
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Проверяем валидность статуса
    valid_statuses = [s.value for s in models.OrderStatus]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный статус. Допустимые значения: {', '.join(valid_statuses)}"
        )
    
    order.status = models.OrderStatus(status)
    
    # Если заказ завершен, устанавливаем дату завершения
    if status == models.OrderStatus.COMPLETED.value and not order.completed_at:
        order.completed_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": f"Статус заказа обновлен на {status}", "orderId": order_id}

@router.patch("/users/{user_id}/toggle-block")
async def toggle_user_block(
    user_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Блокировка/разблокировка пользователя
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя заблокировать самого себя"
        )
    
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    user.is_active = not user.is_active
    db.commit()
    
    status_text = "разблокирован" if user.is_active else "заблокирован"
    return {"message": f"Пользователь {status_text}", "userId": user_id, "isActive": user.is_active}