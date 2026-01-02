# test_cargopro_api.py
"""
Тесты для проверки всех эндпоинтов CargoPro API
IP адрес: 192.168.10.102
"""

import requests
import json
import time
import os
import sys
from datetime import datetime
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
BASE_URL = "http://192.168.10.102:8000"
API_URL = f"{BASE_URL}/api"

# Тестовые данные
TEST_ADMIN = {
    "email": "admin@cargopro.com",
    "password": "Admin123!"
}

TEST_CLIENT = {
    "email": "client1@example.com",
    "password": "Client123!"
}

TEST_DRIVER = {
    "email": "driver1@example.com",
    "password": "Driver123!"
}

# Глобальные переменные для хранения токенов и ID
tokens = {}
user_ids = {}
order_id = None
bid_id = None

# Вспомогательные функции
def get_auth_headers(user_type="admin"):
    """Получение заголовков с токеном авторизации"""
    token = tokens.get(user_type)
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}

def make_request(method, endpoint, data=None, headers=None, user_type="admin", expected_status=200):
    """Универсальная функция для выполнения запросов"""
    url = f"{API_URL}{endpoint}"
    
    if headers is None:
        headers = get_auth_headers(user_type)
    
    headers["Content-Type"] = "application/json"
    
    logger.info(f"Making {method} request to {endpoint}")
    
    if method == "GET":
        response = requests.get(url, headers=headers, params=data)
    elif method == "POST":
        response = requests.post(url, json=data, headers=headers)
    elif method == "PUT":
        response = requests.put(url, json=data, headers=headers)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    logger.info(f"Response status: {response.status_code}")
    
    if response.status_code != expected_status:
        logger.error(f"Request failed: {response.status_code} - {response.text}")
    
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"
    
    return response

# Основные тесты
class TestAuthAPI:
    """Тесты для эндпоинтов аутентификации"""
    
    def test_health_check(self):
        """Тест проверки здоровья API"""
        response = make_request("GET", "/", data=None, headers={}, user_type=None, expected_status=200)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        logger.info(f"Health check: {data['message']}")
    
    def test_register_new_user(self):
        """Тест регистрации нового пользователя"""
        timestamp = int(time.time())
        new_user = {
            "email": f"testuser{timestamp}@example.com",
            "phone": f"+7999{timestamp % 10000000:07d}",
            "full_name": f"Test User {timestamp}",
            "role": "client",
            "password": "Test123!"
        }
        
        response = make_request("POST", "/auth/register", new_user, user_type=None)
        data = response.json()
        assert "email" in data
        assert data["email"] == new_user["email"]
        logger.info(f"New user registered: {data['email']}")
    
    def test_login_admin(self):
        """Тест входа администратора"""
        response = make_request("POST", "/auth/login", TEST_ADMIN, user_type=None)
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        
        tokens["admin"] = data["access_token"]
        user_ids["admin"] = data["user"]["id"]
        
        logger.info(f"Admin logged in: {data['user']['email']}")
        logger.info(f"Admin token received")
    
    def test_login_client(self):
        """Тест входа клиента"""
        response = make_request("POST", "/auth/login", TEST_CLIENT, user_type=None)
        data = response.json()
        assert "access_token" in data
        
        tokens["client"] = data["access_token"]
        user_ids["client"] = data["user"]["id"]
        
        logger.info(f"Client logged in: {data['user']['email']}")
    
    def test_login_driver(self):
        """Тест входа водителя"""
        response = make_request("POST", "/auth/login", TEST_DRIVER, user_type=None)
        data = response.json()
        assert "access_token" in data
        
        tokens["driver"] = data["access_token"]
        user_ids["driver"] = data["user"]["id"]
        
        logger.info(f"Driver logged in: {data['user']['email']}")
    
    def test_get_current_user(self):
        """Тест получения информации о текущем пользователе"""
        response = make_request("GET", "/auth/me", user_type="admin")
        data = response.json()
        assert "email" in data
        assert data["email"] == TEST_ADMIN["email"]
        logger.info(f"Current user: {data['email']}")
    
    def test_refresh_token(self):
        """Тест обновления токена"""
        # Сначала получаем refresh токен
        login_response = make_request("POST", "/auth/login", TEST_ADMIN, user_type=None)
        refresh_token = login_response.json()["refresh_token"]
        
        response = make_request("POST", "/auth/refresh", {"refresh_token": refresh_token}, user_type=None)
        data = response.json()
        assert "access_token" in data
        logger.info("Token refreshed successfully")

