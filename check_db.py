# check_db.py
"""
Проверка базы данных
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.config import settings

print("Проверка базы данных...")
print(f"Database URL: {settings.DATABASE_URL}")

# Проверяем файл SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    print(f"SQLite файл: {db_path}")
    
    if os.path.exists(db_path):
        print(f"Файл БД существует, размер: {os.path.getsize(db_path)} байт")
    else:
        print("Файл БД не существует")

# Пытаемся создать таблицы
try:
    print("\nПопытка создать таблицы...")
    Base.metadata.create_all(bind=engine)
    print("Таблицы успешно созданы!")
except Exception as e:
    print(f"Ошибка при создании таблиц: {e}")
    print(f"Тип ошибки: {type(e)}")