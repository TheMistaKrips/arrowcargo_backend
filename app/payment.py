"""
Платежная система (симуляция)
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid
import logging
from enum import Enum

from . import schemas, crud
from .config import settings

logger = logging.getLogger(__name__)

class PaymentMethod(Enum):
    """Методы оплаты"""
    CARD = "card"
    SBP = "sbp"
    YOOMONEY = "yoomoney"
    PAYPAL = "paypal"

class PaymentGateway:
    """Платежный шлюз (симуляция)"""
    
    def __init__(self):
        self.transactions: Dict[str, Dict] = {}
    
    def create_payment(
        self,
        amount: float,
        currency: str = "RUB",
        description: str = "",
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Создание платежа
        Возвращает: (успех, сообщение, payment_id)
        """
        try:
            # Генерируем ID платежа
            payment_id = f"pay_{uuid.uuid4().hex[:16]}"
            
            # В реальном приложении здесь интеграция с платежным шлюзом
            # (Stripe, YooKassa, CloudPayments и т.д.)
            
            # Сохраняем транзакцию
            self.transactions[payment_id] = {
                "payment_id": payment_id,
                "amount": amount,
                "currency": currency,
                "description": description,
                "metadata": metadata or {},
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Payment created: {payment_id}, amount: {amount} {currency}")
            
            return True, "Payment created successfully", payment_id
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            return False, f"Error creating payment: {str(e)}", None
    
    def confirm_payment(self, payment_id: str) -> Tuple[bool, str]:
        """Подтверждение платежа (симуляция)"""
        if payment_id not in self.transactions:
            return False, "Payment not found"
        
        transaction = self.transactions[payment_id]
        
        # В реальном приложении здесь проверка статуса в платежном шлюзе
        # Для симуляции всегда успех
        transaction["status"] = "succeeded"
        transaction["confirmed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Payment confirmed: {payment_id}")
        return True, "Payment confirmed successfully"
    
    def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> Tuple[bool, str]:
        """Возврат платежа (симуляция)"""
        if payment_id not in self.transactions:
            return False, "Payment not found"
        
        transaction = self.transactions[payment_id]
        
        if transaction["status"] != "succeeded":
            return False, "Payment is not succeeded"
        
        refund_amount = amount or transaction["amount"]
        
        # Создаем запись о возврате
        refund_id = f"ref_{uuid.uuid4().hex[:16]}"
        
        logger.info(f"Payment refunded: {payment_id}, amount: {refund_amount}")
        return True, f"Refund created: {refund_id}"
    
    def get_payment_status(self, payment_id: str) -> Optional[str]:
        """Получение статуса платежа"""
        if payment_id in self.transactions:
            return self.transactions[payment_id]["status"]
        return None

class PaymentService:
    """Сервис оплаты"""
    
    def __init__(self):
        self.gateway = PaymentGateway()
    
    async def create_order_payment(
        self,
        db,
        order_id: int,
        user_id: int,
        payment_method: str
    ) -> Tuple[bool, str, Optional[schemas.PaymentResponse]]:
        """Создание платежа для заказа"""
        try:
            # Получаем заказ
            order = crud.get_order(db, order_id)
            if not order:
                return False, "Order not found", None
            
            # Проверяем, что заказ принадлежит пользователю
            if order.client_id != user_id:
                return False, "Order does not belong to user", None
            
            # Проверяем, что заказ еще не оплачен
            if order.payment_status == schemas.PaymentStatus.COMPLETED:
                return False, "Order already paid", None
            
            # Проверяем финальную цену
            if not order.final_price:
                return False, "Order price is not set", None
            
            # Создаем платеж в базе данных
            payment_create = schemas.PaymentCreate(
                amount=order.final_price,
                order_id=order_id,
                payment_method=payment_method,
                description=f"Оплата заказа #{order.order_number}"
            )
            
            payment = crud.create_payment(db, payment_create, user_id)
            
            # Создаем платеж в платежном шлюзе
            success, message, gateway_payment_id = self.gateway.create_payment(
                amount=order.final_price,
                currency="RUB",
                description=f"Оплата заказа #{order.order_number}",
                metadata={
                    "order_id": order_id,
                    "order_number": order.order_number,
                    "user_id": user_id
                }
            )
            
            if success and gateway_payment_id:
                # Обновляем платеж с ID из шлюза
                payment = crud.update_payment_status(
                    db,
                    payment.id,
                    schemas.PaymentStatus.PROCESSING.value,
                    gateway_payment_id
                )
                
                # Для симуляции сразу подтверждаем платеж
                if settings.TEST_MODE:
                    self.gateway.confirm_payment(gateway_payment_id)
                    payment = crud.update_payment_status(
                        db,
                        payment.id,
                        schemas.PaymentStatus.COMPLETED.value
                    )
                
                logger.info(f"Payment created for order {order_id}: {gateway_payment_id}")
                return True, "Payment created successfully", schemas.PaymentResponse.model_validate(payment)
            else:
                # Если ошибка в шлюзе, обновляем статус
                payment = crud.update_payment_status(
                    db,
                    payment.id,
                    schemas.PaymentStatus.FAILED.value
                )
                return False, f"Payment gateway error: {message}", None
                
        except Exception as e:
            logger.error(f"Error creating payment for order {order_id}: {e}")
            return False, f"Error: {str(e)}", None
    
    async def process_payment_webhook(
        self,
        db,
        payment_id: str,
        status: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """Обработка вебхука от платежного шлюза"""
        try:
            # Находим платеж по payment_id из шлюза
            payment = db.query(crud.models.Payment).filter(
                crud.models.Payment.payment_id == payment_id
            ).first()
            
            if not payment:
                return False, "Payment not found"
            
            # Обновляем статус платежа
            payment_status = self._map_gateway_status(status)
            if not payment_status:
                return False, f"Unknown status: {status}"
            
            payment = crud.update_payment_status(db, payment.id, payment_status)
            
            logger.info(f"Payment webhook processed: {payment_id} -> {status}")
            return True, "Webhook processed successfully"
            
        except Exception as e:
            logger.error(f"Error processing payment webhook: {e}")
            return False, f"Error: {str(e)}"
    
    def _map_gateway_status(self, gateway_status: str) -> Optional[str]:
        """Маппинг статусов платежного шлюза на наши статусы"""
        status_map = {
            "succeeded": schemas.PaymentStatus.COMPLETED.value,
            "pending": schemas.PaymentStatus.PENDING.value,
            "processing": schemas.PaymentStatus.PROCESSING.value,
            "failed": schemas.PaymentStatus.FAILED.value,
            "refunded": schemas.PaymentStatus.REFUNDED.value,
        }
        return status_map.get(gateway_status.lower())
    
    async def create_payout(
        self,
        db,
        driver_id: int,
        amount: float,
        description: str = ""
    ) -> Tuple[bool, str, Optional[str]]:
        """Создание выплаты водителю"""
        try:
            # Проверяем баланс водителя
            driver = crud.get_user_by_id(db, driver_id)
            if not driver:
                return False, "Driver not found", None
            
            if driver.balance < amount:
                return False, "Insufficient balance", None
            
            # Создаем выплату в шлюзе
            success, message, payout_id = self.gateway.create_payment(
                amount=amount,
                currency="RUB",
                description=description or f"Выплата водителю #{driver_id}",
                metadata={
                    "driver_id": driver_id,
                    "type": "payout"
                }
            )
            
            if success:
                # Списание с баланса водителя
                driver.balance -= amount
                db.commit()
                
                logger.info(f"Payout created for driver {driver_id}: {amount} RUB")
                return True, "Payout created successfully", payout_id
            else:
                return False, message, None
                
        except Exception as e:
            logger.error(f"Error creating payout for driver {driver_id}: {e}")
            return False, f"Error: {str(e)}", None
    
    def get_supported_payment_methods(self) -> List[Dict]:
        """Получение списка поддерживаемых методов оплаты"""
        return [
            {
                "id": PaymentMethod.CARD.value,
                "name": "Банковская карта",
                "description": "Оплата картой Visa/Mastercard",
                "min_amount": 10.0,
                "max_amount": 100000.0,
                "currency": "RUB"
            },
            {
                "id": PaymentMethod.SBP.value,
                "name": "Система быстрых платежей (СБП)",
                "description": "Оплата через СБП по номеру телефона",
                "min_amount": 1.0,
                "max_amount": 100000.0,
                "currency": "RUB"
            },
            {
                "id": PaymentMethod.YOOMONEY.value,
                "name": "ЮMoney",
                "description": "Оплата через кошелек ЮMoney",
                "min_amount": 10.0,
                "max_amount": 75000.0,
                "currency": "RUB"
            }
        ]

# Глобальный экземпляр платежного сервиса
payment_service = PaymentService()