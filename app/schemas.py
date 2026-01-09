"""
Pydantic схемы для валидации данных
"""
import enum
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum
from decimal import Decimal

# Enums for schemas
class UserRole(str, Enum):
    CLIENT = "client"
    DRIVER = "driver"
    ADMIN = "admin"

class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class SupportTicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class SupportTicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SupportTicketCategory(str, enum.Enum):
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    DISPUTE = "dispute"
    OTHER = "other"

class DocumentType(str, enum.Enum):
    TTN = "ttn"
    INVOICE = "invoice"
    PACKING_LIST = "packing_list"
    PHOTO = "photo"
    OTHER = "other"

# Company schemas
class CompanyBase(BaseModel):
    name: str
    inn: str
    kpp: Optional[str] = None
    ogrn: str
    legal_address: str
    actual_address: Optional[str] = None
    bank_name: str
    bank_account: str
    corr_account: Optional[str] = None
    bic: str
    director_name: str
    director_position: str

class CompanyCreate(CompanyBase):
    documents: Optional[Dict[str, str]] = None

class CompanyResponse(CompanyBase):
    id: int
    user_id: int
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderStatus(str, Enum):
    DRAFT = "draft"
    SEARCHING = "searching"
    DRIVER_ASSIGNED = "driver_assigned"
    LOADING = "loading"
    EN_ROUTE = "en_route"
    UNLOADING = "unloading"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PAID = "paid"

class BidStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class ContractBase(BaseModel):
    order_id: int
    template_id: Optional[int] = None

class ContractCreate(ContractBase):
    pass

