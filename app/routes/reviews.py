from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from .. import schemas, crud, models
from ..auth import get_current_active_user
from ..database import get_db

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
logger = logging.getLogger(__name__)

@router.post("/{order_id}", response_model=schemas.ReviewResponse)
async def create_review(
    order_id: int,
    review: schemas.ReviewCreate,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создание отзыва по завершенному заказу"""
    # Проверяем, что reviewed_id - другой участник заказа
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if order.status != models.OrderStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Можно оставить отзыв только по завершенному заказу")
    
    # Проверяем, что reviewed_id - другой участник
    if review.reviewed_id not in [order.client_id, order.driver_id]:
        raise HTTPException(status_code=400, detail="Можно оценить только участника заказа")
    
    if review.reviewed_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя оценить себя")
    
    # Проверяем, что текущий пользователь - участник заказа
    if current_user.id not in [order.client_id, order.driver_id]:
        raise HTTPException(status_code=403, detail="Только участники заказа могут оставлять отзывы")
    
    # Проверяем, что отзыв еще не оставлен
    existing_review = db.query(models.Review).filter(
        models.Review.order_id == order_id,
        models.Review.reviewer_id == current_user.id
    ).first()
    
    if existing_review:
        raise HTTPException(status_code=400, detail="Вы уже оставили отзыв по этому заказу")
    
    # Создаем отзыв
    try:
        created_review = crud.create_review(db, review, current_user.id)
        
        # Аудит
        crud.create_audit_log(db, {
            "user_id": current_user.id,
            "action": "create_review",
            "entity_type": "order",
            "entity_id": order_id,
            "new_values": {
                "reviewed_id": review.reviewed_id,
                "rating": review.rating
            }
        })
        
        return created_review
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/driver/{driver_id}", response_model=List[schemas.ReviewResponse])
async def get_driver_reviews(
    driver_id: int,
    db: Session = Depends(get_db)
):
    """Получение отзывов о водителе (публичный доступ)"""
    driver = crud.get_user_by_id(db, driver_id)
    if not driver or driver.role != models.UserRole.DRIVER:
        raise HTTPException(status_code=404, detail="Водитель не найден")
    
    reviews = crud.get_reviews_by_user(db, driver_id)
    return reviews

@router.get("/client/{client_id}", response_model=List[schemas.ReviewResponse])
async def get_client_reviews(
    client_id: int,
    db: Session = Depends(get_db)
):
    """Получение отзывов о клиенте (публичный доступ)"""
    client = crud.get_user_by_id(db, client_id)
    if not client or client.role != models.UserRole.CLIENT:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    
    reviews = crud.get_reviews_by_user(db, client_id)
    return reviews