class TestUsersAPI:
    """Тесты для эндпоинтов пользователей"""
    
    def test_get_user_profile(self):
        """Тест получения профиля пользователя"""
        response = make_request("GET", "/users/me", user_type="client")
        data = response.json()
        assert "email" in data
        assert data["email"] == TEST_CLIENT["email"]
        logger.info(f"User profile retrieved: {data['email']}")
    
    def test_update_user_profile(self):
        """Тест обновления профиля пользователя"""
        update_data = {
            "full_name": "Updated Test User",
            "phone": "+79991112233"
        }
        
        response = make_request("PUT", "/users/me", update_data, user_type="client")
        data = response.json()
        assert data["full_name"] == update_data["full_name"]
        logger.info(f"User profile updated: {data['full_name']}")
    
    def test_get_all_users_admin(self):
        """Тест получения списка пользователей (только админ)"""
        response = make_request("GET", "/users/", user_type="admin")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Retrieved {len(data)} users")
    
    def test_get_user_by_id(self):
        """Тест получения пользователя по ID (только админ)"""
        response = make_request("GET", f"/users/{user_ids['client']}", user_type="admin")
        data = response.json()
        assert data["id"] == user_ids["client"]
        logger.info(f"User retrieved by ID: {data['email']}")
    
    def test_get_user_balance(self):
        """Тест получения баланса пользователя"""
        response = make_request("GET", "/users/me/balance", user_type="client")
        data = response.json()
        assert "balance" in data
        logger.info(f"User balance: {data['balance']}")

class TestOrdersAPI:
    """Тесты для эндпоинтов заказов"""
    
    def test_create_order(self):
        """Тест создания нового заказа"""
        global order_id
        
        order_data = {
            "from_address": "Москва, Ленинский проспект, 32",
            "from_lat": 55.6911,
            "from_lng": 37.5734,
            "to_address": "Санкт-Петербург, Невский проспект, 28",
            "to_lat": 59.9343,
            "to_lng": 30.3351,
            "cargo_description": "Тестовый груз для проверки API",
            "cargo_weight": 2.5,
            "cargo_volume": 12.0,
            "cargo_type": "Оборудование",
            "desired_price": 35000.0
        }
        
        response = make_request("POST", "/orders/", order_data, user_type="client")
        data = response.json()
        
        assert "order_number" in data
        assert "id" in data
        order_id = data["id"]
        
        logger.info(f"Order created: {data['order_number']} (ID: {order_id})")
    
    def test_get_my_orders(self):
        """Тест получения списка заказов пользователя"""
        response = make_request("GET", "/orders/", user_type="client")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Retrieved {len(data)} orders for client")
    
    def test_get_order_by_id(self):
        """Тест получения заказа по ID"""
        response = make_request("GET", f"/orders/{order_id}", user_type="client")
        data = response.json()
        assert data["id"] == order_id
        logger.info(f"Order retrieved: {data['order_number']}")
    
    def test_publish_order(self):
        """Тест публикации заказа"""
        response = make_request("POST", f"/orders/{order_id}/publish", user_type="client")
        data = response.json()
        assert "message" in data
        logger.info(f"Order published: {data['message']}")
    
    def test_get_available_orders(self):
        """Тест получения доступных заказов (для водителей)"""
        response = make_request("GET", "/orders/available", user_type="driver")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Retrieved {len(data)} available orders")
    
    def test_calculate_price(self):
        """Тест расчета стоимости перевозки"""
        calc_data = {
            "from_lat": 55.7558,
            "from_lng": 37.6173,
            "to_lat": 59.9343,
            "to_lng": 30.3351,
            "weight": 2.5,
            "volume": 12.0
        }
        
        response = make_request("POST", "/orders/calculate-price", calc_data, user_type="client")
        data = response.json()
        assert "suggested_price" in data
        logger.info(f"Price calculated: {data['suggested_price']}")

