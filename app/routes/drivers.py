"""
Роутер для работы с водителями
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_driver, get_current_admin, get_current_driver_or_admin
from ..database import get_db
from ..dependencies import PaginationParams
from ..file_storage import file_storage
from ..notifications import notification_service

router = APIRouter(prefix="/api/drivers", tags=["drivers"])
logger = logging.getLogger(__name__)

@router.post("/profile", response_model=schemas.DriverProfileResponse)
async def create_driver_profile(
    profile: schemas.DriverProfileCreate,
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Создание профиля водителя
    """
    # Проверка существования профиля
    existing_profile = crud.get_driver_profile(db, current_user.id)
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Профиль уже существует"
        )
    
    # Создание профиля
    created_profile = crud.create_driver_profile(db, profile, current_user.id)
    
    # Отправляем уведомление администраторам
    admins = crud.get_users(db, role="admin", is_active=True)
    for admin in admins:
        await notification_service.send_notification(
            db,
            admin.id,
            "verification_required",
            {"driver_id": current_user.id, "driver_name": current_user.full_name}
        )
    
    logger.info(f"Driver profile created for user: {current_user.email}")
    
    return created_profile

@router.get("/profile", response_model=schemas.DriverProfileResponse)
async def get_my_driver_profile(
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Получение профиля текущего водителя
    """
    profile = crud.get_driver_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль не найден"
        )
    
    return profile

@router.put("/profile", response_model=schemas.DriverProfileResponse)
async def update_driver_profile(
    profile_update: schemas.DriverProfileUpdate,
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Обновление профиля водителя
    """
    profile = crud.update_driver_profile(db, current_user.id, profile_update)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль не найден"
        )
    
    logger.info(f"Driver profile updated for user: {current_user.email}")
    
    return profile

@router.post("/profile/online")
async def set_driver_online(
    lat: float = Query(..., ge=-90, le=90, description="Широта"),
    lng: float = Query(..., ge=-180, le=180, description="Долгота"),
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Установка статуса "онлайн" для водителя
    """
    profile = crud.update_driver_location(db, current_user.id, lat, lng)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль не найден"
        )
    
    profile.is_online = True
    db.commit()
    db.refresh(profile)
    
    logger.info(f"Driver set online: {current_user.email} at ({lat}, {lng})")
    
    return {"message": "Водитель в сети", "location": {"lat": lat, "lng": lng}}

@router.post("/profile/offline")
async def set_driver_offline(
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Установка статуса "офлайн" для водителя
    """
    profile = crud.get_driver_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль не найден"
        )
    
    profile.is_online = False
    db.commit()
    db.refresh(profile)
    
    logger.info(f"Driver set offline: {current_user.email}")
    
    return {"message": "Водитель не в сети"}

@router.get("/nearby")
async def get_nearby_drivers(
    lat: float = Query(..., ge=-90, le=90, description="Широта"),
    lng: float = Query(..., ge=-180, le=180, description="Долгота"),
    radius_km: float = Query(50, ge=1, le=500, description="Радиус поиска в км"),
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Поиск водителей поблизости (упрощенная версия)
    """
    # В реальном приложении здесь должен быть поиск по геолокации
    # Для упрощения возвращаем онлайн водителей
    
    drivers = crud.get_driver_profiles(db, is_online=True, limit=20)
    
    # Фильтруем по расстоянию (упрощенно)
    nearby_drivers = []
    for driver in drivers:
        if driver.current_location_lat and driver.current_location_lng:
            distance = crud.utils.calculate_distance(
                lat, lng,
                driver.current_location_lat, driver.current_location_lng
            )
            if distance <= radius_km:
                nearby_drivers.append({
                    "driver": schemas.DriverProfileResponse.model_validate(driver),
                    "distance_km": round(distance, 2),
                    "user": schemas.UserResponse.model_validate(driver.user)
                })
    
    return {"drivers": nearby_drivers, "count": len(nearby_drivers)}

@router.get("/", response_model=List[schemas.DriverWithProfile])
async def get_drivers(
    pagination: PaginationParams = Depends(),
    verification_status: Optional[str] = Query(None, description="Статус верификации"),
    is_online: Optional[bool] = Query(None, description="Статус онлайн"),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Получение списка водителей (только для администраторов)
    """
    profiles = crud.get_driver_profiles(
        db,
        skip=pagination.skip,
        limit=pagination.limit,
        verification_status=verification_status,
        is_online=is_online
    )
    
    # Формируем ответ с информацией о пользователе
    result = []
    for profile in profiles:
        result.append({
            "user": schemas.UserResponse.model_validate(profile.user),
            "profile": schemas.DriverProfileResponse.model_validate(profile)
        })
    
    return result

@router.get("/{driver_id}/profile", response_model=schemas.DriverWithProfile)
async def get_driver_profile_by_id(
    driver_id: int,
    current_user: schemas.UserResponse = Depends(get_current_driver_or_admin),
    db: Session = Depends(get_db)
):
    """
    Получение профиля водителя по ID
    """
    # Проверка прав доступа
    if current_user.role == "driver" and current_user.id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен"
        )
    
    profile = crud.get_driver_profile(db, driver_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль не найден"
        )
    
    return {
        "user": schemas.UserResponse.model_validate(profile.user),
        "profile": schemas.DriverProfileResponse.model_validate(profile)
    }

