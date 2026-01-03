"""
Роутер для отслеживания местоположения (WebSocket)
"""
from typing import Annotated
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
import json
import logging
from datetime import datetime, timedelta

from .. import crud, schemas, models
from ..auth import verify_token, get_current_user
from ..database import get_db
from ..websocket_manager import manager
from ..utils import validate_coordinates

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/track/driver")
async def websocket_track_driver_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint для водителей для отправки местоположения
    """
    # Верификация токена
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    user_id = payload.get("user_id")
    user_role = payload.get("role")
    
    if not user_id or user_role != models.UserRole.DRIVER.value:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Получение пользователя и профиля водителя
    user = crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    profile = crud.get_driver_profile(db, user_id)
    if not profile or profile.verification_status != models.VerificationStatus.VERIFIED:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Driver not verified")
        return
    
    # Подключение водителя к трекингу
    await manager.connect_driver_tracking(websocket, user_id)
    
    try:
        # Основной цикл получения местоположения
        while True:
            data = await websocket.receive_text()
            location_data = json.loads(data)
            
            # Проверка типа сообщения
            if location_data.get("type") != "location_update":
                continue
            
            lat = location_data.get("lat")
            lng = location_data.get("lng")
            
            # Валидация координат
            if not validate_coordinates(lat, lng):
                await websocket.send_json({
                    "type": "error",
                    "message": "Неверные координаты"
                })
                continue
            
            accuracy = location_data.get("accuracy")
            speed = location_data.get("speed")
            heading = location_data.get("heading")
            
            # Получение активного заказа водителя
            order = db.query(models.Order).filter(
                models.Order.driver_id == user_id,
                models.Order.status.in_([
                    models.OrderStatus.DRIVER_ASSIGNED,
                    models.OrderStatus.LOADING,
                    models.OrderStatus.EN_ROUTE,
                    models.OrderStatus.UNLOADING
                ])
            ).order_by(models.Order.updated_at.desc()).first()
            
            order_id = order.id if order else None
            
            # Сохранение местоположения в базу данных
            location_create = schemas.LocationCreate(
                lat=lat,
                lng=lng,
                order_id=order_id,
                accuracy=accuracy,
                speed=speed,
                heading=heading
            )
            
            location = crud.create_location_update(db, location_create, user_id)
            
            # Обновление текущего местоположения в профиле водителя
            profile.current_location_lat = lat
            profile.current_location_lng = lng
            profile.is_online = True
            db.commit()
            
            # Подготовка данных для трансляции
            broadcast_data = {
                "driver_id": user_id,
                "driver_name": user.full_name,
                "vehicle_number": profile.vehicle_number,
                "order_id": order_id,
                "order_number": order.order_number if order else None,
                "lat": lat,
                "lng": lng,
                "accuracy": accuracy,
                "speed": speed,
                "heading": heading,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Трансляция местоположения всем подписчикам
            await manager.broadcast_location(user_id, broadcast_data)
            
            # Подтверждение получения местоположения
            await websocket.send_json({
                "type": "location_received",
                "data": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "location_id": location.id
                }
            })
            
            logger.debug(f"Location update from driver {user.email}: ({lat}, {lng})")
            
    except WebSocketDisconnect:
        logger.info(f"Driver tracking WebSocket disconnected: driver {user.email}")
        manager.disconnect_driver_tracking(user_id)
        
    except Exception as e:
        logger.error(f"Driver tracking WebSocket error: {e}")
        manager.disconnect_driver_tracking(user_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

@router.websocket("/ws/track/subscribe/{driver_id}")
async def websocket_track_subscribe_endpoint(
    websocket: WebSocket,
    driver_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint для подписки на отслеживание водителя
    """
    # Верификация токена
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    user_id = payload.get("user_id")
    user_role = payload.get("role")
    
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Получение пользователя
    user = crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Проверка прав доступа
    if user.role == models.UserRole.ADMIN:
        # Администраторы могут отслеживать любого водителя
        await manager.connect_admin(websocket, user_id)
        
    elif user.role == models.UserRole.CLIENT:
        # Клиенты могут отслеживать только водителей своих активных заказов
        active_order = db.query(models.Order).filter(
            models.Order.client_id == user_id,
            models.Order.driver_id == driver_id,
            models.Order.status.in_([
                models.OrderStatus.DRIVER_ASSIGNED,
                models.OrderStatus.LOADING,
                models.OrderStatus.EN_ROUTE,
                models.OrderStatus.UNLOADING
            ])
        ).first()
        
        if not active_order:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not authorized")
            return
        
        await manager.connect_tracking_subscriber(websocket, driver_id, user_id)
        
    else:
        # Водители не могут отслеживать других водителей
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not authorized")
        return
    
    try:
        # Получение водителя
        driver = crud.get_user_by_id(db, driver_id)
        driver_profile = crud.get_driver_profile(db, driver_id)
        
        if not driver or not driver_profile:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Driver not found")
            return
        
        # Отправка информации о водителе
        await websocket.send_json({
            "type": "driver_info",
            "data": {
                "driver_id": driver_id,
                "driver_name": driver.full_name,
                "driver_email": driver.email,
                "vehicle_type": driver_profile.vehicle_type,
                "vehicle_model": driver_profile.vehicle_model,
                "vehicle_number": driver_profile.vehicle_number,
                "phone": driver.phone,
                "rating": driver_profile.rating,
                "is_online": driver_profile.is_online
            }
        })
        
        # Отправка последнего известного местоположения
        last_location = db.query(models.LocationUpdate).filter(
            models.LocationUpdate.driver_id == driver_id
        ).order_by(models.LocationUpdate.timestamp.desc()).first()
        
        if last_location:
            await websocket.send_json({
                "type": "location_update",
                "data": {
                    "driver_id": driver_id,
                    "lat": last_location.lat,
                    "lng": last_location.lng,
                    "accuracy": last_location.accuracy,
                    "speed": last_location.speed,
                    "heading": last_location.heading,
                    "order_id": last_location.order_id,
                    "timestamp": last_location.timestamp.isoformat()
                }
            })
        
        # Получение истории маршрута для активного заказа
        if user.role == models.UserRole.CLIENT:
            active_order = db.query(models.Order).filter(
                models.Order.client_id == user_id,
                models.Order.driver_id == driver_id,
                models.Order.status.in_([
                    models.OrderStatus.DRIVER_ASSIGNED,
                    models.OrderStatus.LOADING,
                    models.OrderStatus.EN_ROUTE,
                    models.OrderStatus.UNLOADING
                ])
            ).first()
            
            if active_order:
                route_history = crud.get_locations_by_driver(
                    db, driver_id, active_order.id, limit=100
                )
                
                if route_history:
                    await websocket.send_json({
                        "type": "route_history",
                        "data": {
                            "order_id": active_order.id,
                            "route": [
                                {
                                    "lat": loc.lat,
                                    "lng": loc.lng,
                                    "timestamp": loc.timestamp.isoformat()
                                }
                                for loc in reversed(route_history)  # От старых к новым
                            ]
                        }
                    })
        
        # Основной цикл (поддержание соединения)
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Обработка команд от клиента
            if message_data.get("type") == "request_history":
                hours = message_data.get("hours", 24)
                from_time = datetime.utcnow() - timedelta(hours=hours)
                
                locations = db.query(models.LocationUpdate).filter(
                    models.LocationUpdate.driver_id == driver_id,
                    models.LocationUpdate.timestamp >= from_time
                ).order_by(models.LocationUpdate.timestamp.asc()).all()
                
                await websocket.send_json({
                    "type": "location_history",
                    "data": {
                        "driver_id": driver_id,
                        "locations": [
                            {
                                "lat": loc.lat,
                                "lng": loc.lng,
                                "timestamp": loc.timestamp.isoformat(),
                                "order_id": loc.order_id
                            }
                            for loc in locations
                        ]
                    }
                })
            
    except WebSocketDisconnect:
        logger.info(f"Tracking subscriber WebSocket disconnected: user {user.email}")
        if user.role == models.UserRole.ADMIN:
            manager.disconnect_admin(websocket, user_id)
        else:
            manager.disconnect_tracking_subscriber(websocket, driver_id, user_id)
            
    except Exception as e:
        logger.error(f"Tracking subscriber WebSocket error: {e}")
        if user.role == models.UserRole.ADMIN:
            manager.disconnect_admin(websocket, user_id)
        else:
            manager.disconnect_tracking_subscriber(websocket, driver_id, user_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

@router.get("/track/driver/{driver_id}/locations")
async def get_driver_locations(
    driver_id: int,
    current_user: Annotated[schemas.UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=168, description="Количество часов истории"),
    limit: int = Query(100, ge=1, le=1000, description="Лимит записей")
):
    """
    Получение истории местоположения водителя (HTTP endpoint)
    """
    # Проверка прав доступа
    if current_user.role == models.UserRole.CLIENT:
        # Клиенты могут видеть только водителей своих активных заказов
        active_order = db.query(models.Order).filter(
            models.Order.client_id == current_user.id,
            models.Order.driver_id == driver_id,
            models.Order.status.in_([
                models.OrderStatus.DRIVER_ASSIGNED,
                models.OrderStatus.LOADING,
                models.OrderStatus.EN_ROUTE,
                models.OrderStatus.UNLOADING
            ])
        ).first()
        
        if not active_order:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен"
            )
    
    elif current_user.role == models.UserRole.DRIVER:
        # Водители могут видеть только свое местоположение
        if current_user.id != driver_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен"
            )
    
    # Для администраторов доступ разрешен всегда
    
    # Получение истории местоположения
    from_time = datetime.utcnow() - timedelta(hours=hours)
    
    locations = db.query(models.LocationUpdate).filter(
        models.LocationUpdate.driver_id == driver_id,
        models.LocationUpdate.timestamp >= from_time
    ).order_by(models.LocationUpdate.timestamp.desc()).limit(limit).all()
    
    return locations

