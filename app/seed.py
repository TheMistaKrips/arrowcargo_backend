"""
Seed данные для начальной настройки базы данных
"""
from sqlalchemy.orm import Session
import random
from datetime import datetime, timedelta
from . import crud, models, schemas
from .auth import get_password_hash

def seed_database(db: Session):
    """Заполнение базы данных тестовыми данными"""
    print("🌱 Заполнение базы данных тестовыми данными...")
    
    # Проверяем, есть ли уже данные
    existing_users = db.query(models.User).count()
    if existing_users > 0:
        print("⚠️  База данных уже содержит данные. Пропускаем seed.")
        return
    
    # Создаем администратора
    print("👑 Создание администратора...")
    try:
        admin_user = models.User(
            email="admin@cargopro.com",
            phone="+79991112233",
            full_name="Администратор CargoPro",
            role=models.UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            hashed_password=get_password_hash("Admin123!"),
            balance=0.0
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"✅ Администратор создан: {admin_user.email}")
    except Exception as e:
        print(f"❌ Ошибка создания администратора: {e}")
        return
    
    # Создаем тестовых клиентов
    print("👥 Создание тестовых клиентов...")
    clients_data = [
        {
            "email": "client1@example.com",
            "phone": "+79992223344",
            "full_name": "Иван Петров",
            "password": "Client123"
        },
        {
            "email": "client2@example.com",
            "phone": "+79993334455",
            "full_name": "Мария Сидорова",
            "password": "Client123"
        },
        {
            "email": "company@example.com",
            "phone": "+74951234567",
            "full_name": "ООО 'Грузовик'",
            "password": "Company123"
        }
    ]
    
    clients = []
    for client_data in clients_data:
        try:
            client = models.User(
                email=client_data["email"],
                phone=client_data["phone"],
                full_name=client_data["full_name"],
                role=models.UserRole.CLIENT,
                is_active=True,
                is_verified=True,
                hashed_password=get_password_hash(client_data["password"]),
                balance=10000.0
            )
            db.add(client)
            clients.append(client)
        except Exception as e:
            print(f"Ошибка создания клиента {client_data['email']}: {e}")
    
    db.commit()
    for client in clients:
        db.refresh(client)
        print(f"✅ Клиент создан: {client.email}")
    
    # Создаем тестовых водителей
    print("🚚 Создание тестовых водителей...")
    drivers_data = [
        {
            "email": "driver1@example.com",
            "phone": "+79994445566",
            "full_name": "Алексей Водилов",
            "password": "Driver123",
            "vehicle_type": "Грузовик",
            "vehicle_model": "Mercedes Actros",
            "vehicle_number": "А123ВС777",
            "carrying_capacity": 20.0,
            "volume": 90.0,
            "verification_status": models.VerificationStatus.VERIFIED,
            "rating": 4.8,
            "total_orders": 42,
            "total_distance": 12500.5,
            "is_online": True
        },
        {
            "email": "driver2@example.com",
            "phone": "+79995556677",
            "full_name": "Дмитрий Шоферов",
            "password": "Driver123",
            "vehicle_type": "Фургон",
            "vehicle_model": "Ford Transit",
            "vehicle_number": "В456ОР777",
            "carrying_capacity": 3.5,
            "volume": 18.0,
            "verification_status": models.VerificationStatus.VERIFIED,
            "rating": 4.5,
            "total_orders": 28,
            "total_distance": 8500.0,
            "is_online": True
        },
        {
            "email": "driver3@example.com",
            "phone": "+79996667788",
            "full_name": "Сергей Грузовиков",
            "password": "Driver123",
            "vehicle_type": "Рефрижератор",
            "vehicle_model": "Volvo FH",
            "vehicle_number": "С789ТУ777",
            "carrying_capacity": 18.0,
            "volume": 82.0,
            "verification_status": models.VerificationStatus.PENDING,
            "rating": 4.2,
            "total_orders": 15,
            "total_distance": 6200.0,
            "is_online": False
        }
    ]
    
    drivers = []
    for driver_data in drivers_data:
        try:
            # Создаем пользователя-водителя
            driver_user = models.User(
                email=driver_data["email"],
                phone=driver_data["phone"],
                full_name=driver_data["full_name"],
                role=models.UserRole.DRIVER,
                is_active=True,
                is_verified=True if driver_data["verification_status"] == models.VerificationStatus.VERIFIED else False,
                hashed_password=get_password_hash(driver_data["password"]),
                balance=5000.0
            )
            db.add(driver_user)
            db.flush()  # Получаем ID пользователя
            
            # Создаем профиль водителя
            driver_profile = models.DriverProfile(
                user_id=driver_user.id,
                vehicle_type=driver_data["vehicle_type"],
                vehicle_model=driver_data["vehicle_model"],
                vehicle_number=driver_data["vehicle_number"],
                carrying_capacity=driver_data["carrying_capacity"],
                volume=driver_data["volume"],
                verification_status=driver_data["verification_status"],
                rating=driver_data["rating"],
                total_orders=driver_data["total_orders"],
                total_distance=driver_data["total_distance"],
                is_online=driver_data["is_online"],
                current_location_lat=55.7558 + random.uniform(-0.1, 0.1) if driver_data["is_online"] else None,
                current_location_lng=37.6173 + random.uniform(-0.1, 0.1) if driver_data["is_online"] else None
            )
            db.add(driver_profile)
            drivers.append(driver_user)
            print(f"✅ Водитель создан: {driver_user.email}")
        except Exception as e:
            print(f"Ошибка создания водителя {driver_data.get('email', 'unknown')}: {e}")
    
    db.commit()
    
    # Создаем тестовые заказы
    print("📦 Создание тестовых заказов...")
    orders_data = [
        {
            "client_id": clients[0].id,
            "status": models.OrderStatus.SEARCHING,
            "from_address": "Москва, Ленинский проспект, 32",
            "from_lat": 55.6911,
            "from_lng": 37.5734,
            "to_address": "Санкт-Петербург, Невский проспект, 28",
            "to_lat": 59.9343,
            "to_lng": 30.3351,
            "cargo_description": "Оборудование для офиса",
            "cargo_weight": 2.5,
            "cargo_volume": 12.0,
            "cargo_type": "Оборудование",
            "desired_price": 35000.0,
            "pickup_date": datetime.utcnow() + timedelta(days=2)
        },
        {
            "client_id": clients[1].id,
            "driver_id": drivers[0].id,
            "status": models.OrderStatus.EN_ROUTE,
            "from_address": "Екатеринбург, ул. Малышева, 51",
            "from_lat": 56.8389,
            "from_lng": 60.6057,
            "to_address": "Челябинск, пр. Ленина, 54",
            "to_lat": 55.1644,
            "to_lng": 61.4368,
            "cargo_description": "Партия одежды",
            "cargo_weight": 8.0,
            "cargo_volume": 45.0,
            "cargo_type": "Одежда",
            "desired_price": 18000.0,
            "final_price": 17500.0,
            "platform_fee": 875.0,
            "order_amount": 16625.0,
            "payment_status": models.PaymentStatus.COMPLETED,
            "pickup_date": datetime.utcnow() - timedelta(days=1),
            "delivery_date": datetime.utcnow() + timedelta(days=1)
        }
    ]
    
    for i, order_data in enumerate(orders_data):
        try:
            # Генерируем номер заказа
            order_number = crud.generate_order_number()
            
            # Расчет расстояния
            distance = crud.utils.calculate_distance(
                order_data["from_lat"], order_data["from_lng"],
                order_data["to_lat"], order_data["to_lng"]
            )
            
            order = models.Order(
                order_number=order_number,
                distance_km=distance,
                **{k: v for k, v in order_data.items() if k not in ['client_id', 'driver_id']}
            )
            order.client_id = order_data["client_id"]
            if "driver_id" in order_data:
                order.driver_id = order_data["driver_id"]
            
            db.add(order)
            db.flush()
            print(f"✅ Заказ создан: {order.order_number} ({order.status})")
        except Exception as e:
            print(f"Ошибка создания заказа {i}: {e}")
    
    db.commit()
    
    print("🎉 Заполнение базы данных завершено!")
    print("\n📋 Тестовые данные для входа:")
    print("=" * 50)
    print("👑 Администратор (для админ-панели):")
    print(f"  Email: admin@cargopro.com")
    print(f"  Пароль: Admin123!")
    print()
    print("👥 Клиенты (через API или мобильное приложение):")
    print(f"  1. Email: client1@example.com, Пароль: Client123")
    print(f"  2. Email: client2@example.com, Пароль: Client123")
    print()
    print("🚚 Водители (через мобильное приложение):")
    print(f"  1. Email: driver1@example.com, Пароль: Driver123 (верифицирован)")
    print(f"  2. Email: driver2@example.com, Пароль: Driver123 (верифицирован)")
    print(f"  3. Email: driver3@example.com, Пароль: Driver123 (ожидает верификации)")
    print("=" * 50)

def clear_database(db: Session):
    """Очистка базы данных (только для тестов!)"""
    print("⚠️  Очистка базы данных...")
    
    # Порядок удаления важен из-за внешних ключей
    db.query(models.Notification).delete()
    db.query(models.Payment).delete()
    db.query(models.LocationUpdate).delete()
    db.query(models.Message).delete()
    db.query(models.Bid).delete()
    db.query(models.Order).delete()
    db.query(models.DriverProfile).delete()
    db.query(models.User).delete()
    
    db.commit()
    print("✅ База данных очищена")