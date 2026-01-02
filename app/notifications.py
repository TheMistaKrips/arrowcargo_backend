"""
Система уведомлений
"""
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
import logging
from enum import Enum

from . import crud, schemas
from .websocket_manager import manager

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """Типы уведомлений"""
    # Для мобильного приложения водителей
    NEW_ORDER_AVAILABLE = "new_order_available"
    BID_ACCEPTED = "bid_accepted"
    BID_REJECTED = "bid_rejected"
    ORDER_ASSIGNED = "order_assigned"
    ORDER_UPDATED = "order_updated"
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    
    # Для админ-панели
    NEW_DRIVER_REGISTERED = "new_driver_registered"
    NEW_ORDER_CREATED = "new_order_created"
    PAYMENT_RECEIVED = "payment_received"
    VERIFICATION_REQUIRED = "verification_required"
    
    # Для основного сайта
    DRIVER_ASSIGNED = "driver_assigned"
    ORDER_IN_PROGRESS = "order_in_progress"
    ORDER_DELIVERED = "order_delivered"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"

class NotificationService:
    def __init__(self):
        self.notification_templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """Загрузка шаблонов уведомлений"""
        return {
            NotificationType.NEW_ORDER_AVAILABLE.value: {
                "title": "Новый заказ доступен",
                "message": "Появился новый заказ по вашему маршруту"
            },
            NotificationType.BID_ACCEPTED.value: {
                "title": "Ваша ставка принята",
                "message": "Поздравляем! Ваша ставка на заказ была принята"
            },
            NotificationType.BID_REJECTED.value: {
                "title": "Ваша ставка отклонена",
                "message": "К сожалению, ваша ставка на заказ была отклонена"
            },
            NotificationType.ORDER_ASSIGNED.value: {
                "title": "Заказ назначен",
                "message": "Вам назначен новый заказ"
            },
            NotificationType.ORDER_UPDATED.value: {
                "title": "Заказ обновлен",
                "message": "В заказе произошли изменения"
            },
            NotificationType.ORDER_COMPLETED.value: {
                "title": "Заказ завершен",
                "message": "Заказ успешно завершен"
            },
            NotificationType.ORDER_CANCELLED.value: {
                "title": "Заказ отменен",
                "message": "Заказ был отменен"
            },
            NotificationType.NEW_DRIVER_REGISTERED.value: {
                "title": "Новый водитель",
                "message": "Зарегистрирован новый водитель"
            },
            NotificationType.NEW_ORDER_CREATED.value: {
                "title": "Новый заказ",
                "message": "Создан новый заказ на перевозку"
            },
            NotificationType.PAYMENT_RECEIVED.value: {
                "title": "Получен платеж",
                "message": "Поступила оплата за заказ"
            },
            NotificationType.VERIFICATION_REQUIRED.value: {
                "title": "Требуется верификация",
                "message": "Новый водитель ожидает верификации"
            },
            NotificationType.DRIVER_ASSIGNED.value: {
                "title": "Водитель назначен",
                "message": "На ваш заказ назначен водитель"
            },
            NotificationType.ORDER_IN_PROGRESS.value: {
                "title": "Заказ в процессе",
                "message": "Ваш заказ выполняется"
            },
            NotificationType.ORDER_DELIVERED.value: {
                "title": "Заказ доставлен",
                "message": "Ваш заказ успешно доставлен"
            },
            NotificationType.PAYMENT_SUCCESS.value: {
                "title": "Оплата успешна",
                "message": "Оплата за заказ прошла успешно"
            },
            NotificationType.PAYMENT_FAILED.value: {
                "title": "Ошибка оплаты",
                "message": "При оплате заказа произошла ошибка"
            }
        }
    
    def _get_template(self, notification_type: str) -> Dict[str, str]:
        """Получение шаблона уведомления"""
        return self.notification_templates.get(notification_type, {
            "title": "Уведомление",
            "message": "Новое уведомление"
        })
    
    async def send_notification(
        self,
        db,
        user_id: int,
        notification_type: str,
        data: Optional[Dict] = None
    ) -> schemas.NotificationResponse:
        """Отправка уведомления пользователю"""
        template = self._get_template(notification_type)
        
        # Создаем уведомление в базе данных
        notification = crud.models.Notification(
            user_id=user_id,
            title=template["title"],
            message=template["message"],
            type=notification_type,
            data=data or {}
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        # Отправляем через WebSocket
        try:
            await manager.send_to_user(user_id, {
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
        except Exception as e:
            logger.error(f"Error sending notification via WebSocket: {e}")
        
        return schemas.NotificationResponse.model_validate(notification)
    
    async def send_bulk_notifications(
        self,
        db,
        user_ids: List[int],
        notification_type: str,
        data: Optional[Dict] = None
    ) -> List[schemas.NotificationResponse]:
        """Массовая отправка уведомлений"""
        notifications = []
        for user_id in user_ids:
            try:
                notification = await self.send_notification(db, user_id, notification_type, data)
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Error sending notification to user {user_id}: {e}")
        
        return notifications
    
    async def notify_new_order(self, db, order_id: int):
        """Уведомление о новом заказе"""
        order = crud.get_order(db, order_id)
        if not order:
            return
        
        # Получаем водителей поблизости (упрощенная версия)
        # В реальном приложении здесь должен быть поиск по геолокации
        drivers = crud.get_driver_profiles(db, verification_status="verified", is_online=True)
        
        for driver_profile in drivers[:50]:  # Ограничиваем количество
            await self.send_notification(
                db,
                driver_profile.user_id,
                NotificationType.NEW_ORDER_AVAILABLE.value,
                {
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "from_address": order.from_address,
                    "to_address": order.to_address,
                    "price": order.desired_price,
                    "distance": order.distance_km
                }
            )
        
        # Уведомление администраторов
        admins = crud.get_users(db, role="admin", is_active=True)
        for admin in admins:
            await self.send_notification(
                db,
                admin.id,
                NotificationType.NEW_ORDER_CREATED.value,
                {
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "client_id": order.client_id,
                    "price": order.desired_price
                }
            )
    
    async def notify_bid_accepted(self, db, bid_id: int):
        """Уведомление о принятии ставки"""
        bid = crud.get_bid(db, bid_id)
        if not bid:
            return
        
        # Водителю
        await self.send_notification(
            db,
            bid.driver_id,
            NotificationType.BID_ACCEPTED.value,
            {
                "bid_id": bid.id,
                "order_id": bid.order_id,
                "proposed_price": bid.proposed_price
            }
        )
        
        # Клиенту
        order = crud.get_order(db, bid.order_id)
        if order:
            await self.send_notification(
                db,
                order.client_id,
                NotificationType.DRIVER_ASSIGNED.value,
                {
                    "order_id": order.id,
                    "driver_id": bid.driver_id,
                    "driver_name": bid.driver.full_name if bid.driver else None
                }
            )
    
    async def notify_order_completed(self, db, order_id: int):
        """Уведомление о завершении заказа"""
        order = crud.get_order(db, order_id)
        if not order:
            return
        
        # Клиенту
        await self.send_notification(
            db,
            order.client_id,
            NotificationType.ORDER_DELIVERED.value,
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "final_price": order.final_price
            }
        )
        
        # Водителю
        if order.driver_id:
            await self.send_notification(
                db,
                order.driver_id,
                NotificationType.ORDER_COMPLETED.value,
                {
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "order_amount": order.order_amount
                }
            )
    
    async def notify_payment_success(self, db, payment_id: int):
        """Уведомление об успешной оплате"""
        payment = crud.get_payment(db, payment_id)
        if not payment:
            return
        
        # Клиенту
        await self.send_notification(
            db,
            payment.user_id,
            NotificationType.PAYMENT_SUCCESS.value,
            {
                "payment_id": payment.id,
                "amount": payment.amount,
                "order_id": payment.order_id
            }
        )
        
        # Администраторам
        admins = crud.get_users(db, role="admin", is_active=True)
        for admin in admins:
            await self.send_notification(
                db,
                admin.id,
                NotificationType.PAYMENT_RECEIVED.value,
                {
                    "payment_id": payment.id,
                    "user_id": payment.user_id,
                    "amount": payment.amount
                }
            )

# Глобальный экземпляр сервиса уведомлений
notification_service = NotificationService()