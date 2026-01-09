# create_migration.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models import (
    User, Order, DriverProfile, Bid, Message, LocationUpdate, 
    Payment, Notification, Company, Contract, ContractTemplate,
    CargoDocument, Review, SupportTicket, AuditLog
)

print("Создание таблиц для новых моделей...")

try:
    # Создаем таблицы
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы успешно созданы!")
    print("\nСозданные таблицы:")
    print("1. companies - Компании (юр. лица)")
    print("2. contracts - Договоры")
    print("3. contract_templates - Шаблоны договоров")
    print("4. cargo_documents - Документы на груз")
    print("5. reviews - Отзывы и рейтинги")
    print("6. support_tickets - Тикеты поддержки")
    print("7. audit_logs - Журнал аудита")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")