class ContractResponse(ContractBase):
    id: int
    pdf_path: Optional[str] = None
    signed_by_client_at: Optional[datetime] = None
    signed_by_driver_at: Optional[datetime] = None
    signed_by_platform_at: Optional[datetime] = None
    status: str
    metadata: Optional[Dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Contract Template schemas
class ContractTemplateBase(BaseModel):
    name: str
    template_type: str
    html_content: str
    variables: Optional[Dict] = None

class ContractTemplateCreate(ContractTemplateBase):
    pass

class ContractTemplateResponse(ContractTemplateBase):
    id: int
    is_active: bool
    version: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class CargoDocumentBase(BaseModel):
    order_id: int
    document_type: DocumentType
    description: Optional[str] = None

class CargoDocumentCreate(CargoDocumentBase):
    pass

class CargoDocumentResponse(CargoDocumentBase):
    id: int
    file_path: str
    uploaded_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Review schemas
class ReviewBase(BaseModel):
    order_id: int
    reviewed_id: int
    rating: float = Field(ge=1.0, le=5.0)
    comment: Optional[str] = None
    category_ratings: Optional[Dict[str, float]] = None

class ReviewCreate(ReviewBase):
    pass

class ReviewResponse(ReviewBase):
    id: int
    reviewer_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Support Ticket schemas
class SupportTicketBase(BaseModel):
    order_id: Optional[int] = None
    category: SupportTicketCategory
    priority: SupportTicketPriority = SupportTicketPriority.MEDIUM
    title: str
    description: str

class SupportTicketCreate(SupportTicketBase):
    pass

class SupportTicketResponse(SupportTicketBase):
    id: int
    user_id: int
    status: SupportTicketStatus
    assigned_to: Optional[int] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Audit Log schemas
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: int
    old_values: Optional[Dict] = None
    new_values: Optional[Dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    full_name: Optional[str] = None
    role: UserRole = UserRole.CLIENT

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 72:
            raise ValueError('Password cannot be longer than 72 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    phone: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    balance: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    company_id: Optional[int] = None
    default_payment_method: Optional[str] = None
    notification_settings: Dict = Field(default_factory=lambda: {
        "email": True,
        "push": True,
        "sms": False,
        "new_order": True,
        "order_updates": True,
        "promotions": False
    })
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None

# Driver schemas
class DriverProfileBase(BaseModel):
    vehicle_type: str
    vehicle_model: Optional[str] = None
    vehicle_number: str
    carrying_capacity: float = Field(..., gt=0)
    volume: float = Field(..., gt=0)

class DriverProfileCreate(DriverProfileBase):
    pass

class DriverProfileUpdate(BaseModel):
    vehicle_type: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_number: Optional[str] = None
    carrying_capacity: Optional[float] = None
    volume: Optional[float] = None
    is_online: Optional[bool] = None
    current_location_lat: Optional[float] = None
    current_location_lng: Optional[float] = None

class DriverProfileResponse(DriverProfileBase):
    id: int
    user_id: int
    verification_status: VerificationStatus
    rating: float
    total_orders: int
    total_distance: float
    is_online: bool
    current_location_lat: Optional[float] = None
    current_location_lng: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class DriverWithProfile(BaseModel):
    user: UserResponse
    profile: DriverProfileResponse
    model_config = ConfigDict(from_attributes=True)

# Order schemas
class OrderBase(BaseModel):
    from_address: str = Field(..., min_length=3)
    from_lat: float = Field(..., ge=-90, le=90)
    from_lng: float = Field(..., ge=-180, le=180)
    to_address: str = Field(..., min_length=3)
    to_lat: float = Field(..., ge=-90, le=90)
    to_lng: float = Field(..., ge=-180, le=180)
    cargo_description: str = Field(..., min_length=5)
    cargo_weight: float = Field(..., gt=0)
    cargo_volume: float = Field(..., gt=0)
    cargo_type: str = Field(..., min_length=2)
    desired_price: float = Field(..., gt=0)
    pickup_date: Optional[datetime] = None

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    driver_id: Optional[int] = None
    final_price: Optional[float] = None
    pickup_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None

class OrderResponse(OrderBase):
    id: int
    order_number: str
    client_id: int
    driver_id: Optional[int] = None
    status: OrderStatus
    distance_km: Optional[float] = None
    final_price: Optional[float] = None
    platform_fee: Optional[float] = None
    order_amount: Optional[float] = None
    payment_status: PaymentStatus
    delivery_date: Optional[datetime] = None
    contract_id: Optional[int] = None
    is_urgent: bool = False
    requirements: Optional[Dict] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class OrderWithRelations(OrderResponse):
    client: Optional[UserResponse] = None
    driver: Optional[UserResponse] = None
    bids: List['BidResponse'] = []
    model_config = ConfigDict(from_attributes=True)

# Bid schemas
class BidBase(BaseModel):
    proposed_price: float = Field(..., gt=0)
    message: Optional[str] = None

class BidCreate(BidBase):
    pass

class BidResponse(BidBase):
    id: int
    order_id: int
    driver_id: int
    status: BidStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    driver: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True)

# Message schemas
class MessageBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: int
    order_id: int
    sender_id: int
    is_read: bool
    timestamp: datetime
    sender: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True)

# Location schemas
class LocationBase(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None

class LocationCreate(LocationBase):
    order_id: Optional[int] = None

class LocationResponse(LocationBase):
    id: int
    driver_id: int
    order_id: Optional[int] = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# Payment schemas
class PaymentBase(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = "RUB"
    description: Optional[str] = None

class PaymentCreate(PaymentBase):
    order_id: int
    payment_method: str

class PaymentResponse(PaymentBase):
    id: int
    user_id: int
    order_id: Optional[int] = None
    status: PaymentStatus
    payment_method: Optional[str] = None
    payment_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# Notification schemas
class NotificationBase(BaseModel):
    title: str
    message: str
    type: str
    data: Optional[dict] = None

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Calculator schemas
class PriceCalculationRequest(BaseModel):
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    weight: float = Field(..., gt=0)
    volume: float = Field(..., gt=0)

class PriceCalculation(BaseModel):
    distance_km: float
    base_price: float
    weight_multiplier: float
    volume_multiplier: float
    suggested_price: float
    platform_fee: float
    driver_amount: float

# Admin schemas
class AdminStats(BaseModel):
    total_users: int
    total_drivers: int
    total_clients: int
    total_orders: int
    total_revenue: float
    pending_verifications: int
    active_orders: int

class VerificationRequest(BaseModel):
    driver_id: int
    status: VerificationStatus
    notes: Optional[str] = None

# Update forward references
OrderWithRelations.model_rebuild()
BidResponse.model_rebuild()