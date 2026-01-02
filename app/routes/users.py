"""
Роутер для работы с пользователями
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import schemas, crud
from ..auth import get_current_active_user, get_current_admin
from ..database import get_db
from ..dependencies import PaginationParams

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/me", response_model=schemas.UserResponse)
async def read_users_me(
    current_user: schemas.UserResponse = Depends(get_current_active_user)
):
    """
    Получение информации о текущем пользователе
    """
    return current_user

@router.put("/me", response_model=schemas.UserResponse)
async def update_user_me(
    user_update: schemas.UserUpdate,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Обновление информации текущего пользователя
    """
    updated_user = crud.update_user(db, current_user.id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return updated_user

@router.get("/", response_model=List[schemas.UserResponse])
async def get_users(
    pagination: PaginationParams = Depends(),
    role: Optional[str] = Query(None, description="Фильтр по роли"),
    is_active: Optional[bool] = Query(None, description="Фильтр по активности"),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение списка пользователей (только для администраторов)
    """
    users = crud.get_users(
        db,
        skip=pagination.skip,
        limit=pagination.limit,
        role=role,
        is_active=is_active
    )
    return users

@router.get("/{user_id}", response_model=schemas.UserResponse)
async def get_user_by_id(
    user_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение информации о пользователе по ID (только для администраторов)
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return user

@router.put("/{user_id}", response_model=schemas.UserResponse)
async def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Обновление информации пользователя (только для администраторов)
    """
    updated_user = crud.update_user(db, user_id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return updated_user

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Удаление пользователя (только для администраторов)
    """
    success = crud.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return {"message": "Пользователь удален"}

@router.post("/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Активация пользователя (только для администраторов)
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    user.is_active = True
    db.commit()
    db.refresh(user)
    
    return {"message": "Пользователь активирован"}

@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Деактивация пользователя (только для администраторов)
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    user.is_active = False
    db.commit()
    db.refresh(user)
    
    return {"message": "Пользователь деактивирован"}

@router.get("/me/balance")
async def get_my_balance(
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Получение баланса текущего пользователя
    """
    user = crud.get_user_by_id(db, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return {"balance": user.balance}

@router.get("/search")
async def search_users(
    query: str = Query(..., description="Поисковый запрос (email, телефон, имя)"),
    pagination: PaginationParams = Depends(),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Поиск пользователей (только для администраторов)
    """
    users = db.query(crud.models.User).filter(
        (crud.models.User.email.ilike(f"%{query}%")) |
        (crud.models.User.phone.ilike(f"%{query}%")) |
        (crud.models.User.full_name.ilike(f"%{query}%"))
    ).order_by(crud.models.User.created_at.desc())\
     .offset(pagination.skip)\
     .limit(pagination.limit)\
     .all()
    
    return users