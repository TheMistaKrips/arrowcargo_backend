"""
Роутер для чата (WebSocket)
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
import json
import logging
from datetime import datetime

from .. import crud, schemas, models
from ..auth import verify_token, get_current_user
from ..database import get_db
from ..websocket_manager import manager
from ..notifications import notification_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/chat/{order_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    order_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint для чата заказа
    """
    # Верификация токена
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    user_id = payload.get("user_id")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Получение пользователя и заказа
    user = crud.get_user_by_id(db, user_id)
    order = crud.get_order(db, order_id)
    
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    if not order:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Order not found")
        return
    
    # Проверка прав доступа к чату
    is_authorized = (
        user.id == order.client_id or 
        user.id == order.driver_id or
        user.role == models.UserRole.ADMIN
    )
    
    if not is_authorized:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not authorized")
        return
    
    # Подключение к чату
    await manager.connect_chat(websocket, order_id, user_id)
    
    try:
        # Отправляем историю сообщений
        messages = crud.get_messages_by_order(db, order_id, limit=50)
        for message in reversed(messages):  # От старых к новым
            await websocket.send_json({
                "type": "chat_history",
                "data": {
                    "id": message.id,
                    "order_id": message.order_id,
                    "sender_id": message.sender_id,
                    "sender_email": message.sender.email,
                    "sender_name": message.sender.full_name,
                    "sender_role": message.sender.role.value,
                    "content": message.content,
                    "is_read": message.is_read,
                    "timestamp": message.timestamp.isoformat()
                }
            })
        
        # Отправляем уведомление о подключении
        await manager.broadcast_chat_message(order_id, {
            "type": "user_connected",
            "data": {
                "user_id": user_id,
                "user_email": user.email,
                "user_name": user.full_name,
                "user_role": user.role.value,
                "timestamp": datetime.utcnow().isoformat()
            }
        }, exclude_user_id=user_id)
        
        # Основной цикл обработки сообщений
        while True:
            # Получение сообщения от клиента
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Проверка типа сообщения
            if message_data.get("type") != "chat_message":
                continue
            
            content = message_data.get("content", "").strip()
            if not content:
                continue
            
            # Сохранение сообщения в базу данных
            message_create = schemas.MessageCreate(content=content)
            message = crud.create_message(db, message_create, order_id, user_id)
            
            # Подготовка сообщения для трансляции
            broadcast_message = {
                "type": "chat_message",
                "data": {
                    "id": message.id,
                    "order_id": message.order_id,
                    "sender_id": message.sender_id,
                    "sender_email": user.email,
                    "sender_name": user.full_name,
                    "sender_role": user.role.value,
                    "content": message.content,
                    "is_read": message.is_read,
                    "timestamp": message.timestamp.isoformat()
                }
            }
            
            # Трансляция сообщения всем участникам чата
            await manager.broadcast_chat_message(order_id, broadcast_message)
            
            # Отправка уведомления другим участникам чата
            other_user_id = order.client_id if user_id != order.client_id else (order.driver_id or 0)
            if other_user_id:
                try:
                    await notification_service.send_notification(
                        db,
                        other_user_id,
                        "chat_message",
                        {
                            "order_id": order_id,
                            "order_number": order.order_number,
                            "sender_id": user_id,
                            "sender_name": user.full_name,
                            "message": content[:100] + ("..." if len(content) > 100 else "")
                        }
                    )
                except Exception as e:
                    logger.error(f"Error sending chat notification: {e}")
            
            logger.info(f"Chat message sent: order {order_id}, user {user.email}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: order {order_id}, user {user.email}")
        manager.disconnect_chat(websocket, order_id, user_id)
        
        # Отправляем уведомление об отключении
        try:
            await manager.broadcast_chat_message(order_id, {
                "type": "user_disconnected",
                "data": {
                    "user_id": user_id,
                    "user_email": user.email,
                    "user_name": user.full_name,
                    "user_role": user.role.value,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }, exclude_user_id=user_id)
        except:
            pass
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect_chat(websocket, order_id, user_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

@router.get("/chat/{order_id}/messages", response_model=list[schemas.MessageResponse])
async def get_chat_messages(
    order_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение истории сообщений чата (HTTP endpoint)
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
            detail="Доступ к чату запрещен"
        )
    
    # Получение сообщений
    messages = crud.get_messages_by_order(db, order_id, skip, limit)
    
    # Помечаем сообщения как прочитанные
    if messages:
        crud.mark_messages_as_read(db, order_id, current_user.id)
    
    return messages

@router.post("/chat/{order_id}/mark-read")
async def mark_chat_as_read(
    order_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Пометка всех сообщений чата как прочитанных
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
            detail="Доступ к чату запрещен"
        )
    
    # Помечаем сообщения как прочитанные
    updated_count = crud.mark_messages_as_read(db, order_id, current_user.id)
    
    return {"message": f"Отмечено {updated_count} сообщений как прочитанные"}

@router.get("/chat/unread-count")
async def get_unread_chat_count(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение количества непрочитанных сообщений
    """
    # Получаем все заказы пользователя
    if current_user.role == models.UserRole.CLIENT:
        orders = crud.get_orders(db, client_id=current_user.id)
    elif current_user.role == models.UserRole.DRIVER:
        orders = crud.get_orders(db, driver_id=current_user.id)
    else:  # Admin
        orders = []
    
    total_unread = 0
    orders_with_unread = []
    
    for order in orders:
        unread_count = db.query(models.Message).filter(
            models.Message.order_id == order.id,
            models.Message.sender_id != current_user.id,
            models.Message.is_read == False
        ).count()
        
        if unread_count > 0:
            total_unread += unread_count
            orders_with_unread.append({
                "order_id": order.id,
                "order_number": order.order_number,
                "unread_count": unread_count,
                "last_message": db.query(models.Message)
                    .filter(models.Message.order_id == order.id)
                    .order_by(models.Message.timestamp.desc())
                    .first()
            })
    
    return {
        "total_unread": total_unread,
        "orders_with_unread": orders_with_unread,
        "user_id": current_user.id
    }

@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint для получения уведомлений в реальном времени
    """
    # Верификация токена
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    user_id = payload.get("user_id")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Получение пользователя
    user = crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Подключение пользователя
    await manager.connect_user(websocket, user_id)
    
    try:
        # Отправляем непрочитанные уведомления
        notifications = db.query(models.Notification).filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        ).order_by(models.Notification.created_at.desc()).limit(20).all()
        
        for notification in notifications:
            await websocket.send_json({
                "type": "notification",
                "data": {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "type": notification.type,
                    "data": notification.data,
                    "is_read": notification.is_read,
                    "created_at": notification.created_at.isoformat()
                }
            })
        
        # Основной цикл (поддержание соединения)
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Обработка команд от клиента
            if message_data.get("type") == "mark_as_read":
                notification_id = message_data.get("notification_id")
                if notification_id:
                    notification = db.query(models.Notification).filter(
                        models.Notification.id == notification_id,
                        models.Notification.user_id == user_id
                    ).first()
                    
                    if notification:
                        notification.is_read = True
                        db.commit()
                        
                        await websocket.send_json({
                            "type": "notification_marked_read",
                            "data": {"notification_id": notification_id}
                        })
            
            elif message_data.get("type") == "mark_all_as_read":
                db.query(models.Notification).filter(
                    models.Notification.user_id == user_id,
                    models.Notification.is_read == False
                ).update({"is_read": True})
                db.commit()
                
                await websocket.send_json({
                    "type": "all_notifications_marked_read",
                    "data": {"user_id": user_id}
                })
            
    except WebSocketDisconnect:
        logger.info(f"Notification WebSocket disconnected: user {user.email}")
        manager.disconnect_user(websocket, user_id)
        
    except Exception as e:
        logger.error(f"Notification WebSocket error: {e}")
        manager.disconnect_user(websocket, user_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass