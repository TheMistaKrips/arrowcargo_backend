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

def create_company(db: Session, company: schemas.CompanyCreate, user_id: int) -> models.Company:
    """Создание компании"""
    db_company = models.Company(
        user_id=user_id,
        **company.model_dump()
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    
    # Обновляем пользователя
    user = get_user_by_id(db, user_id)
    if user:
        user.company_id = db_company.id
        db.commit()
    
    return db_company

def get_company(db: Session, company_id: int) -> Optional[models.Company]:
    """Получение компании по ID"""
    return db.query(models.Company).filter(models.Company.id == company_id).first()

def get_company_by_user(db: Session, user_id: int) -> Optional[models.Company]:
    """Получение компании по user_id"""
    return db.query(models.Company).filter(models.Company.user_id == user_id).first()

def get_companies(db: Session, skip: int = 0, limit: int = 100, 
                  verification_status: Optional[str] = None) -> List[models.Company]:
    """Получение списка компаний"""
    query = db.query(models.Company)
    
    if verification_status:
        query = query.filter(models.Company.verification_status == verification_status)
    
    return query.order_by(desc(models.Company.created_at)).offset(skip).limit(limit).all()

def verify_company(db: Session, company_id: int, status: str, 
                   notes: Optional[str] = None) -> Optional[models.Company]:
    """Верификация компании"""
    company = get_company(db, company_id)
    if not company:
        return None
    
    company.verification_status = status
    db.commit()
    db.refresh(company)
    
    # Создаем запись в журнале аудита
    create_audit_log(db, {
        "user_id": None,  # Система
        "action": "verify_company",
        "entity_type": "company",
        "entity_id": company_id,
        "new_values": {"verification_status": status, "notes": notes}
    })
    
    return company

# Contract CRUD
def create_contract(db: Session, contract: schemas.ContractCreate) -> models.Contract:
    """Создание договора"""
    db_contract = models.Contract(**contract.model_dump())
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)
    return db_contract

def get_contract(db: Session, contract_id: int) -> Optional[models.Contract]:
    """Получение договора по ID"""
    return db.query(models.Contract).filter(models.Contract.id == contract_id).first()

def get_contract_by_order(db: Session, order_id: int) -> Optional[models.Contract]:
    """Получение договора по order_id"""
    return db.query(models.Contract).filter(models.Contract.order_id == order_id).first()

def update_contract_status(db: Session, contract_id: int, status: str, 
                          signature_data: Optional[Dict] = None) -> Optional[models.Contract]:
    """Обновление статуса договора"""
    contract = get_contract(db, contract_id)
    if not contract:
        return None
    
    contract.status = status
    
    if signature_data:
        if signature_data.get("signed_by") == "client":
            contract.signed_by_client_at = datetime.utcnow()
        elif signature_data.get("signed_by") == "driver":
            contract.signed_by_driver_at = datetime.utcnow()
        elif signature_data.get("signed_by") == "platform":
            contract.signed_by_platform_at = datetime.utcnow()
        
        if signature_data.get("metadata"):
            contract.metadata = signature_data["metadata"]
    
    db.commit()
    db.refresh(contract)
    
    # Аудит
    create_audit_log(db, {
        "user_id": signature_data.get("user_id") if signature_data else None,
        "action": f"sign_contract_{signature_data.get('signed_by', 'unknown')}" if signature_data else "update_contract_status",
        "entity_type": "contract",
        "entity_id": contract_id,
        "new_values": {"status": status, "signature_data": signature_data}
    })
    
    return contract