class TestBidsAPI:
    """Тесты для эндпоинтов ставок"""
    
    def test_create_bid(self):
        """Тест создания ставки на заказ"""
        global bid_id
        
        bid_data = {
            "proposed_price": 34000.0,
            "message": "Тестовая ставка от водителя"
        }
        
        response = make_request("POST", f"/bids/order/{order_id}", bid_data, user_type="driver")
        data = response.json()
        
        assert "id" in data
        bid_id = data["id"]
        
        logger.info(f"Bid created: ID {bid_id} for order {order_id}")
    
    def test_get_order_bids(self):
        """Тест получения ставок для заказа"""
        response = make_request("GET", f"/bids/order/{order_id}", user_type="client")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Retrieved {len(data)} bids for order")
    
    def test_get_my_bids(self):
        """Тест получения ставок текущего водителя"""
        response = make_request("GET", "/bids/my", user_type="driver")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Driver has {len(data)} bids")
    
    def test_get_best_bids(self):
        """Тест получения лучших ставок для заказа"""
        response = make_request("GET", f"/bids/order/{order_id}/best", user_type="client")
        data = response.json()
        assert "bids" in data
        logger.info(f"Retrieved {data['count']} best bids")
    
    def test_get_bid_stats(self):
        """Тест получения статистики по ставкам"""
        response = make_request("GET", "/bids/stats/my", user_type="driver")
        data = response.json()
        assert "total_bids" in data
        logger.info(f"Bid stats: {data['total_bids']} total bids")

class TestDriversAPI:
    """Тесты для эндпоинтов водителей"""
    
    def test_create_driver_profile(self):
        """Тест создания профиля водителя"""
        # Сначала создадим нового водителя
        timestamp = int(time.time())
        new_driver = {
            "email": f"newdriver{timestamp}@example.com",
            "phone": f"+7999{timestamp % 10000000:07d}",
            "full_name": f"New Driver {timestamp}",
            "role": "driver",
            "password": "Driver123!"
        }
        
        response = make_request("POST", "/auth/register", new_driver, user_type=None)
        driver_id = response.json()["id"]
        
        # Логинимся как новый водитель
        login_data = {"email": new_driver["email"], "password": new_driver["password"]}
        login_response = make_request("POST", "/auth/login", login_data, user_type=None)
        driver_token = login_response.json()["access_token"]
        
        # Создаем профиль
        profile_data = {
            "vehicle_type": "Грузовик",
            "vehicle_model": "Test Model",
            "vehicle_number": f"A{timestamp % 1000:03d}BC777",
            "carrying_capacity": 15.0,
            "volume": 60.0
        }
        
        headers = {"Authorization": f"Bearer {driver_token}", "Content-Type": "application/json"}
        response = requests.post(f"{API_URL}/drivers/profile", json=profile_data, headers=headers)
        
        assert response.status_code == 200
        logger.info(f"Driver profile created for: {new_driver['email']}")
    
    def test_get_driver_profile(self):
        """Тест получения профиля водителя"""
        response = make_request("GET", "/drivers/profile", user_type="driver")
        data = response.json()
        assert "vehicle_number" in data
        logger.info(f"Driver profile retrieved: {data['vehicle_number']}")
    
    def test_set_driver_online(self):
        """Тест установки статуса онлайн для водителя"""
        response = make_request("POST", "/drivers/profile/online?lat=55.7558&lng=37.6173", user_type="driver")
        data = response.json()
        assert "message" in data
        logger.info(f"Driver status: {data['message']}")
    
    def test_get_nearby_drivers(self):
        """Тест поиска водителей поблизости"""
        response = make_request("GET", "/drivers/nearby?lat=55.7558&lng=37.6173&radius_km=50", user_type="client")
        data = response.json()
        assert "drivers" in data
        logger.info(f"Found {len(data['drivers'])} nearby drivers")

class TestAdminAPI:
    """Тесты для административных эндпоинтов"""
    
    def test_get_admin_stats(self):
        """Тест получения статистики для админ-панели"""
        response = make_request("GET", "/admin/stats", user_type="admin")
        data = response.json()
        assert "total_users" in data
        logger.info(f"Admin stats: {data['total_users']} users, {data['total_orders']} orders")
    
    def test_get_pending_verifications(self):
        """Тест получения списка водителей, ожидающих верификации"""
        response = make_request("GET", "/admin/verifications/pending", user_type="admin")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Pending verifications: {len(data)} drivers")
    
    def test_get_detailed_stats(self):
        """Тест получения детальной статистики"""
        response = make_request("GET", "/admin/stats/detailed?period=7d", user_type="admin")
        data = response.json()
        assert "period" in data
        logger.info(f"Detailed stats for period: {data['period']}")
    
    def test_get_recent_activity(self):
        """Тест получения недавней активности"""
        response = make_request("GET", "/admin/recent-activity?limit=10", user_type="admin")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Recent activity: {len(data)} events")
    
    def test_get_orders_analytics(self):
        """Тест получения аналитики по заказам"""
        response = make_request("GET", "/admin/orders/analytics?period=30d", user_type="admin")
        data = response.json()
        assert "total_orders" in data
        logger.info(f"Orders analytics: {data['total_orders']} orders")

