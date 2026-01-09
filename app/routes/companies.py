from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_admin
from ..database import get_db
from ..dependencies import PaginationParams

router = APIRouter(prefix="/api/companies", tags=["companies"])
logger = logging.getLogger(__name__)

@router.post("/register", response_model=schemas.CompanyResponse)
async def register_company(
    company: schemas.CompanyCreate,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Регистрация компании (для юр. лиц)"""
    # Проверяем, что пользователь еще не зарегистрировал компанию
    existing_company = crud.get_company_by_user(db, current_user.id)
    if existing_company:
        raise HTTPException(status_code=400, detail="Компания уже зарегистрирована")
    
    # Проверяем, что ИНН не используется
    existing_inn = db.query(models.Company).filter(
        models.Company.inn == company.inn
    ).first()
    
    if existing_inn:
        raise HTTPException(status_code=400, detail="Компания с таким ИНН уже зарегистрирована")
    
    # Создаем компанию
    created_company = crud.create_company(db, company, current_user.id)
    
    # Аудит
    crud.create_audit_log(db, {
        "user_id": current_user.id,
        "action": "register_company",
        "entity_type": "company",
        "entity_id": created_company.id,
        "new_values": {
            "name": company.name,
            "inn": company.inn
        }
    })
    
    return created_company

@router.get("/my", response_model=schemas.CompanyResponse)
async def get_my_company(
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получение моей компании"""
    company = crud.get_company_by_user(db, current_user.id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    
    return company

@router.get("/", response_model=List[schemas.CompanyResponse])
async def get_companies(
    pagination: PaginationParams = Depends(),
    verification_status: Optional[str] = None,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение списка компаний (только для админов)"""
    companies = crud.get_companies(
        db,
        skip=pagination.skip,
        limit=pagination.limit,
        verification_status=verification_status
    )
    return companies

@router.post("/{company_id}/verify")
async def verify_company(
    company_id: int,
    status: str,
    notes: Optional[str] = None,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Верификация компании (только для админов)"""
    company = crud.get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    
    updated_company = crud.verify_company(db, company_id, status, notes)
    
    if not updated_company:
        raise HTTPException(status_code=500, detail="Ошибка верификации")
    
    return {"message": "Статус компании обновлен", "company": updated_company}