# ContractTemplate CRUD
def create_contract_template(db: Session, template: schemas.ContractTemplateCreate) -> models.ContractTemplate:
    """Создание шаблона договора"""
    db_template = models.ContractTemplate(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def get_contract_template(db: Session, template_id: int) -> Optional[models.ContractTemplate]:
    """Получение шаблона по ID"""
    return db.query(models.ContractTemplate).filter(models.ContractTemplate.id == template_id).first()

def get_contract_templates(db: Session, template_type: Optional[str] = None, 
                          is_active: bool = True) -> List[models.ContractTemplate]:
    """Получение списка шаблонов"""
    query = db.query(models.ContractTemplate).filter(models.ContractTemplate.is_active == is_active)
    
    if template_type:
        query = query.filter(models.ContractTemplate.template_type == template_type)
    
    return query.order_by(desc(models.ContractTemplate.created_at)).all()

def generate_contract_pdf(db: Session, contract_id: int, template_variables: Dict) -> str:
    """Генерация PDF договора"""
    contract = get_contract(db, contract_id)
    if not contract:
        raise ValueError("Contract not found")
    
    # Временная заглушка - в продакшене интегрировать с библиотекой для генерации PDF
    import uuid
    pdf_path = f"contracts/{contract_id}_{uuid.uuid4().hex[:8]}.pdf"
    
    # Обновляем путь в договоре
    contract.pdf_path = pdf_path
    db.commit()
    
    return pdf_path

# CargoDocument CRUD
def create_cargo_document(db: Session, document: schemas.CargoDocumentCreate, 
                         uploaded_by: int) -> models.CargoDocument:
    """Создание документа на груз"""
    db_document = models.CargoDocument(
        uploaded_by=uploaded_by,
        **document.model_dump()
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

def get_cargo_document(db: Session, document_id: int) -> Optional[models.CargoDocument]:
    """Получение документа по ID"""
    return db.query(models.CargoDocument).filter(models.CargoDocument.id == document_id).first()

def get_cargo_documents_by_order(db: Session, order_id: int) -> List[models.CargoDocument]:
    """Получение документов по заказу"""
    return db.query(models.CargoDocument).filter(models.CargoDocument.order_id == order_id).all()

# Review CRUD
def create_review(db: Session, review: schemas.ReviewCreate, reviewer_id: int) -> models.Review:
    """Создание отзыва"""
    # Проверяем, что заказ завершен
    order = get_order(db, review.order_id)
    if not order or order.status != models.OrderStatus.COMPLETED:
        raise ValueError("Можно оставлять отзывы только по завершенным заказам")
    
    # Проверяем, что отзыв пишет участник заказа
    if reviewer_id not in [order.client_id, order.driver_id]:
        raise ValueError("Только участники заказа могут оставлять отзывы")
    
    # Проверяем, что отзыв пишется другому участнику
    if reviewer_id == review.reviewed_id:
        raise ValueError("Нельзя оставить отзыв самому себе")
    
    # Проверяем, что отзыв еще не оставлен
    existing_review = db.query(models.Review).filter(
        models.Review.order_id == review.order_id,
        models.Review.reviewer_id == reviewer_id
    ).first()
    
    if existing_review:
        raise ValueError("Вы уже оставили отзыв по этому заказу")
    
    db_review = models.Review(
        reviewer_id=reviewer_id,
        **review.model_dump()
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    
    # Обновляем рейтинг пользователя
    update_user_rating(db, review.reviewed_id)
    
    return db_review

def get_reviews_by_user(db: Session, user_id: int) -> List[models.Review]:
    """Получение отзывов о пользователе"""
    return db.query(models.Review).filter(models.Review.reviewed_id == user_id).all()

def update_user_rating(db: Session, user_id: int) -> None:
    """Обновление рейтинга пользователя"""
    reviews = get_reviews_by_user(db, user_id)
    if not reviews:
        return
    
    avg_rating = sum([r.rating for r in reviews]) / len(reviews)
    
    user = get_user_by_id(db, user_id)
    if user:
        # Предполагаем, что в User есть поле rating
        # Если нет, нужно добавить
        user.rating = avg_rating
        db.commit()

# SupportTicket CRUD
def create_support_ticket(db: Session, ticket: schemas.SupportTicketCreate, 
                         user_id: int) -> models.SupportTicket:
    """Создание тикета поддержки"""
    db_ticket = models.SupportTicket(
        user_id=user_id,
        **ticket.model_dump()
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

def get_support_ticket(db: Session, ticket_id: int) -> Optional[models.SupportTicket]:
    """Получение тикета по ID"""
    return db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()

def get_support_tickets(db: Session, skip: int = 0, limit: int = 100,
                       status: Optional[str] = None, 
                       priority: Optional[str] = None,
                       assigned_to: Optional[int] = None) -> List[models.SupportTicket]:
    """Получение списка тикетов"""
    query = db.query(models.SupportTicket)
    
    if status:
        query = query.filter(models.SupportTicket.status == status)
    if priority:
        query = query.filter(models.SupportTicket.priority == priority)
    if assigned_to:
        query = query.filter(models.SupportTicket.assigned_to == assigned_to)
    
    return query.order_by(desc(models.SupportTicket.created_at)).offset(skip).limit(limit).all()

def update_ticket_status(db: Session, ticket_id: int, status: str,
                        resolution_notes: Optional[str] = None,
                        assigned_to: Optional[int] = None) -> Optional[models.SupportTicket]:
    """Обновление статуса тикета"""
    ticket = get_support_ticket(db, ticket_id)
    if not ticket:
        return None
    
    ticket.status = status
    
    if status == "resolved":
        ticket.resolved_at = datetime.utcnow()
    
    if resolution_notes:
        ticket.resolution_notes = resolution_notes
    
    if assigned_to:
        ticket.assigned_to = assigned_to
    
    db.commit()
    db.refresh(ticket)
    return ticket

# AuditLog CRUD
def create_audit_log(db: Session, audit_data: Dict) -> models.AuditLog:
    """Создание записи в журнале аудита"""
    db_log = models.AuditLog(**audit_data)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_audit_logs(db: Session, skip: int = 0, limit: int = 100,
                  user_id: Optional[int] = None,
                  entity_type: Optional[str] = None,
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None) -> List[models.AuditLog]:
    """Получение журнала аудита"""
    query = db.query(models.AuditLog)
    
    if user_id:
        query = query.filter(models.AuditLog.user_id == user_id)
    if entity_type:
        query = query.filter(models.AuditLog.entity_type == entity_type)
    if start_date:
        query = query.filter(models.AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(models.AuditLog.created_at <= end_date)
    
    return query.order_by(desc(models.AuditLog.created_at)).offset(skip).limit(limit).all()

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