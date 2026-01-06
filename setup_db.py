#!/usr/bin/env python3
"""
Создание базы данных с тестовыми данными - РАБОЧАЯ ВЕРСИЯ
"""
import sys
import os
import hashlib
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import Base
from app import models

def get_password_hash(password: str) -> str:
    """Хеширование пароля - SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_database():
    """Создание базы данных с тестовыми данными"""
    print("=" * 60)
    print("🚀 Создание базы данных CargoPro")
    print("=" * 60)
    
    # Удаляем старую базу если есть
    db_file = "./cargopro.db"
    if os.path.exists(db_file):
        print(f"🗑️  Удаление старой базы: {db_file}")
        os.remove(db_file)
    
    # Создаем таблицы
    print("📊 Создание таблиц...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы успешно")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        return
    
    # Создаем сессию
    db = SessionLocal()
    
    try:
        # 1. СОЗДАЕМ АДМИНИСТРАТОРА
        print("\n👑 Создание администратора...")
        admin_password = "Admin123!"
        admin_hash = get_password_hash(admin_password)
        
        admin_user = models.User(
            email="admin@cargopro.com",
            phone="+79991112233",
            full_name="Администратор Системы",
            role=models.UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            hashed_password=admin_hash,
            balance=0.0
        )
        db.add(admin_user)
        print(f"✅ Администратор: admin@cargopro.com / {admin_password}")
        print(f"   Хэш пароля: {admin_hash[:30]}...")
        
        # 2. СОЗДАЕМ КЛИЕНТОВ
        print("\n👥 Создание клиентов...")
        clients_data = [
            {
                "email": "client1@example.com",
                "phone": "+79992223344",
                "name": "Иван Иванов",
                "password": "Client1!",
                "balance": 50000.0
            },
            {
                "email": "client2@example.com", 
                "phone": "+79993334455",
                "name": "Мария Петрова",
                "password": "Client2!",
                "balance": 75000.0
            },
            {
                "email": "company@example.com",
                "phone": "+74951234567",
                "name": "ООО 'Грузовик'",
                "password": "Company1!",
                "balance": 150000.0
            }
        ]
        
        clients = []
        for client in clients_data:
            user = models.User(
                email=client["email"],
                phone=client["phone"],
                full_name=client["name"],
                role=models.UserRole.CLIENT,
                is_active=True,
                is_verified=True,
                hashed_password=get_password_hash(client["password"]),
                balance=client["balance"]
            )
            db.add(user)
            clients.append(user)
            print(f"✅ Клиент: {client['email']} / {client['password']}")
        
        # 3. СОЗДАЕМ ВОДИТЕЛЕЙ
        print("\n🚚 Создание водителей...")
        drivers_data = [
            {
                "email": "driver1@example.com",
                "phone": "+79994445566",
                "name": "Алексей Водителев",
                "password": "Driver1!",
                "verified": True,
                "vehicle": "Грузовик",
                "model": "Mercedes Actros",
                "plate": "А123ВС777"
            },
            {
                "email": "driver2@example.com",
                "phone": "+79995556677",
                "name": "Дмитрий Шоферов",
                "password": "Driver2!",
                "verified": True,
                "vehicle": "Фургон",
                "model": "Ford Transit",
                "plate": "В456ОР777"
            },
            {
                "email": "driver3@example.com",
                "phone": "+79996667788",
                "name": "Сергей Грузовиков",
                "password": "Driver3!",
                "verified": False,
                "vehicle": "Рефрижератор",
                "model": "Volvo FH",
                "plate": "С789ТУ777"
            }
        ]
        
        drivers = []
        for driver in drivers_data:
            # Пользователь-водитель
            driver_user = models.User(
                email=driver["email"],
                phone=driver["phone"],
                full_name=driver["name"],
                role=models.UserRole.DRIVER,
                is_active=True,
                is_verified=driver["verified"],
                hashed_password=get_password_hash(driver["password"]),
                balance=25000.0
            )
            db.add(driver_user)
            db.flush()  # Получаем ID
            
            # Профиль водителя
            driver_profile = models.DriverProfile(
                user_id=driver_user.id,
                vehicle_type=driver["vehicle"],
                vehicle_model=driver["model"],
                vehicle_number=driver["plate"],
                carrying_capacity=random.uniform(3.5, 20.0),
                volume=random.uniform(15.0, 90.0),
                verification_status=models.VerificationStatus.VERIFIED if driver["verified"] else models.VerificationStatus.PENDING,
                rating=round(random.uniform(4.0, 5.0), 1),
                total_orders=random.randint(10, 50),
                total_distance=random.uniform(5000, 15000),
                is_online=driver["verified"],
                current_location_lat=55.7558 + random.uniform(-0.1, 0.1) if driver["verified"] else None,
                current_location_lng=37.6173 + random.uniform(-0.1, 0.1) if driver["verified"] else None
            )
            db.add(driver_profile)
            drivers.append(driver_user)
            
            status = "верифицирован ✅" if driver["verified"] else "ожидает верификации ⏳"
            print(f"✅ Водитель: {driver['email']} / {driver['password']} ({status})")
        
        # 4. СОЗДАЕМ ЗАКАЗЫ
        print("\n📦 Создание заказов...")
        
        # Генерация номера заказа
        def generate_order_number():
            return f"ORD{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
        
        # Заказ 1: Поиск водителя
        order1 = models.Order(
            order_number=generate_order_number(),
            client_id=clients[0].id,
            status=models.OrderStatus.SEARCHING,
            from_address="Москва, ул. Тверская, 1",
            from_lat=55.7558,
            from_lng=37.6173,
            to_address="Санкт-Петербург, Невский проспект, 28",
            to_lat=59.9343,
            to_lng=30.3351,
            distance_km=634.0,
            cargo_description="Офисная мебель",
            cargo_weight=2.5,
            cargo_volume=12.0,
            cargo_type="Мебель",
            desired_price=35000.0,
            pickup_date=datetime.utcnow() + timedelta(days=2)
        )
        db.add(order1)
        print(f"✅ Заказ 1: {order1.order_number} (поиск водителя)")
        
        # Заказ 2: В пути
        order2 = models.Order(
            order_number=generate_order_number(),
            client_id=clients[1].id,
            driver_id=drivers[0].id,
            status=models.OrderStatus.EN_ROUTE,
            from_address="Екатеринбург, ул. Малышева, 51",
            from_lat=56.8389,
            from_lng=60.6057,
            to_address="Челябинск, пр. Ленина, 54",
            to_lat=55.1644,
            to_lng=61.4368,
            distance_km=198.0,
            cargo_description="Промышленное оборудование",
            cargo_weight=15.0,
            cargo_volume=60.0,
            cargo_type="Оборудование",
            desired_price=85000.0,
            final_price=82000.0,
            platform_fee=4100.0,
            order_amount=77900.0,
            payment_status=models.PaymentStatus.COMPLETED,
            pickup_date=datetime.utcnow() - timedelta(hours=12),
            delivery_date=datetime.utcnow() + timedelta(hours=36)
        )
        db.add(order2)
        print(f"✅ Заказ 2: {order2.order_number} (в пути)")
        
        # Заказ 3: Завершен
        order3 = models.Order(
            order_number=generate_order_number(),
            client_id=clients[2].id,
            driver_id=drivers[1].id,
            status=models.OrderStatus.COMPLETED,
            from_address="Новосибирск, Красный проспект, 28",
            from_lat=55.0302,
            from_lng=82.9204,
            to_address="Кемерово, ул. Весенняя, 15",
            to_lat=55.3547,
            to_lng=86.0863,
            distance_km=248.0,
            cargo_description="Строительные материалы",
            cargo_weight=25.0,
            cargo_volume=90.0,
            cargo_type="Строительные материалы",
            desired_price=120000.0,
            final_price=115000.0,
            platform_fee=5750.0,
            order_amount=109250.0,
            payment_status=models.PaymentStatus.COMPLETED,
            pickup_date=datetime.utcnow() - timedelta(days=3),
            delivery_date=datetime.utcnow() - timedelta(days=1),
            completed_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(order3)
        print(f"✅ Заказ 3: {order3.order_number} (завершен)")
        
        # Сохраняем все изменения
        db.commit()
        
        print("\n" + "=" * 60)
        print("🎉 БАЗА ДАННЫХ УСПЕШНО СОЗДАНА!")
        print("=" * 60)
        
        print("\n📋 УЧЕТНЫЕ ЗАПИСИ ДЛЯ ТЕСТИРОВАНИЯ:")
        print("-" * 50)
        print("👑 АДМИНИСТРАТОР (админ-панель):")
        print(f"  Email:    admin@cargopro.com")
        print(f"  Пароль:   Admin123!")
        print()
        print("👥 КЛИЕНТЫ (сайт/приложение):")
        print(f"  1. Email:    client1@example.com")
        print(f"     Пароль:   Client1!")
        print(f"     Баланс:   50 000 ₽")
        print()
        print(f"  2. Email:    client2@example.com")
        print(f"     Пароль:   Client2!")
        print(f"     Баланс:   75 000 ₽")
        print()
        print(f"  3. Email:    company@example.com")
        print(f"     Пароль:   Company1!")
        print(f"     Баланс:   150 000 ₽")
        print()
        print("🚚 ВОДИТЕЛИ (мобильное приложение):")
        print(f"  1. Email:    driver1@example.com")
        print(f"     Пароль:   Driver1!")
        print(f"     Статус:   верифицирован ✅")
        print()
        print(f"  2. Email:    driver2@example.com")
        print(f"     Пароль:   Driver2!")
        print(f"     Статус:   верифицирован ✅")
        print()
        print(f"  3. Email:    driver3@example.com")
        print(f"     Пароль:   Driver3!")
        print(f"     Статус:   ожидает верификации ⏳")
        print("-" * 50)
        
        print("\n🚀 СЛЕДУЮЩИЕ ШАГИ:")
        print("1. Запустите сервер: python run.py")
        print("2. Откройте API документацию: http://localhost:8000/api/docs")
        print("3. Запустите фронтенд (админ-панель)")
        print("4. Войдите с данными администратора")
        print("\n⚡ Тестирование через curl:")
        print('curl -X POST http://localhost:8000/api/auth/login \\')
        print('  -H "Content-Type: application/x-www-form-urlencoded" \\')
        print('  -d "username=admin@cargopro.com&password=Admin123!"')
        
    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИ СОЗДАНИИ БАЗЫ ДАННЫХ: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_database()