@router.post("/upload-document")
async def upload_document(
    document_type: str = Query(..., description="Тип документа: license, passport, vehicle_registration, insurance"),
    file: UploadFile = File(...),
    current_user: schemas.UserResponse = Depends(get_current_driver),
    db: Session = Depends(get_db)
):
    """
    Загрузка документа водителя
    """
    # Проверка типа документа
    allowed_types = ["license", "passport", "vehicle_registration", "insurance"]
    if document_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый тип документа. Допустимые: {', '.join(allowed_types)}"
        )
    
    # Сохранение файла
    try:
        file_path = await file_storage.save_driver_document(file, current_user.id, document_type)
        
        # Обновление профиля водителя
        profile = crud.get_driver_profile(db, current_user.id)
        if profile:
            if document_type == "license":
                profile.license_path = file_path
            elif document_type == "passport":
                profile.passport_path = file_path
            elif document_type == "vehicle_registration":
                profile.vehicle_registration_path = file_path
            elif document_type == "insurance":
                profile.insurance_path = file_path
            
            db.commit()
        
        logger.info(f"Document uploaded: {document_type} for user: {current_user.email}")
        
        return {
            "message": "Документ успешно загружен",
            "document_type": document_type,
            "file_path": file_path,
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке документа: {str(e)}"
        )

@router.get("/stats/{driver_id}")
async def get_driver_stats(
    driver_id: int,
    current_user: schemas.UserResponse = Depends(get_current_driver_or_admin),
    db: Session = Depends(get_db)
):
    """
    Получение статистики водителя
    """
    # Проверка прав доступа
    if current_user.role == "driver" and current_user.id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен"
        )
    
    profile = crud.get_driver_profile(db, driver_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль не найден"
        )
    
    # Получаем заказы водителя
    orders = crud.get_orders(db, driver_id=driver_id)
    
    # Рассчитываем статистику
    completed_orders = [o for o in orders if o.status == models.OrderStatus.COMPLETED]
    cancelled_orders = [o for o in orders if o.status == models.OrderStatus.CANCELLED]
    active_orders = [o for o in orders if o.status in [
        models.OrderStatus.DRIVER_ASSIGNED,
        models.OrderStatus.LOADING,
        models.OrderStatus.EN_ROUTE,
        models.OrderStatus.UNLOADING
    ]]
    
    total_earnings = sum(o.order_amount or 0 for o in completed_orders)
    avg_rating = profile.rating
    acceptance_rate = len(completed_orders) / max(len(orders), 1) * 100
    
    stats = {
        "total_orders": len(orders),
        "completed_orders": len(completed_orders),
        "cancelled_orders": len(cancelled_orders),
        "active_orders": len(active_orders),
        "total_earnings": total_earnings,
        "average_rating": avg_rating,
        "acceptance_rate": round(acceptance_rate, 2),
        "total_distance": profile.total_distance,
        "verification_status": profile.verification_status.value
    }
    
    return stats

@router.post("/search")
async def search_drivers(
    query: str = Query(..., description="Поисковый запрос (имя, email, телефон, номер машины)"),
    pagination: PaginationParams = Depends(),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Поиск водителей (только для администраторов)
    """
    profiles = db.query(crud.models.DriverProfile).join(crud.models.User).filter(
        (crud.models.User.email.ilike(f"%{query}%")) |
        (crud.models.User.phone.ilike(f"%{query}%")) |
        (crud.models.User.full_name.ilike(f"%{query}%")) |
        (crud.models.DriverProfile.vehicle_number.ilike(f"%{query}%")) |
        (crud.models.DriverProfile.vehicle_model.ilike(f"%{query}%"))
    ).order_by(crud.models.DriverProfile.created_at.desc())\
     .offset(pagination.skip)\
     .limit(pagination.limit)\
     .all()
    
    result = []
    for profile in profiles:
        result.append({
            "user": schemas.UserResponse.model_validate(profile.user),
            "profile": schemas.DriverProfileResponse.model_validate(profile)
        })
    
    return result