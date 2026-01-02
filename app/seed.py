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
    
    # Создаем тестовых клиентов
    print("👥 Создание тестовых клиентов...")
    clients_data = [
        {
            "email": "client1@example.com",
            "phone": "+79992223344",
            "full_name": "Иван Петров",
            "password": "Client123!"
        },
        {
            "email": "client2@example.com",
            "phone": "+79993334455",
            "full_name": "Мария Сидорова",
            "password": "Client123!"
        },
        {
            "email": "company@example.com",
            "phone": "+74951234567",
            "full_name": "ООО 'Грузовик'",
            "password": "Company123!"
        }
    ]
    
    clients = []
    for client_data in clients_data:
        client = models.User(
            email=client_data["email"],
            phone=client_data["phone"],
            full_name=client_data["full_name"],
            role=models.UserRole.CLIENT,
            is_active=True,
            is_verified=True,
            hashed_password=get_password_hash(client_data["password"]),
            balance=10000.0  # Начальный баланс
        )
        db.add(client)
        clients.append(client)
    
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
            "password": "Driver123!",
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
            "password": "Driver123!",
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
            "password": "Driver123!",
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
        },
        {
            "email": "driver4@example.com",
            "phone": "+79997778899",
            "full_name": "Павел Перевозкин",
            "password": "Driver123!",
            "vehicle_type": "Тентованный",
            "vehicle_model": "Scania R450",
            "vehicle_number": "Е012КХ777",
            "carrying_capacity": 22.0,
            "volume": 96.0,
            "verification_status": models.VerificationStatus.VERIFIED,
            "rating": 4.9,
            "total_orders": 67,
            "total_distance": 21000.0,
            "is_online": True
        }
    ]
    
    drivers = []
    for driver_data in drivers_data:
        # Создаем пользователя-водителя
        driver_user = models.User(
            email=driver_data["email"],
            phone=driver_data["phone"],
            full_name=driver_data["full_name"],
            role=models.UserRole.DRIVER,
            is_active=True,
            is_verified=True if driver_data["verification_status"] == models.VerificationStatus.VERIFIED else False,
            hashed_password=get_password_hash(driver_data["password"]),
            balance=5000.0  # Начальный баланс
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
    
    db.commit()
    for driver in drivers:
        db.refresh(driver)
        print(f"✅ Водитель создан: {driver.email}")
    
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
        },
        {
            "client_id": clients[2].id,
            "status": models.OrderStatus.DRAFT,
            "from_address": "Новосибирск, Красный проспект, 28",
            "from_lat": 55.0084,
            "from_lng": 82.9357,
            "to_address": "Красноярск, ул. Карла Маркса, 48",
            "to_lat": 56.0153,
            "to_lng": 92.8932,
            "cargo_description": "Строительные материалы",
            "cargo_weight": 15.0,
            "cargo_volume": 75.0,
            "cargo_type": "Стройматериалы",
            "desired_price": 42000.0,
            "pickup_date": datetime.utcnow() + timedelta(days=3)
        },
        {
            "client_id": clients[0].id,
            "driver_id": drivers[1].id,
            "status": models.OrderStatus.COMPLETED,
            "from_address": "Казань, ул. Баумана, 44",
            "from_lat": 55.7961,
            "from_lng": 49.1064,
            "to_address": "Самара, ул. Куйбышева, 92",
            "to_lat": 53.1959,
            "to_lng": 50.1002,
            "cargo_description": "Электроника и бытовая техника",
            "cargo_weight": 3.0,
            "cargo_volume": 15.0,
            "cargo_type": "Электроника",
            "desired_price": 22000.0,
            "final_price": 21500.0,
            "platform_fee": 1075.0,
            "order_amount": 20425.0,
            "payment_status": models.PaymentStatus.COMPLETED,
            "pickup_date": datetime.utcnow() - timedelta(days=5),
            "delivery_date": datetime.utcnow() - timedelta(days=2),
            "completed_at": datetime.utcnow() - timedelta(days=2)
        },
        {
            "client_id": clients[1].id,
            "status": models.OrderStatus.SEARCHING,
            "from_address": "Ростов-на-Дону, ул. Большая Садовая, 88",
            "from_lat": 47.2224,
            "from_lng": 39.7186,
            "to_address": "Краснодар, ул. Красная, 32",
            "to_lat": 45.0355,
            "to_lng": 38.9753,
            "cargo_description": "Продукты питания (охлажденные)",
            "cargo_weight": 5.0,
            "cargo_volume": 30.0,
            "cargo_type": "Продукты",
            "desired_price": 15000.0,
            "pickup_date": datetime.utcnow() + timedelta(days=1)
        }
    ]
    
    orders = []
    for i, order_data in enumerate(orders_data):
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
            **{k: v for k, v in order_data.items() if k != 'client_id' and k != 'driver_id'}
        )
        order.client_id = order_data["client_id"]
        if "driver_id" in order_data:
            order.driver_id = order_data["driver_id"]
        
        db.add(order)
        orders.append(order)
    
    db.commit()
    for order in orders:
        db.refresh(order)
        print(f"✅ Заказ создан: {order.order_number} ({order.status})")
    
    # Создаем тестовые ставки
    print("💰 Создание тестовых ставок...")
    bids_data = [
        {
            "order_id": orders[0].id,
            "driver_id": drivers[0].id,
            "proposed_price": 34000.0,
            "message": "Могу взять заказ завтра утром",
            "status": models.BidStatus.PENDING
        },
        {
            "order_id": orders[0].id,
            "driver_id": drivers[3].id,
            "proposed_price": 33000.0,
            "message": "Еду в том направлении, могу взять дешевле",
            "status": models.BidStatus.PENDING
        },
        {
            "order_id": orders[2].id,
            "driver_id": drivers[1].id,
            "proposed_price": 40000.0,
            "message": "Специализируюсь на строительных материалах",
            "status": models.BidStatus.PENDING
        },
        {
            "order_id": orders[4].id,
            "driver_id": drivers[0].id,
            "proposed_price": 14500.0,
            "message": "Есть рефрижератор, могу перевезти продукты",
            "status": models.BidStatus.ACCEPTED
        }
    ]
    
    for bid_data in bids_data:
        bid = models.Bid(**bid_data)
        db.add(bid)
    
    db.commit()
    print(f"✅ Создано {len(bids_data)} ставок")
    
    # Создаем тестовые сообщения в чате
    print("💬 Создание тестовых сообщений...")
    messages_data = [
        {
            "order_id": orders[1].id,
            "sender_id": clients[1].id,
            "content": "Здравствуйте! Когда планируете начать погрузку?",
            "timestamp": datetime.utcnow() - timedelta(days=1, hours=3)
        },
        {
            "order_id": orders[1].id,
            "sender_id": drivers[0].id,
            "content": "Добрый день! Подъеду к 10:00 завтра",
            "timestamp": datetime.utcnow() - timedelta(days=1, hours=2, minutes=30)
        },
        {
            "order_id": orders[1].id,
            "sender_id": clients[1].id,
            "content": "Отлично, буду ждать. Нужна ли помощь с погрузкой?",
            "timestamp": datetime.utcnow() - timedelta(days=1, hours=2)
        },
        {
            "order_id": orders[1].id,
            "sender_id": drivers[0].id,
            "content": "Да, потребуется 2 человека для погрузки",
            "timestamp": datetime.utcnow() - timedelta(days=1, hours=1)
        },
        {
            "order_id": orders[3].id,
            "sender_id": clients[0].id,
            "content": "Спасибо за быструю доставку! Все в порядке",
            "timestamp": datetime.utcnow() - timedelta(days=2, hours=5)
        },
        {
            "order_id": orders[3].id,
            "sender_id": drivers[1].id,
            "content": "Рад был помочь! Обращайтесь еще",
            "timestamp": datetime.utcnow() - timedelta(days=2, hours=4)
        }
    ]
    
    for message_data in messages_data:
        message = models.Message(**message_data)
        db.add(message)
    
    db.commit()
    print(f"✅ Создано {len(messages_data)} сообщений")
    
    # Создаем тестовые платежи
    print("💳 Создание тестовых платежей...")
    payments_data = [
        {
            "user_id": clients[1].id,
            "order_id": orders[1].id,
            "amount": 17500.0,
            "currency": "RUB",
            "status": models.PaymentStatus.COMPLETED,
            "payment_method": "card",
            "payment_id": "pay_test_123456",
            "description": f"Оплата заказа #{orders[1].order_number}",
            "completed_at": datetime.utcnow() - timedelta(days=1)
        },
        {
            "user_id": clients[0].id,
            "order_id": orders[3].id,
            "amount": 21500.0,
            "currency": "RUB",
            "status": models.PaymentStatus.COMPLETED,
            "payment_method": "sbp",
            "payment_id": "pay_test_789012",
            "description": f"Оплата заказа #{orders[3].order_number}",
            "completed_at": datetime.utcnow() - timedelta(days=2)
        }
    ]
    
    for payment_data in payments_data:
        payment = models.Payment(**payment_data)
        db.add(payment)
    
    db.commit()
    print(f"✅ Создано {len(payments_data)} платежей")
    
    # Создаем тестовые уведомления
    print("🔔 Создание тестовых уведомлений...")
    notifications_data = [
        {
            "user_id": drivers[0].id,
            "title": "Новый заказ доступен",
            "message": "Появился новый заказ по вашему маршруту",
            "type": "new_order",
            "data": {"order_id": orders[0].id},
            "is_read": False,
            "created_at": datetime.utcnow() - timedelta(hours=2)
        },
        {
            "user_id": drivers[3].id,
            "title": "Новый заказ доступен",
            "message": "Появился новый заказ по вашему маршруту",
            "type": "new_order",
            "data": {"order_id": orders[0].id},
            "is_read": True,
            "created_at": datetime.utcnow() - timedelta(hours=1)
        },
        {
            "user_id": clients[1].id,
            "title": "Водитель назначен",
            "message": "На ваш заказ назначен водитель",
            "type": "driver_assigned",
            "data": {"order_id": orders[1].id, "driver_id": drivers[0].id},
            "is_read": True,
            "created_at": datetime.utcnow() - timedelta(days=1)
        },
        {
            "user_id": admin_user.id,
            "title": "Новый водитель",
            "message": "Зарегистрирован новый водитель",
            "type": "new_driver",
            "data": {"driver_id": drivers[2].id},
            "is_read": False,
            "created_at": datetime.utcnow() - timedelta(days=3)
        }
    ]
    
    for notification_data in notifications_data:
        notification = models.Notification(**notification_data)
        db.add(notification)
    
    db.commit()
    print(f"✅ Создано {len(notifications_data)} уведомлений")
    
    print("🎉 Заполнение базы данных завершено!")
    print("\n📋 Тестовые данные для входа:")
    print("=" * 50)
    print("👑 Администратор:")
    print(f"  Email: admin@cargopro.com")
    print(f"  Пароль: Admin123!")
    print()
    print("👥 Клиенты:")
    print(f"  1. Email: client1@example.com, Пароль: Client123!")
    print(f"  2. Email: client2@example.com, Пароль: Client123!")
    print(f"  3. Email: company@example.com, Пароль: Company123!")
    print()
    print("🚚 Водители:")
    print(f"  1. Email: driver1@example.com, Пароль: Driver123! (верифицирован, онлайн)")
    print(f"  2. Email: driver2@example.com, Пароль: Driver123! (верифицирован, онлайн)")
    print(f"  3. Email: driver3@example.com, Пароль: Driver123! (ожидает верификации, офлайн)")
    print(f"  4. Email: driver4@example.com, Пароль: Driver123! (верифицирован, онлайн)")
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