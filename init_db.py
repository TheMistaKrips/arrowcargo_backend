# init_db.py
"""
Инициализация базы данных с правильной кодировкой
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
import sqlalchemy
import traceback

print("Инициализация базы данных...")

try:
    # Создаем таблицы с указанием кодировки
    Base.metadata.create_all(bind=engine)
    print("База данных успешно инициализирована!")
    
    # Проверяем соединение
    with engine.connect() as conn:
        result = conn.execute("SELECT 1").scalar()
        print(f"Проверка соединения: {result}")
        
except Exception as e:
    print(f"Ошибка: {e}")
    traceback.print_exc()
    
    # Пробуем альтернативный подход
    print("\nПробуем альтернативный подход...")
    try:
        # Создаем движок с явной кодировкой
        from sqlalchemy import create_engine
        from app.config import settings
        
        new_engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=True
        )
        
        Base.metadata.create_all(bind=new_engine)
        print("База данных создана с альтернативным движком!")
        
    except Exception as e2:
        print(f"Альтернативный подход также не сработал: {e2}")