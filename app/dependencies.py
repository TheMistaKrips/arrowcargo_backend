"""
Зависимости для Dependency Injection
"""
from fastapi import Depends, HTTPException, status, Query, Header
from sqlalchemy.orm import Session
from typing import Optional
import jwt
from .config import settings
from .database import get_db
from .auth import get_current_user, get_current_admin, get_current_driver, get_current_client
from . import crud

# Зависимости для WebSocket аутентификации
async def get_websocket_user(
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Получение пользователя для WebSocket соединения"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is required"
        )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user = crud.get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return user
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_websocket_driver(
    user = Depends(get_websocket_user)
):
    """Получение водителя для WebSocket соединения"""
    if user.role != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint"
        )
    return user

async def get_websocket_admin(
    user = Depends(get_websocket_user)
):
    """Получение администратора для WebSocket соединения"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint"
        )
    return user

# Зависимости для проверки разрешений
async def check_order_access(
    order_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Проверка доступа к заказу"""
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Администраторы имеют доступ ко всему
    if current_user.role == "admin":
        return order
    
    # Клиенты имеют доступ к своим заказам
    if current_user.role == "client" and order.client_id == current_user.id:
        return order
    
    # Водители имеют доступ к назначенным заказам
    if current_user.role == "driver" and order.driver_id == current_user.id:
        return order
    
    # Водители также имеют доступ к заказам, на которые они сделали ставки
    if current_user.role == "driver":
        bid = db.query(crud.models.Bid).filter(
            crud.models.Bid.order_id == order_id,
            crud.models.Bid.driver_id == current_user.id
        ).first()
        if bid:
            return order
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this order"
    )

async def check_driver_verified(
    current_user = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """Проверка верификации водителя"""
    profile = crud.get_driver_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver profile not found"
        )
    
    if profile.verification_status != "verified":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver profile is not verified"
        )
    
    return current_user

# Зависимости для пагинации
class PaginationParams:
    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Количество пропущенных записей"),
        limit: int = Query(100, ge=1, le=1000, description="Количество записей"),
        sort_by: str = Query("created_at", description="Поле для сортировки"),
        sort_desc: bool = Query(True, description="Сортировка по убыванию")
    ):
        self.skip = skip
        self.limit = limit
        self.sort_by = sort_by
        self.sort_desc = sort_desc

# Зависимости для фильтрации заказов
class OrderFilterParams:
    def __init__(
        self,
        status: Optional[str] = Query(None, description="Статус заказа"),
        min_price: Optional[float] = Query(None, ge=0, description="Минимальная цена"),
        max_price: Optional[float] = Query(None, ge=0, description="Максимальная цена"),
        cargo_type: Optional[str] = Query(None, description="Тип груза"),
        date_from: Optional[str] = Query(None, description="Дата от (YYYY-MM-DD)"),
        date_to: Optional[str] = Query(None, description="Дата до (YYYY-MM-DD)")
    ):
        self.status = status
        self.min_price = min_price
        self.max_price = max_price
        self.cargo_type = cargo_type
        self.date_from = date_from
        self.date_to = date_to

# Зависимости для API ключей (для интеграции)
async def verify_api_key(
    x_api_key: Optional[str] = Header(None)
):
    """Проверка API ключа для интеграций"""
    # В реальном приложении ключи должны храниться в базе данных
    valid_keys = {
        "mobile_app_key": "mobile-app-integration",
        "admin_panel_key": "admin-panel-integration",
        "website_key": "website-integration"
    }
    
    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return valid_keys[x_api_key]

# Зависимость для rate limiting (упрощенная версия)
class RateLimiter:
    def __init__(self):
        # В реальном приложении использовать Redis
        self.requests = {}
    
    async def __call__(self, user_id: int = Depends(get_current_user)):
        import time
        current_time = time.time()
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # Удаляем старые запросы (старше 1 минуты)
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if current_time - req_time < 60
        ]
        
        # Проверяем лимит (60 запросов в минуту)
        if len(self.requests[user_id]) >= 60:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests"
            )
        
        self.requests[user_id].append(current_time)
        return user_id

# Создаем экземпляр rate limiter
rate_limiter = RateLimiter()