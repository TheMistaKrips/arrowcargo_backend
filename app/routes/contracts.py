from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_admin
from ..database import get_db
from ..file_storage import file_storage

router = APIRouter(prefix="/api/contracts", tags=["contracts"])
logger = logging.getLogger(__name__)

@router.post("/generate/{order_id}", response_model=schemas.ContractResponse)
async def generate_contract(
    order_id: int,
    template_type: str = "transport",
    background_tasks: BackgroundTasks = None,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Генерация договора для заказа"""
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
    
    # Проверяем, нет ли уже договора
    existing_contract = crud.get_contract_by_order(db, order_id)
    if existing_contract:
        raise HTTPException(status_code=400, detail="Договор уже существует")
    
    # Получаем шаблон
    templates = crud.get_contract_templates(db, template_type=template_type)
    if not templates:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    template = templates[0]
    
    # Создаем договор
    contract_data = schemas.ContractCreate(
        order_id=order_id,
        template_id=template.id
    )
    
    contract = crud.create_contract(db, contract_data)
    
    # Генерируем PDF в фоне
    if background_tasks:
        background_tasks.add_task(
            generate_contract_pdf_task,
            db,
            contract.id,
            template.id,
            order.id
        )
    
    return contract

@router.get("/{contract_id}", response_model=schemas.ContractResponse)
async def get_contract(
    contract_id: int,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получение договора"""
    contract = crud.get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Договор не найден")
    
    # Проверка прав доступа
    order = crud.get_order(db, contract.order_id)
    has_access = False
    
    if current_user.role == models.UserRole.ADMIN:
        has_access = True
    elif order:
        if current_user.role == models.UserRole.CLIENT and order.client_id == current_user.id:
            has_access = True
        elif current_user.role == models.UserRole.DRIVER and order.driver_id == current_user.id:
            has_access = True
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    return contract

@router.post("/{contract_id}/sign")
async def sign_contract(
    contract_id: int,
    signature_data: dict,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Подписание договора"""
    contract = crud.get_contract(db, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Договор не найден")
    
    order = crud.get_order(db, contract.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем, кто подписывает
    if current_user.role == models.UserRole.CLIENT and order.client_id == current_user.id:
        signature_data["signed_by"] = "client"
        signature_data["user_id"] = current_user.id
    elif current_user.role == models.UserRole.DRIVER and order.driver_id == current_user.id:
        signature_data["signed_by"] = "driver"
        signature_data["user_id"] = current_user.id
    elif current_user.role == models.UserRole.ADMIN:
        signature_data["signed_by"] = "platform"
        signature_data["user_id"] = current_user.id
    else:
        raise HTTPException(status_code=403, detail="Нет прав на подписание")
    
    # Обновляем статус
    updated_contract = crud.update_contract_status(
        db, contract_id, "signed", signature_data
    )
    
    if not updated_contract:
        raise HTTPException(status_code=500, detail="Ошибка при подписании")
    
    return {"message": "Договор подписан", "contract": updated_contract}

@router.get("/templates/", response_model=List[schemas.ContractTemplateResponse])
async def get_contract_templates(
    template_type: Optional[str] = None,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение шаблонов договоров (только для админов)"""
    templates = crud.get_contract_templates(db, template_type)
    return templates

@router.post("/templates/", response_model=schemas.ContractTemplateResponse)
async def create_contract_template(
    template: schemas.ContractTemplateCreate,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Создание шаблона договора (только для админов)"""
    created_template = crud.create_contract_template(db, template)
    return created_template

# Вспомогательные функции
async def generate_contract_pdf_task(db: Session, contract_id: int, 
                                    template_id: int, order_id: int):
    """Фоновая задача генерации PDF"""
    try:
        # Получаем данные для шаблона
        order = crud.get_order(db, order_id)
        contract = crud.get_contract(db, contract_id)
        
        if not order or not contract:
            return
        
        # Собираем переменные для шаблона
        template_variables = {
            "order_number": order.order_number,
            "order_id": order.id,
            "contract_id": contract.id,
            "created_at": order.created_at.strftime("%d.%m.%Y"),
            "client_name": order.client.full_name if order.client else "",
            "client_phone": order.client.phone if order.client else "",
            "driver_name": order.driver.full_name if order.driver else "",
            "driver_phone": order.driver.phone if order.driver else "",
            "from_address": order.from_address,
            "to_address": order.to_address,
            "cargo_description": order.cargo_description,
            "cargo_weight": order.cargo_weight,
            "final_price": order.final_price or order.desired_price,
            "distance": order.distance_km
        }
        
        # Генерируем PDF
        pdf_path = crud.generate_contract_pdf(db, contract_id, template_variables)
        
        # Обновляем путь в договоре
        contract.pdf_path = pdf_path
        db.commit()
        
    except Exception as e:
        logger.error(f"Error generating contract PDF: {e}")