from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .. import schemas, crud, models
from ..auth import get_current_active_user, get_current_admin
from ..database import get_db
from ..dependencies import PaginationParams

router = APIRouter(prefix="/api/support", tags=["support"])
logger = logging.getLogger(__name__)

@router.post("/tickets/", response_model=schemas.SupportTicketResponse)
async def create_support_ticket(
    ticket: schemas.SupportTicketCreate,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создание тикета поддержки"""
    created_ticket = crud.create_support_ticket(db, ticket, current_user.id)
    
    # Аудит
    crud.create_audit_log(db, {
        "user_id": current_user.id,
        "action": "create_support_ticket",
        "entity_type": "support_ticket",
        "entity_id": created_ticket.id,
        "new_values": {
            "title": ticket.title,
            "category": ticket.category,
            "priority": ticket.priority
        }
    })
    
    # TODO: Отправить уведомление админам
    
    return created_ticket

@router.get("/tickets/my", response_model=List[schemas.SupportTicketResponse])
async def get_my_tickets(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(None),
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получение моих тикетов"""
    tickets = crud.get_support_tickets(
        db,
        skip=pagination.skip,
        limit=pagination.limit,
        status=status
    )
    
    # Фильтруем только свои тикеты
    my_tickets = [t for t in tickets if t.user_id == current_user.id]
    return my_tickets

@router.get("/tickets/admin", response_model=List[schemas.SupportTicketResponse])
async def get_admin_tickets(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Получение тикетов для админа (только для админов)"""
    tickets = crud.get_support_tickets(
        db,
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
        priority=priority,
        assigned_to=assigned_to
    )
    return tickets

@router.get("/tickets/{ticket_id}", response_model=schemas.SupportTicketResponse)
async def get_ticket(
    ticket_id: int,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получение тикета по ID"""
    ticket = crud.get_support_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    # Проверка прав доступа
    if current_user.role != models.UserRole.ADMIN and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    return ticket

@router.put("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    status: Optional[str] = None,
    resolution_notes: Optional[str] = None,
    assigned_to: Optional[int] = None,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Обновление тикета (только для админов)"""
    ticket = crud.get_support_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    updated_ticket = crud.update_ticket_status(
        db, ticket_id, status, resolution_notes, assigned_to
    )
    
    if not updated_ticket:
        raise HTTPException(status_code=500, detail="Ошибка обновления")
    
    # Аудит
    crud.create_audit_log(db, {
        "user_id": current_user.id,
        "action": "update_support_ticket",
        "entity_type": "support_ticket",
        "entity_id": ticket_id,
        "new_values": {
            "status": status,
            "assigned_to": assigned_to
        }
    })
    
    return {"message": "Тикет обновлен", "ticket": updated_ticket}

@router.post("/tickets/{ticket_id}/assign")
async def assign_ticket_to_me(
    ticket_id: int,
    current_user: schemas.UserResponse = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Назначение тикета себе (только для админов)"""
    ticket = crud.get_support_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    
    updated_ticket = crud.update_ticket_status(
        db, ticket_id, "in_progress", assigned_to=current_user.id
    )
    
    return {"message": "Тикет назначен вам", "ticket": updated_ticket}