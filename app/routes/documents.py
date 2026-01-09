from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import os

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_admin
from ..database import get_db
from ..file_storage import file_storage

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)

@router.post("/upload/cargo/{order_id}")
async def upload_cargo_document(
    order_id: int,
    file: UploadFile = File(...),
    document_type: str = "photo",
    description: Optional[str] = None,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Загрузка документа на груз"""
    # Проверяем права доступа
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    has_access = False
    if current_user.role == models.UserRole.ADMIN:
        has_access = True
    elif current_user.role == models.UserRole.CLIENT and order.client_id == current_user.id:
        has_access = True
    elif current_user.role == models.UserRole.DRIVER and order.driver_id == current_user.id:
        has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Сохраняем файл
    try:
        file_path = await file_storage.save_file(file, f"cargo/{order_id}", current_user.id)
        
        # Создаем запись в БД
        document_data = schemas.CargoDocumentCreate(
            order_id=order_id,
            document_type=document_type,
            description=description
        )
        
        document = crud.create_cargo_document(db, document_data, current_user.id)
        
        # Аудит
        crud.create_audit_log(db, {
            "user_id": current_user.id,
            "action": "upload_cargo_document",
            "entity_type": "order",
            "entity_id": order_id,
            "new_values": {
                "document_type": document_type,
                "file_path": file_path
            }
        })
        
        return {
            "message": "Документ загружен",
            "document_id": document.id,
            "file_path": file_path
        }
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")

@router.get("/cargo/{order_id}", response_model=List[schemas.CargoDocumentResponse])
async def get_cargo_documents(
    order_id: int,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получение документов груза"""
    # Проверяем права доступа
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    has_access = False
    if current_user.role == models.UserRole.ADMIN:
        has_access = True
    elif current_user.role == models.UserRole.CLIENT and order.client_id == current_user.id:
        has_access = True
    elif current_user.role == models.UserRole.DRIVER and order.driver_id == current_user.id:
        has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    documents = crud.get_cargo_documents_by_order(db, order_id)
    return documents

@router.get("/driver/{driver_id}/verify")
async def get_driver_documents_for_verification(
    driver_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение документов водителя для верификации (только для админов)"""
    driver = crud.get_user_by_id(db, driver_id)
    if not driver or driver.role != models.UserRole.DRIVER:
        raise HTTPException(status_code=404, detail="Водитель не найден")
    
    profile = crud.get_driver_profile(db, driver_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль водителя не найден")
    
    # Собираем документы из профиля
    documents = []
    
    if profile.license_path:
        documents.append({
            "type": "driver_license",
            "path": profile.license_path,
            "description": "Водительское удостоверение"
        })
    
    if profile.passport_path:
        documents.append({
            "type": "passport",
            "path": profile.passport_path,
            "description": "Паспорт"
        })
    
    if profile.vehicle_registration_path:
        documents.append({
            "type": "vehicle_registration",
            "path": profile.vehicle_registration_path,
            "description": "Свидетельство о регистрации ТС"
        })
    
    if profile.insurance_path:
        documents.append({
            "type": "insurance",
            "path": profile.insurance_path,
            "description": "Страховой полис"
        })
    
    return {
        "driver_id": driver_id,
        "full_name": driver.full_name,
        "verification_status": profile.verification_status.value,
        "documents": documents,
        "profile_data": {
            "vehicle_type": profile.vehicle_type,
            "vehicle_number": profile.vehicle_number,
            "carrying_capacity": profile.carrying_capacity,
            "volume": profile.volume
        }
    }