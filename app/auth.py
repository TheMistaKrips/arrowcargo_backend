"""
Аутентификация и авторизация - РАБОЧАЯ ВЕРСИЯ
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import secrets
import hashlib

from . import models, schemas
from .database import get_db
from .config import settings

# Схема OAuth2 для получения токена
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False
)

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля - SHA256"""
    try:
        test_hash = hashlib.sha256(plain_password.encode()).hexdigest()
        return test_hash == hashed_password
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Хеширование пароля - SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Получение пользователя по email"""
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """Получение пользователя по ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()

def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    """Аутентификация пользователя"""
    print(f"🔐 Authenticating user: {email}")
    user = get_user_by_email(db, email)
    if not user:
        print(f"❌ User not found: {email}")
        return None
    
    if not verify_password(password, user.hashed_password):
        print(f"❌ Wrong password for: {email}")
        return None
    
    print(f"✅ User authenticated: {email}, role: {user.role}")
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание access токена"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access",
        "jti": secrets.token_urlsafe(32)
    })
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание refresh токена"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_urlsafe(32)
    })
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    """Проверка токена"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
) -> models.User:
    """Получение текущего пользователя из токена"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("user_id")
    token_type: str = payload.get("type")
    
    if user_id is None or token_type != "access":
        raise credentials_exception
    
    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    
    return user

async def get_current_active_user(
    current_user: Annotated[schemas.UserResponse, Depends(get_current_user)]
) -> schemas.UserResponse:
    """Проверка активности пользователя"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    return current_user

def check_user_role(user: models.User, allowed_roles: list) -> bool:
    """Проверка роли пользователя"""
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not allowed for {user.role} role"
        )
    return True

# Специальные зависимости для разных ролей
async def get_current_admin(
    current_user: Annotated[models.User, Depends(get_current_user)]
) -> models.User:
    """Только администраторы"""
    check_user_role(current_user, [models.UserRole.ADMIN])
    return current_user

async def get_current_driver(
    current_user: Annotated[models.User, Depends(get_current_user)]
) -> models.User:
    """Только водители"""
    check_user_role(current_user, [models.UserRole.DRIVER])
    return current_user

async def get_current_client(
    current_user: Annotated[models.User, Depends(get_current_user)]
) -> models.User:
    """Только клиенты"""
    check_user_role(current_user, [models.UserRole.CLIENT])
    return current_user

async def get_current_client_or_admin(
    current_user: Annotated[models.User, Depends(get_current_user)]
) -> models.User:
    """Клиенты или администраторы"""
    check_user_role(current_user, [models.UserRole.CLIENT, models.UserRole.ADMIN])
    return current_user

async def get_current_driver_or_admin(
    current_user: Annotated[models.User, Depends(get_current_user)]
) -> models.User:
    """Водители или администраторы"""
    check_user_role(current_user, [models.UserRole.DRIVER, models.UserRole.ADMIN])
    return current_user