@router.get("/track/order/{order_id}/route")
async def get_order_route(
    order_id: int,
    current_user: Annotated[schemas.UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Получение маршрута заказа
    """
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    
    # Проверка прав доступа
    is_authorized = (
        current_user.id == order.client_id or 
        current_user.id == order.driver_id or
        current_user.role == models.UserRole.ADMIN
    )
    
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен"
        )
    
    # Получение точек маршрута
    route_points = []
    
    # Начальная точка (откуда)
    route_points.append({
        "type": "pickup",
        "address": order.from_address,
        "lat": order.from_lat,
        "lng": order.from_lng,
        "timestamp": order.pickup_date.isoformat() if order.pickup_date else None
    })
    
    # Промежуточные точки (если есть трекинг)
    if order.driver_id:
        locations = crud.get_locations_by_driver(db, order.driver_id, order_id, limit=200)
        for loc in locations:
            route_points.append({
                "type": "tracking",
                "lat": loc.lat,
                "lng": loc.lng,
                "timestamp": loc.timestamp.isoformat(),
                "accuracy": loc.accuracy,
                "speed": loc.speed
            })
    
    # Конечная точка (куда)
    route_points.append({
        "type": "delivery",
        "address": order.to_address,
        "lat": order.to_lat,
        "lng": order.to_lng,
        "timestamp": order.delivery_date.isoformat() if order.delivery_date else None
    })
    
    # Расчет статистики
    total_distance = order.distance_km or 0
    estimated_time = None
    
    if len(route_points) > 2 and order.driver_id:
        # Расчет пройденного расстояния (упрощенно)
        driver_profile = crud.get_driver_profile(db, order.driver_id)
        if driver_profile:
            estimated_time = total_distance / 60  # Предполагаемая скорость 60 км/ч
    
    return {
        "order_id": order_id,
        "order_number": order.order_number,
        "status": order.status.value,
        "route_points": route_points,
        "statistics": {
            "total_distance_km": total_distance,
            "estimated_time_hours": estimated_time,
            "points_count": len(route_points)
        }
    }