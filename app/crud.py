"""
Операции с базой данных (CRUD)
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import random
import string

from . import models, schemas
from .auth import get_password_hash
from .utils import calculate_distance

# User CRUD
def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Создание пользователя"""
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Получение пользователя по email"""
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """Получение пользователя по ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_users(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    role: Optional[str] = None,
    is_active: Optional[bool] = None
) -> List[models.User]:
    """Получение списка пользователей"""
    query = db.query(models.User)
    
    if role:
        query = query.filter(models.User.role == role)
    if is_active is not None:
        query = query.filter(models.User.is_active == is_active)
    
    return query.order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()

def update_user(
    db: Session, 
    user_id: int, 
    user_update: schemas.UserUpdate
) -> Optional[models.User]:
    """Обновление пользователя"""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: int) -> bool:
    """Удаление пользователя"""
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    db.delete(user)
    db.commit()
    return True

# Driver Profile CRUD
def create_driver_profile(
    db: Session, 
    profile: schemas.DriverProfileCreate, 
    user_id: int
) -> models.DriverProfile:
    """Создание профиля водителя"""
    db_profile = models.DriverProfile(
        user_id=user_id,
        **profile.model_dump()
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

def get_driver_profile(db: Session, user_id: int) -> Optional[models.DriverProfile]:
    """Получение профиля водителя"""
    return db.query(models.DriverProfile).filter(models.DriverProfile.user_id == user_id).first()

def get_driver_profiles(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    verification_status: Optional[str] = None,
    is_online: Optional[bool] = None
) -> List[models.DriverProfile]:
    """Получение списка профилей водителей"""
    query = db.query(models.DriverProfile)
    
    if verification_status:
        query = query.filter(models.DriverProfile.verification_status == verification_status)
    if is_online is not None:
        query = query.filter(models.DriverProfile.is_online == is_online)
    
    return query.order_by(desc(models.DriverProfile.rating)).offset(skip).limit(limit).all()

def update_driver_profile(
    db: Session, 
    user_id: int, 
    profile_update: schemas.DriverProfileUpdate
) -> Optional[models.DriverProfile]:
    """Обновление профиля водителя"""
    profile = get_driver_profile(db, user_id)
    if not profile:
        return None
    
    update_data = profile_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return profile

def update_driver_location(
    db: Session,
    user_id: int,
    lat: float,
    lng: float
) -> Optional[models.DriverProfile]:
    """Обновление местоположения водителя"""
    profile = get_driver_profile(db, user_id)
    if not profile:
        return None
    
    profile.current_location_lat = lat
    profile.current_location_lng = lng
    profile.is_online = True
    
    db.commit()
    db.refresh(profile)
    return profile

def verify_driver_profile(
    db: Session,
    user_id: int,
    status: str,
    notes: Optional[str] = None
) -> Optional[models.DriverProfile]:
    """Верификация профиля водителя"""
    profile = get_driver_profile(db, user_id)
    if not profile:
        return None
    
    profile.verification_status = status
    
    # Если верифицирован, активируем пользователя
    if status == models.VerificationStatus.VERIFIED:
        user = get_user_by_id(db, user_id)
        if user:
            user.is_verified = True
    
    db.commit()
    db.refresh(profile)
    return profile

# Order CRUD
def generate_order_number() -> str:
    """Генерация номера заказа"""
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    numbers = ''.join(random.choices(string.digits, k=6))
    return f"CP{letters}{numbers}"

def create_order(db: Session, order: schemas.OrderCreate, client_id: int) -> models.Order:
    """Создание заказа"""
    # Расчет расстояния
    distance = calculate_distance(
        order.from_lat, order.from_lng,
        order.to_lat, order.to_lng
    )
    
    db_order = models.Order(
        order_number=generate_order_number(),
        client_id=client_id,
        distance_km=distance,
        **order.model_dump()
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def get_order(db: Session, order_id: int) -> Optional[models.Order]:
    """Получение заказа по ID"""
    return db.query(models.Order).filter(models.Order.id == order_id).first()

def get_order_by_number(db: Session, order_number: str) -> Optional[models.Order]:
    """Получение заказа по номеру"""
    return db.query(models.Order).filter(models.Order.order_number == order_number).first()

def get_orders(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[int] = None,
    driver_id: Optional[int] = None,
    status: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    cargo_type: Optional[str] = None
) -> List[models.Order]:
    """Получение списка заказов"""
    query = db.query(models.Order)
    
    if client_id:
        query = query.filter(models.Order.client_id == client_id)
    if driver_id:
        query = query.filter(models.Order.driver_id == driver_id)
    if status:
        query = query.filter(models.Order.status == status)
    if min_price:
        query = query.filter(models.Order.desired_price >= min_price)
    if max_price:
        query = query.filter(models.Order.desired_price <= max_price)
    if cargo_type:
        query = query.filter(models.Order.cargo_type == cargo_type)
    
    return query.order_by(desc(models.Order.created_at)).offset(skip).limit(limit).all()

def get_available_orders(
    db: Session,
    driver_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[models.Order]:
    """Получение доступных для заказа водителей"""
    query = db.query(models.Order).filter(
        models.Order.status.in_([models.OrderStatus.SEARCHING])
    )
    
    # Если указан водитель, можно добавить фильтры по его возможностям
    if driver_id:
        driver_profile = get_driver_profile(db, driver_id)
        if driver_profile:
            # Фильтр по грузоподъемности и объему
            query = query.filter(
                models.Order.cargo_weight <= driver_profile.carrying_capacity,
                models.Order.cargo_volume <= driver_profile.volume
            )
    
    return query.order_by(desc(models.Order.created_at)).offset(skip).limit(limit).all()

def update_order(
    db: Session, 
    order_id: int, 
    order_update: schemas.OrderUpdate
) -> Optional[models.Order]:
    """Обновление заказа"""
    order = get_order(db, order_id)
    if not order:
        return None
    
    update_data = order_update.model_dump(exclude_unset=True)
    
    # Если назначается водитель, меняем статус
    if "driver_id" in update_data and update_data["driver_id"]:
        order.status = models.OrderStatus.DRIVER_ASSIGNED
    
    # Если устанавливается финальная цена, рассчитываем комиссию
    if "final_price" in update_data and update_data["final_price"]:
        order.final_price = update_data["final_price"]
        order.platform_fee = order.final_price * 0.05  # 5% комиссия
        order.order_amount = order.final_price - order.platform_fee
    
    for field, value in update_data.items():
        if field != "final_price":  # Уже обработали
            setattr(order, field, value)
    
    db.commit()
    db.refresh(order)
    return order

def complete_order(db: Session, order_id: int) -> Optional[models.Order]:
    """Завершение заказа"""
    order = get_order(db, order_id)
    if not order:
        return None
    
    order.status = models.OrderStatus.COMPLETED
    order.completed_at = datetime.utcnow()
    
    # Обновляем статистику водителя
    if order.driver_id:
        profile = get_driver_profile(db, order.driver_id)
        if profile:
            profile.total_orders += 1
            if order.distance_km:
                profile.total_distance += order.distance_km
    
    db.commit()
    db.refresh(order)
    return order

def cancel_order(db: Session, order_id: int) -> Optional[models.Order]:
    """Отмена заказа"""
    order = get_order(db, order_id)
    if not order:
        return None
    
    order.status = models.OrderStatus.CANCELLED
    
    # Отменяем все ставки по этому заказу
    bids = db.query(models.Bid).filter(models.Bid.order_id == order_id).all()
    for bid in bids:
        bid.status = models.BidStatus.CANCELLED
    
    db.commit()
    db.refresh(order)
    return order

# Bid CRUD
def create_bid(
    db: Session, 
    bid: schemas.BidCreate, 
    order_id: int, 
    driver_id: int
) -> models.Bid:
    """Создание ставки"""
    # Проверяем, что заказ доступен для ставок
    order = get_order(db, order_id)
    if not order or order.status != models.OrderStatus.SEARCHING:
        raise ValueError("Order is not available for bidding")
    
    # Проверяем, что водитель уже не делал ставку
    existing_bid = db.query(models.Bid).filter(
        models.Bid.order_id == order_id,
        models.Bid.driver_id == driver_id
    ).first()
    
    if existing_bid:
        raise ValueError("You already placed a bid on this order")
    
    db_bid = models.Bid(
        order_id=order_id,
        driver_id=driver_id,
        **bid.model_dump()
    )
    db.add(db_bid)
    db.commit()
    db.refresh(db_bid)
    return db_bid

def get_bid(db: Session, bid_id: int) -> Optional[models.Bid]:
    """Получение ставки по ID"""
    return db.query(models.Bid).filter(models.Bid.id == bid_id).first()

def get_bids_by_order(db: Session, order_id: int) -> List[models.Bid]:
    """Получение ставок по заказу"""
    return db.query(models.Bid).filter(models.Bid.order_id == order_id).all()

def get_bids_by_driver(db: Session, driver_id: int) -> List[models.Bid]:
    """Получение ставок водителя"""
    return db.query(models.Bid).filter(models.Bid.driver_id == driver_id).all()

def accept_bid(db: Session, bid_id: int) -> Optional[models.Bid]:
    """Принятие ставки"""
    bid = get_bid(db, bid_id)
    if not bid:
        return None
    
    # Обновляем статус ставки
    bid.status = models.BidStatus.ACCEPTED
    
    # Обновляем заказ
    order = get_order(db, bid.order_id)
    if order:
        order.driver_id = bid.driver_id
        order.status = models.OrderStatus.DRIVER_ASSIGNED
        order.final_price = bid.proposed_price
        order.platform_fee = bid.proposed_price * 0.05
        order.order_amount = bid.proposed_price - order.platform_fee
    
    # Отклоняем все другие ставки по этому заказу
    other_bids = db.query(models.Bid).filter(
        and_(
            models.Bid.order_id == bid.order_id,
            models.Bid.id != bid_id
        )
    ).all()
    
    for other_bid in other_bids:
        other_bid.status = models.BidStatus.REJECTED
    
    db.commit()
    db.refresh(bid)
    return bid

def reject_bid(db: Session, bid_id: int) -> Optional[models.Bid]:
    """Отклонение ставки"""
    bid = get_bid(db, bid_id)
    if not bid:
        return None
    
    bid.status = models.BidStatus.REJECTED
    db.commit()
    db.refresh(bid)
    return bid

# Message CRUD
def create_message(
    db: Session, 
    message: schemas.MessageCreate, 
    order_id: int, 
    sender_id: int
) -> models.Message:
    """Создание сообщения"""
    db_message = models.Message(
        order_id=order_id,
        sender_id=sender_id,
        **message.model_dump()
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def get_messages_by_order(
    db: Session, 
    order_id: int, 
    skip: int = 0, 
    limit: int = 100
) -> List[models.Message]:
    """Получение сообщений по заказу"""
    return db.query(models.Message)\
        .filter(models.Message.order_id == order_id)\
        .order_by(models.Message.timestamp.asc())\
        .offset(skip)\
        .limit(limit)\
        .all()

def mark_messages_as_read(
    db: Session,
    order_id: int,
    user_id: int
) -> int:
    """Пометка сообщений как прочитанных"""
    result = db.query(models.Message)\
        .filter(
            models.Message.order_id == order_id,
            models.Message.sender_id != user_id,
            models.Message.is_read == False
        )\
        .update({"is_read": True})
    
    db.commit()
    return result

# Location CRUD
def create_location_update(
    db: Session, 
    location: schemas.LocationCreate, 
    driver_id: int
) -> models.LocationUpdate:
    """Создание обновления местоположения"""
    db_location = models.LocationUpdate(
        driver_id=driver_id,
        **location.model_dump()
    )
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    return db_location

def get_locations_by_driver(
    db: Session, 
    driver_id: int, 
    order_id: Optional[int] = None,
    limit: int = 100
) -> List[models.LocationUpdate]:
    """Получение обновлений местоположения водителя"""
    query = db.query(models.LocationUpdate)\
        .filter(models.LocationUpdate.driver_id == driver_id)
    
    if order_id:
        query = query.filter(models.LocationUpdate.order_id == order_id)
    
    return query\
        .order_by(desc(models.LocationUpdate.timestamp))\
        .limit(limit)\
        .all()

# Payment CRUD
def create_payment(
    db: Session,
    payment: schemas.PaymentCreate,
    user_id: int
) -> models.Payment:
    """Создание платежа"""
    db_payment = models.Payment(
        user_id=user_id,
        **payment.model_dump()
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def get_payment(db: Session, payment_id: int) -> Optional[models.Payment]:
    """Получение платежа по ID"""
    return db.query(models.Payment).filter(models.Payment.id == payment_id).first()

def update_payment_status(
    db: Session,
    payment_id: int,
    status: str,
    payment_id_external: Optional[str] = None
) -> Optional[models.Payment]:
    """Обновление статуса платежа"""
    payment = get_payment(db, payment_id)
    if not payment:
        return None
    
    payment.status = status
    if payment_id_external:
        payment.payment_id = payment_id_external
    
    if status == models.PaymentStatus.COMPLETED:
        payment.completed_at = datetime.utcnow()
        
        # Обновляем баланс пользователя
        user = get_user_by_id(db, payment.user_id)
        if user:
            user.balance += payment.amount
        
        # Обновляем статус заказа
        if payment.order_id:
            order = get_order(db, payment.order_id)
            if order:
                order.payment_status = models.PaymentStatus.COMPLETED
                order.status = models.OrderStatus.PAID
    
    db.commit()
    db.refresh(payment)
    return payment

# Statistics
def get_system_stats(db: Session) -> Dict[str, Any]:
    """Получение системной статистики"""
    stats = {}
    
    # Пользователи
    stats["total_users"] = db.query(func.count(models.User.id)).scalar()
    stats["total_drivers"] = db.query(func.count(models.User.id))\
        .filter(models.User.role == models.UserRole.DRIVER)\
        .scalar()
    stats["total_clients"] = db.query(func.count(models.User.id))\
        .filter(models.User.role == models.UserRole.CLIENT)\
        .scalar()
    
    # Заказы
    stats["total_orders"] = db.query(func.count(models.Order.id)).scalar()
    stats["active_orders"] = db.query(func.count(models.Order.id))\
        .filter(
            models.Order.status.in_([
                models.OrderStatus.SEARCHING,
                models.OrderStatus.DRIVER_ASSIGNED,
                models.OrderStatus.LOADING,
                models.OrderStatus.EN_ROUTE
            ])
        )\
        .scalar()
    
    # Выручка
    stats["total_revenue"] = db.query(func.coalesce(func.sum(models.Order.platform_fee), 0)).scalar() or 0
    
    # Ожидающие верификации
    stats["pending_verifications"] = db.query(func.count(models.DriverProfile.id))\
        .filter(models.DriverProfile.verification_status == models.VerificationStatus.PENDING)\
        .scalar()
    
    # За последние 7 дней
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    stats["new_users_week"] = db.query(func.count(models.User.id))\
        .filter(models.User.created_at >= week_ago)\
        .scalar()
    
    stats["new_orders_week"] = db.query(func.count(models.Order.id))\
        .filter(models.Order.created_at >= week_ago)\
        .scalar()
    
    stats["revenue_week"] = db.query(func.coalesce(func.sum(models.Order.platform_fee), 0))\
        .filter(
            models.Order.created_at >= week_ago,
            models.Order.payment_status == models.PaymentStatus.COMPLETED
        )\
        .scalar() or 0
    
    return stats