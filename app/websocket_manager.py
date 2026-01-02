"""
Менеджер WebSocket соединений
"""
from typing import Dict, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Для чата: order_id -> список WebSocket соединений
        self.chat_connections: Dict[int, List[WebSocket]] = defaultdict(list)
        
        # Для трекинга: driver_id -> список WebSocket соединений подписчиков
        self.tracking_connections: Dict[int, List[WebSocket]] = defaultdict(list)
        
        # Для водителей, отправляющих свою геопозицию
        self.driver_tracking_sockets: Dict[int, WebSocket] = {}
        
        # Для администраторов
        self.admin_connections: List[WebSocket] = []
        
        # Словарь user_id -> список активных соединений
        self.user_connections: Dict[int, List[WebSocket]] = defaultdict(list)
        
        # Ограничение соединений на пользователя
        self.max_connections_per_user = 5

    # Общие методы
    async def connect_user(self, websocket: WebSocket, user_id: int):
        """Подключение пользователя"""
        await websocket.accept()
        
        # Проверка лимита соединений
        if len(self.user_connections[user_id]) >= self.max_connections_per_user:
            # Закрываем самое старое соединение
            old_ws = self.user_connections[user_id].pop(0)
            try:
                await old_ws.close(code=1000)
            except:
                pass
        
        self.user_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected. Total connections: {len(self.user_connections[user_id])}")

    def disconnect_user(self, websocket: WebSocket, user_id: int):
        """Отключение пользователя"""
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
                logger.info(f"User {user_id} disconnected. Remaining connections: {len(self.user_connections[user_id])}")
            
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def send_to_user(self, user_id: int, message: dict):
        """Отправка сообщения конкретному пользователю"""
        if user_id in self.user_connections:
            disconnected = []
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to user {user_id}: {e}")
                    disconnected.append(connection)
            
            for connection in disconnected:
                self.disconnect_user(connection, user_id)

    # Методы для чата
    async def connect_chat(self, websocket: WebSocket, order_id: int, user_id: int):
        """Подключение к чату заказа"""
        await self.connect_user(websocket, user_id)
        
        if order_id not in self.chat_connections:
            self.chat_connections[order_id] = []
        
        self.chat_connections[order_id].append(websocket)
        logger.info(f"User {user_id} connected to chat for order {order_id}")

    def disconnect_chat(self, websocket: WebSocket, order_id: int, user_id: int):
        """Отключение от чата"""
        self.disconnect_user(websocket, user_id)
        
        if order_id in self.chat_connections:
            if websocket in self.chat_connections[order_id]:
                self.chat_connections[order_id].remove(websocket)
            
            if not self.chat_connections[order_id]:
                del self.chat_connections[order_id]

    async def broadcast_chat_message(self, order_id: int, message: dict, exclude_user_id: Optional[int] = None):
        """Трансляция сообщения в чат"""
        if order_id in self.chat_connections:
            disconnected = []
            for connection in self.chat_connections[order_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting chat message: {e}")
                    disconnected.append(connection)
            
            for connection in disconnected:
                # Находим user_id для этого соединения
                for uid, connections in self.user_connections.items():
                    if connection in connections:
                        self.disconnect_chat(connection, order_id, uid)
                        break

    # Методы для трекинга (водители)
    async def connect_driver_tracking(self, websocket: WebSocket, driver_id: int):
        """Подключение водителя для отправки геопозиции"""
        await websocket.accept()
        self.driver_tracking_sockets[driver_id] = websocket
        logger.info(f"Driver {driver_id} connected for location updates")

    def disconnect_driver_tracking(self, driver_id: int):
        """Отключение водителя от трекинга"""
        if driver_id in self.driver_tracking_sockets:
            del self.driver_tracking_sockets[driver_id]
            logger.info(f"Driver {driver_id} disconnected from location updates")

    # Методы для трекинга (подписчики)
    async def connect_tracking_subscriber(self, websocket: WebSocket, driver_id: int, user_id: int):
        """Подключение подписчика к трекингу водителя"""
        await self.connect_user(websocket, user_id)
        
        if driver_id not in self.tracking_connections:
            self.tracking_connections[driver_id] = []
        
        self.tracking_connections[driver_id].append(websocket)
        logger.info(f"User {user_id} subscribed to tracking for driver {driver_id}")

    def disconnect_tracking_subscriber(self, websocket: WebSocket, driver_id: int, user_id: int):
        """Отключение подписчика от трекинга"""
        self.disconnect_user(websocket, user_id)
        
        if driver_id in self.tracking_connections:
            if websocket in self.tracking_connections[driver_id]:
                self.tracking_connections[driver_id].remove(websocket)
            
            if not self.tracking_connections[driver_id]:
                del self.tracking_connections[driver_id]

    async def broadcast_location(self, driver_id: int, location_data: dict):
        """Трансляция местоположения водителя всем подписчикам"""
        # Отправляем подписчикам
        if driver_id in self.tracking_connections:
            disconnected = []
            for connection in self.tracking_connections[driver_id]:
                try:
                    await connection.send_json({
                        "type": "location_update",
                        "driver_id": driver_id,
                        "data": location_data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error broadcasting location to subscriber: {e}")
                    disconnected.append(connection)
            
            for connection in disconnected:
                # Находим user_id для этого соединения
                for uid, connections in self.user_connections.items():
                    if connection in connections:
                        self.disconnect_tracking_subscriber(connection, driver_id, uid)
                        break
        
        # Отправляем администраторам
        disconnected_admins = []
        for connection in self.admin_connections:
            try:
                await connection.send_json({
                    "type": "admin_location_update",
                    "driver_id": driver_id,
                    "data": location_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.error(f"Error broadcasting location to admin: {e}")
                disconnected_admins.append(connection)
        
        for connection in disconnected_admins:
            if connection in self.admin_connections:
                self.admin_connections.remove(connection)

    # Методы для администраторов
    async def connect_admin(self, websocket: WebSocket, admin_id: int):
        """Подключение администратора"""
        await self.connect_user(websocket, admin_id)
        self.admin_connections.append(websocket)
        logger.info(f"Admin {admin_id} connected")

    def disconnect_admin(self, websocket: WebSocket, admin_id: int):
        """Отключение администратора"""
        self.disconnect_user(websocket, admin_id)
        if websocket in self.admin_connections:
            self.admin_connections.remove(websocket)

    async def broadcast_admin_notification(self, notification: dict):
        """Трансляция уведомления администраторам"""
        disconnected = []
        for connection in self.admin_connections:
            try:
                await connection.send_json({
                    "type": "admin_notification",
                    "data": notification,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.error(f"Error broadcasting admin notification: {e}")
                disconnected.append(connection)
        
        for connection in disconnected:
            if connection in self.admin_connections:
                self.admin_connections.remove(connection)

    async def broadcast_system_message(self, message: dict, user_ids: Optional[List[int]] = None):
        """Трансляция системного сообщения"""
        if user_ids:
            # Отправляем конкретным пользователям
            for user_id in user_ids:
                await self.send_to_user(user_id, {
                    "type": "system_message",
                    "data": message,
                    "timestamp": datetime.utcnow().isoformat()
                })
        else:
            # Отправляем всем пользователям
            for user_id in list(self.user_connections.keys()):
                await self.send_to_user(user_id, {
                    "type": "system_message",
                    "data": message,
                    "timestamp": datetime.utcnow().isoformat()
                })

    # Статистика
    def get_stats(self) -> dict:
        """Получение статистики соединений"""
        return {
            "total_users_connected": len(self.user_connections),
            "total_connections": sum(len(conns) for conns in self.user_connections.values()),
            "active_chats": len(self.chat_connections),
            "drivers_tracking": len(self.driver_tracking_sockets),
            "tracking_subscriptions": len(self.tracking_connections),
            "admins_connected": len(self.admin_connections)
        }

# Глобальный экземпляр менеджера
manager = ConnectionManager()