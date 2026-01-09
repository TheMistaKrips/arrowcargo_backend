"""
Модели базы данных
"""
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base

class UserRole(str, enum.Enum):
    CLIENT = "client"
    DRIVER = "driver"
    ADMIN = "admin"

class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Company(Base):
    """Компания (для юр. лиц)"""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    inn = Column(String, unique=True, nullable=False)
    kpp = Column(String, nullable=True)
    ogrn = Column(String, nullable=False)
    legal_address = Column(String, nullable=False)
    actual_address = Column(String, nullable=True)
    bank_name = Column(String, nullable=False)
    bank_account = Column(String, nullable=False)
    corr_account = Column(String, nullable=True)
    bic = Column(String, nullable=False)
    director_name = Column(String, nullable=False)
    director_position = Column(String, nullable=False)
    documents = Column(JSON, nullable=True)  # {"egrul": "path", "order": "path"}
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", backref="company")

class Contract(Base):
    """Договор/контракт"""
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(Integer, ForeignKey("contract_templates.id"), nullable=True)
    pdf_path = Column(String, nullable=True)
    signed_by_client_at = Column(DateTime(timezone=True), nullable=True)
    signed_by_driver_at = Column(DateTime(timezone=True), nullable=True)
    signed_by_platform_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="draft")  # draft, sent, signed, archived
    contract_metadata = Column(JSON, nullable=True)  # Подписанты, даты, номера
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    order = relationship("Order", backref="contract")
    template = relationship("ContractTemplate")

class CargoDocument(Base):
    """Документы на груз"""
    __tablename__ = "cargo_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String, nullable=False)  # ttn, invoice, packing_list, photo
    file_path = Column(String, nullable=False)
    description = Column(String, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", backref="cargo_documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    
class ContractTemplate(Base):
    """Шаблон договора"""
    __tablename__ = "contract_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    template_type = Column(String, nullable=False)  # client_agreement, driver_agreement, transport
    html_content = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)  # {"client_name": "string", "order_id": "int"}
    is_active = Column(Boolean, default=True)
    version = Column(String, default="1.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Review(Base):
    """Отзывы и рейтинги"""
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Float, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    category_ratings = Column(JSON, nullable=True)  # {"punctuality": 5, "communication": 4, ...}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", backref="review")
    reviewer = relationship("User", foreign_keys=[reviewer_id], backref="given_reviews")
    reviewed = relationship("User", foreign_keys=[reviewed_id], backref="received_reviews")

class SupportTicket(Base):
    """Тикет поддержки"""
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    category = Column(String, nullable=False)  # technical, financial, dispute, other
    priority = Column(String, default="medium")  # low, medium, high, critical
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="open")  # open, in_progress, resolved, closed
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)  # admin
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="tickets")
    order = relationship("Order", backref="tickets")
    assignee = relationship("User", foreign_keys=[assigned_to])

class AuditLog(Base):
    """Журнал аудита действий"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)  # create, update, delete, login, etc.
    entity_type = Column(String, nullable=False)  # user, order, bid, etc.
    entity_id = Column(Integer, nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")

class OrderStatus(str, enum.Enum):
    DRAFT = "draft"              # Черновик
    SEARCHING = "searching"      # Поиск водителя
    DRIVER_ASSIGNED = "driver_assigned"  # Водитель назначен
    LOADING = "loading"          # Погрузка
    EN_ROUTE = "en_route"        # В пути
    UNLOADING = "unloading"      # Разгрузка
    COMPLETED = "completed"      # Завершен
    CANCELLED = "cancelled"      # Отменен
    PAID = "paid"                # Оплачен

class BidStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    default_payment_method = Column(String, nullable=True)
    notification_settings = Column(JSON, default=lambda: {
        "email": True,
        "push": True,
        "sms": False,
        "new_order": True,
        "order_updates": True,
        "promotions": False
    })
    
    # Relationships
    driver_profile = relationship("DriverProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    orders_as_client = relationship("Order", foreign_keys="Order.client_id", back_populates="client")
    orders_as_driver = relationship("Order", foreign_keys="Order.driver_id", back_populates="driver")
    bids = relationship("Bid", back_populates="driver", cascade="all, delete-orphan")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    location_updates = relationship("LocationUpdate", back_populates="driver")
    payments = relationship("Payment", back_populates="user")

class DriverProfile(Base):
    __tablename__ = "driver_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    vehicle_type = Column(String, nullable=False)
    vehicle_model = Column(String, nullable=True)
    vehicle_number = Column(String, nullable=False)
    carrying_capacity = Column(Float, nullable=False)  # в тоннах
    volume = Column(Float, nullable=False)  # в м³
    license_path = Column(String, nullable=True)
    passport_path = Column(String, nullable=True)
    vehicle_registration_path = Column(String, nullable=True)
    insurance_path = Column(String, nullable=True)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    rating = Column(Float, default=0.0)
    total_orders = Column(Integer, default=0)
    total_distance = Column(Float, default=0.0)
    is_online = Column(Boolean, default=False)
    current_location_lat = Column(Float, nullable=True)
    current_location_lng = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="driver_profile")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True, nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.DRAFT, nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True)
    is_urgent = Column(Boolean, default=False)
    requirements = Column(JSON, nullable=True)  # {"loading_equipment": True, "temperature": "-18"}
    
    # Address information
    from_address = Column(String, nullable=False)
    from_lat = Column(Float, nullable=False)
    from_lng = Column(Float, nullable=False)
    to_address = Column(String, nullable=False)
    to_lat = Column(Float, nullable=False)
    to_lng = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=True)
    
    # Cargo details
    cargo_description = Column(String, nullable=False)
    cargo_weight = Column(Float, nullable=False)  # в тоннах
    cargo_volume = Column(Float, nullable=False)  # в м³
    cargo_type = Column(String, nullable=False)
    cargo_images = Column(JSON, nullable=True)  # Пути к изображениям груза
    
    # Price information
    desired_price = Column(Float, nullable=False)
    final_price = Column(Float, nullable=True)
    platform_fee = Column(Float, nullable=True)  # 5% комиссия
    order_amount = Column(Float, nullable=True)  # Сумма заказа (финальная цена - комиссия)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Dates
    pickup_date = Column(DateTime, nullable=True)
    delivery_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    client = relationship("User", foreign_keys=[client_id], back_populates="orders_as_client")
    driver = relationship("User", foreign_keys=[driver_id], back_populates="orders_as_driver")
    bids = relationship("Bid", back_populates="order", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="order", cascade="all, delete-orphan")
    location_updates = relationship("LocationUpdate", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False, cascade="all, delete-orphan")

class Bid(Base):
    __tablename__ = "bids"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    proposed_price = Column(Float, nullable=False)
    message = Column(String, nullable=True)
    status = Column(Enum(BidStatus), default=BidStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="bids")
    driver = relationship("User", back_populates="bids")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")

class LocationUpdate(Base):
    __tablename__ = "location_updates"
    
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    driver = relationship("User", back_populates="location_updates")
    order = relationship("Order", back_populates="location_updates")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, unique=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="RUB")
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_method = Column(String, nullable=True)
    payment_id = Column(String, nullable=True)  # ID платежа в платежной системе
    description = Column(String, nullable=True)
    # ИЗМЕНИТЬ НА:
    payment_metadata = Column(JSON, nullable=True)  # <-- ИСПРАВЛЕНО
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    order = relationship("Order", back_populates="payment")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    type = Column(String, nullable=False)  # order, payment, system, etc.
    data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")  # УБИРАЕМ `me` из этой строки