class TestChatAPI:
    """Тесты для эндпоинтов чата"""
    
    def test_get_chat_messages(self):
        """Тест получения сообщений чата"""
        response = make_request("GET", f"/chat/{order_id}/messages", user_type="client")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Chat messages: {len(data)} messages")
    
    def test_mark_chat_as_read(self):
        """Тест пометки сообщений как прочитанных"""
        response = make_request("POST", f"/chat/{order_id}/mark-read", user_type="client")
        data = response.json()
        assert "message" in data
        logger.info(f"Chat marked as read: {data['message']}")
    
    def test_get_unread_count(self):
        """Тест получения количества непрочитанных сообщений"""
        response = make_request("GET", "/chat/unread-count", user_type="client")
        data = response.json()
        assert "total_unread" in data
        logger.info(f"Unread messages: {data['total_unread']}")

class TestHealthAPI:
    """Тесты для эндпоинтов здоровья системы"""
    
    def test_health_check_endpoint(self):
        """Тест проверки здоровья"""
        response = make_request("GET", "/health", user_type=None, headers={})
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        logger.info(f"Health check: {data['status']}")
    
    def test_detailed_health_check(self):
        """Тест детальной проверки здоровья"""
        response = make_request("GET", "/health/detailed", user_type="admin")
        data = response.json()
        assert "status" in data
        logger.info(f"Detailed health check: {data['status']}")
    
    def test_database_health(self):
        """Тест проверки здоровья базы данных"""
        response = make_request("GET", "/health/database", user_type="admin")
        data = response.json()
        assert "status" in data
        logger.info(f"Database health: {data['status']}")
    
    def test_system_metrics(self):
        """Тест получения метрик системы"""
        response = make_request("GET", "/metrics", user_type="admin")
        data = response.json()
        assert "timestamp" in data
        logger.info("System metrics retrieved")

class TestIntegrationAPI:
    """Тесты для интеграционных эндпоинтов"""
    
    def test_get_order_status_public(self):
        """Тест получения статуса заказа (публичный доступ)"""
        # Сначала получаем номер заказа
        order_response = make_request("GET", f"/orders/{order_id}", user_type="client")
        order_number = order_response.json()["order_number"]
        
        # Запрашиваем статус публично
        response = requests.get(f"{API_URL}/integration/public/order/{order_number}/status")
        assert response.status_code == 200
        data = response.json()
        assert "order_number" in data
        logger.info(f"Public order status: {data['status']}")
    
    def test_get_payment_methods(self):
        """Тест получения методов оплаты"""
        response = make_request("GET", "/integration/payment/methods", 
                              headers={"X-API-Key": "mobile_app_key"}, user_type=None)
        data = response.json()
        assert "methods" in data
        logger.info(f"Payment methods: {len(data['methods'])} available")

class TestTrackAPI:
    """Тесты для эндпоинтов отслеживания"""
    
    def test_get_driver_locations(self):
        """Тест получения истории местоположения водителя"""
        response = make_request("GET", f"/track/driver/{user_ids['driver']}/locations?hours=24&limit=10", 
                              user_type="admin")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Driver locations: {len(data)} records")
    
    def test_get_order_route(self):
        """Тест получения маршрута заказа"""
        response = make_request("GET", f"/track/order/{order_id}/route", user_type="client")
        data = response.json()
        assert "route_points" in data
        logger.info(f"Order route points: {len(data['route_points'])}")

