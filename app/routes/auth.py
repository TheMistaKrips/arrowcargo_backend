"""
Роутер для аутентификации
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import logging

from .. import schemas, crud
from ..auth import (
    authenticate_user, create_access_token, create_refresh_token,
    verify_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_password_hash
)
from ..database import get_db
from ..notifications import notification_service

router = APIRouter(prefix="/api/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

@router.post("/register", response_model=schemas.UserResponse)
async def register(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Регистрация нового пользователя
    """
    # Проверка существования пользователя
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован"
        )
    
    # Проверка номера телефона
    db_user_by_phone = db.query(crud.models.User).filter(
        crud.models.User.phone == user.phone
    ).first()
    
    if db_user_by_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Номер телефона уже зарегистрирован"
        )
    
    try:
        # Создание пользователя
        created_user = crud.create_user(db=db, user=user)
        
        # Если это водитель, отправляем уведомление администраторам
        if user.role == schemas.UserRole.DRIVER:
            background_tasks.add_task(
                notify_admins_about_new_driver,
                db,
                created_user.id
            )
        
        logger.info(f"User registered: {created_user.email}, role: {created_user.role}")
        
        return created_user
        
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка регистрации: {str(e)}"
        )

@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Вход в систему
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь неактивен"
        )
    
    # Создание токенов
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email, "role": user.role.value},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"user_id": user.id, "email": user.email, "role": user.role.value}
    )
    
    logger.info(f"User logged in: {user.email}, role: {user.role}")
    
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=schemas.UserResponse.model_validate(user)
    )

@router.post("/refresh", response_model=schemas.Token)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    Обновление access токена с помощью refresh токена
    """
    payload = verify_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный refresh токен"
        )
    
    token_type = payload.get("type")
    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный тип токена"
        )
    
    user_id = payload.get("user_id")
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь неактивен"
        )
    
    # Создание новых токенов
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email, "role": user.role.value},
        expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(
        data={"user_id": user.id, "email": user.email, "role": user.role.value}
    )
    
    logger.info(f"Token refreshed for user: {user.email}")
    
    return schemas.Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=schemas.UserResponse.model_validate(user)
    )

@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Получение информации о текущем пользователе
    """
    return current_user

@router.post("/change-password")
async def change_password(
    password_data: schemas.UserUpdate,
    current_user: schemas.UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Смена пароля
    """
    if not password_data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль не указан"
        )
    
    # Обновляем пароль
    hashed_password = get_password_hash(password_data.password)
    current_user.hashed_password = hashed_password
    db.commit()
    
    logger.info(f"Password changed for user: {current_user.email}")
    
    return {"message": "Пароль успешно изменен"}

@router.post("/reset-password-request")
async def reset_password_request(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Запрос на сброс пароля
    """
    user = crud.get_user_by_email(db, email)
    if not user:
        # Для безопасности не раскрываем, существует ли пользователь
        return {"message": "Если пользователь с таким email существует, инструкции отправлены на почту"}
    
    # Генерируем токен сброса пароля
    reset_token = create_access_token(
        data={"user_id": user.id, "purpose": "password_reset"},
        expires_delta=timedelta(hours=1)
    )
    
    # В реальном приложении здесь отправка email
    # background_tasks.add_task(send_password_reset_email, user.email, reset_token)
    
    logger.info(f"Password reset requested for user: {user.email}")
    
    return {"message": "Если пользователь с таким email существует, инструкции отправлены на почту"}

@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """
    Сброс пароля с использованием токена
    """
    payload = verify_token(token)
    if not payload or payload.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или просроченный токен"
        )
    
    user_id = payload.get("user_id")
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Обновляем пароль
    hashed_password = get_password_hash(new_password)
    user.hashed_password = hashed_password
    db.commit()
    
    logger.info(f"Password reset for user: {user.email}")
    
    return {"message": "Пароль успешно изменен"}

# Вспомогательные функции
async def notify_admins_about_new_driver(db: Session, driver_id: int):
    """
    Уведомление администраторов о новом водителе
    """
    try:
        admins = crud.get_users(db, role="admin", is_active=True)
        for admin in admins:
            await notification_service.send_notification(
                db,
                admin.id,
                "new_driver_registered",
                {"driver_id": driver_id}
            )
    except Exception as e:
        logger.error(f"Error notifying admins about new driver: {e}")