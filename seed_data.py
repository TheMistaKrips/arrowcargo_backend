#!/usr/bin/env python3
"""
Скрипт для заполнения базы данных тестовыми данными
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import Base
from app.seed import seed_database, clear_database

def main():
    """Основная функция"""
    print("🌱 Генератор тестовых данных для CargoPro")
    print("=" * 50)
    
    # Создаем таблицы если их нет
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы базы данных созданы")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        return
    
    # Создаем сессию базы данных
    db = SessionLocal()
    
    try:
        # Очищаем базу данных (опционально)
        if len(sys.argv) > 1 and sys.argv[1] == "--clear":
            print("🧹 Очистка базы данных...")
            clear_database(db)
        
        # Заполняем базу данных тестовыми данными
        seed_database(db)
        
        print("=" * 50)
        print("🎉 Тестовые данные успешно созданы!")
        print("\n📋 Тестовые учетные записи:")
        print("-" * 40)
        print("👑 Администратор:")
        print("  Email: admin@cargopro.com")
        print("  Пароль: Admin123!")
        print()
        print("👥 Клиенты:")
        print("  1. Email: client1@example.com, Пароль: Client123!")
        print("  2. Email: client2@example.com, Пароль: Client123!")
        print("  3. Email: company@example.com, Пароль: Company123!")
        print()
        print("🚚 Водители:")
        print("  1. Email: driver1@example.com, Пароль: Driver123!")
        print("  2. Email: driver2@example.com, Пароль: Driver123!")
        print("  3. Email: driver3@example.com, Пароль: Driver123!")
        print("  4. Email: driver4@example.com, Пароль: Driver123!")
        print("-" * 40)
        print("\n🚀 Запустите сервер командой: python run.py")
        print("📚 Документация API: http://localhost:8000/api/docs")
        
    except Exception as e:
        print(f"❌ Ошибка при заполнении базы данных: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()