# Дополнительные тесты для завершения операций
class TestCleanupAPI:
    """Тесты для завершения операций"""
    
    def test_accept_bid(self):
        """Тест принятия ставки"""
        if bid_id:
            response = make_request("POST", f"/bids/{bid_id}/accept", user_type="client")
            data = response.json()
            assert "status" in data
            logger.info(f"Bid accepted: {data['status']}")
    
    def test_complete_order(self):
        """Тест завершения заказа"""
        if order_id:
            # Сначала обновим статус заказа
            update_data = {"status": "en_route"}
            response = make_request("PUT", f"/orders/{order_id}", update_data, user_type="admin")
            
            # Завершаем заказ
            complete_response = make_request("POST", f"/orders/{order_id}/complete", user_type="driver")
            data = complete_response.json()
            assert "message" in data
            logger.info(f"Order completed: {data['message']}")
    
    def test_cancel_order(self):
        """Тест отмены заказа (создадим новый для отмены)"""
        # Создаем новый заказ для отмены
        order_data = {
            "from_address": "Тестовый адрес отправки",
            "from_lat": 55.7558,
            "from_lng": 37.6173,
            "to_address": "Тестовый адрес доставки",
            "to_lat": 55.7600,
            "to_lng": 37.6200,
            "cargo_description": "Тестовый груз для отмены",
            "cargo_weight": 1.0,
            "cargo_volume": 5.0,
            "cargo_type": "Тест",
            "desired_price": 5000.0
        }
        
        response = make_request("POST", "/orders/", order_data, user_type="client")
        cancel_order_id = response.json()["id"]
        
        # Отменяем заказ
        cancel_response = make_request("POST", f"/orders/{cancel_order_id}/cancel", user_type="client")
        cancel_data = cancel_response.json()
        assert "message" in cancel_data
        logger.info(f"Order cancelled: {cancel_data['message']}")

# Функция для запуска всех тестов
def run_all_tests():
    """Запуск всех тестов последовательно"""
    test_classes = [
        TestAuthAPI(),
        TestUsersAPI(),
        TestOrdersAPI(),
        TestBidsAPI(),
        TestDriversAPI(),
        TestAdminAPI(),
        TestChatAPI(),
        TestHealthAPI(),
        TestIntegrationAPI(),
        TestTrackAPI(),
        TestCleanupAPI()
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    logger.info("=" * 80)
    logger.info("НАЧАЛО ТЕСТИРОВАНИЯ CARGO PRO API")
    logger.info("=" * 80)
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        logger.info(f"\nТестируем: {class_name}")
        logger.info("-" * 60)
        
        # Получаем все методы тестирования из класса
        test_methods = [method for method in dir(test_class) 
                       if method.startswith('test_') and callable(getattr(test_class, method))]
        
        for method_name in test_methods:
            total_tests += 1
            method = getattr(test_class, method_name)
            
            try:
                method()
                logger.info(f"OK {method_name}: PASSED")
                passed_tests += 1
            except Exception as e:
                logger.error(f"FAIL {method_name}: FAILED - {str(e)}")
                failed_tests.append(f"{class_name}.{method_name}: {str(e)}")
    
    # Вывод результатов
    logger.info("\n" + "=" * 80)
    logger.info("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    logger.info("=" * 80)
    logger.info(f"Всего тестов: {total_tests}")
    logger.info(f"Пройдено: {passed_tests}")
    logger.info(f"Провалено: {total_tests - passed_tests}")
    
    if failed_tests:
        logger.info("\nПРОВАЛЕННЫЕ ТЕСТЫ:")
        for failed_test in failed_tests:
            logger.info(f"  - {failed_test}")
    else:
        logger.info("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    
    return passed_tests == total_tests

def main():
    """Основная функция"""
    # Проверка доступности сервера
    try:
        logger.info(f"Проверяю доступность сервера {BASE_URL}...")
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200:
            logger.info(f"OK Сервер доступен по адресу {BASE_URL}")
            
            # Запуск всех тестов
            success = run_all_tests()
            
            if success:
                logger.info("\nВСЕ ЭНДПОИНТЫ РАБОТАЮТ КОРРЕКТНО!")
                exit(0)
            else:
                logger.info("\nНЕКОТОРЫЕ ТЕСТЫ ПРОВАЛИЛИСЬ!")
                exit(1)
        else:
            logger.error(f"FAIL Сервер недоступен или вернул ошибку: {response.status_code}")
            exit(1)
    except requests.exceptions.ConnectionError:
        logger.error(f"FAIL Не удалось подключиться к серверу {BASE_URL}")
        logger.info("Убедитесь, что:")
        logger.info("1. Сервер запущен (python run.py)")
        logger.info("2. IP адрес верный (192.168.10.102)")
        logger.info("3. Порт 8000 открыт")
        exit(1)
    except Exception as e:
        logger.error(f"FAIL Ошибка при подключении: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()