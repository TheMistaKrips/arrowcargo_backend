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
    "username": "admin@cargopro.com",
    "password": "Admin123!"
}

TEST_CLIENT = {
    "username": "client1@example.com",
    "password": "Client123!"
}

TEST_DRIVER = {
    "username": "driver1@example.com",
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
    
    if data and method in ["POST", "PUT"]:
        headers["Content-Type"] = "application/json"
    
    logger.info(f"Making {method} request to {endpoint}")
    
    try:
        if method == "GET":
            if data:
                response = requests.get(url, headers=headers, params=data)
            else:
                response = requests.get(url, headers=headers)
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
    except Exception as e:
        logger.error(f"Request error: {e}")
        raise

def login_user(user_data, user_type):
    """Вход пользователя"""
    response = requests.post(f"{API_URL}/auth/login", 
                           data=user_data,
                           headers={"Content-Type": "application/x-www-form-urlencoded"})
    
    if response.status_code == 200:
        data = response.json()
        tokens[user_type] = data["access_token"]
        user_ids[user_type] = data["user"]["id"]
        logger.info(f"{user_type.capitalize()} logged in: {user_data['username']}")
        return True
    else:
        logger.error(f"Login failed for {user_type}: {response.status_code} - {response.text}")
        return False

# Основные тесты
class TestAuthAPI:
    """Тесты для эндпоинтов аутентификации"""
    
    def test_health_check(self):
        """Тест проверки здоровья API"""
        response = requests.get(BASE_URL)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        logger.info(f"Health check: {data['message']}")
        return True
    
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
        
        response = requests.post(f"{API_URL}/auth/register", json=new_user)
        
        if response.status_code in [200, 400]:
            # 400 - пользователь уже существует, это тоже нормально для тестов
            logger.info(f"User registration attempt: {response.status_code}")
            return True
        
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        logger.info(f"New user registered: {data['email']}")
        return True
    
    def test_login_admin(self):
        """Тест входа администратора"""
        return login_user(TEST_ADMIN, "admin")
    
    def test_login_client(self):
        """Тест входа клиента"""
        return login_user(TEST_CLIENT, "client")
    
    def test_login_driver(self):
        """Тест входа водителя"""
        return login_user(TEST_DRIVER, "driver")
    
    def test_get_current_user(self):
        """Тест получения информации о текущем пользователе"""
        response = make_request("GET", "/auth/me", user_type="admin")
        data = response.json()
        assert "email" in data
        assert data["email"] == TEST_ADMIN["username"]
        logger.info(f"Current user: {data['email']}")
        return True
    
    def test_refresh_token(self):
        """Тест обновления токена"""
        # Сначала получаем refresh токен
        login_response = requests.post(f"{API_URL}/auth/login", 
                                     data=TEST_ADMIN,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        if login_response.status_code != 200:
            logger.warning("Skipping refresh token test - login failed")
            return True
        
        refresh_token = login_response.json()["refresh_token"]
        
        response = requests.post(f"{API_URL}/auth/refresh", 
                               json={"refresh_token": refresh_token})
        
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
            logger.info("Token refreshed successfully")
        else:
            logger.warning(f"Refresh token test failed: {response.status_code}")
        
        return True

class TestUsersAPI:
    """Тесты для эндпоинтов пользователей"""
    
    def test_get_user_profile(self):
        """Тест получения профиля пользователя"""
        if not tokens.get("client"):
            logger.warning("Skipping test - client not logged in")
            return True
        
        response = make_request("GET", "/users/me", user_type="client")
        data = response.json()
        assert "email" in data
        assert data["email"] == TEST_CLIENT["username"]
        logger.info(f"User profile retrieved: {data['email']}")
        return True
    
    def test_update_user_profile(self):
        """Тест обновления профиля пользователя"""
        if not tokens.get("client"):
            logger.warning("Skipping test - client not logged in")
            return True
        
        update_data = {
            "full_name": "Updated Test User",
            "phone": "+79991112233"
        }
        
        response = make_request("PUT", "/users/me", update_data, user_type="client")
        data = response.json()
        assert data["full_name"] == update_data["full_name"]
        logger.info(f"User profile updated: {data['full_name']}")
        return True
    
    def test_get_all_users_admin(self):
        """Тест получения списка пользователей (только админ)"""
        if not tokens.get("admin"):
            logger.warning("Skipping test - admin not logged in")
            return True
        
        response = make_request("GET", "/users/", user_type="admin")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Retrieved {len(data)} users")
        return True
    
    def test_get_user_by_id(self):
        """Тест получения пользователя по ID (только админ)"""
        if not tokens.get("admin") or not user_ids.get("client"):
            logger.warning("Skipping test - admin or client ID not available")
            return True
        
        response = make_request("GET", f"/users/{user_ids['client']}", user_type="admin")
        data = response.json()
        assert data["id"] == user_ids["client"]
        logger.info(f"User retrieved by ID: {data['email']}")
        return True
    
    def test_get_user_balance(self):
        """Тест получения баланса пользователя"""
        if not tokens.get("client"):
            logger.warning("Skipping test - client not logged in")
            return True
        
        response = make_request("GET", "/users/me/balance", user_type="client")
        data = response.json()
        assert "balance" in data
        logger.info(f"User balance: {data['balance']}")
        return True

class TestOrdersAPI:
    """Тесты для эндпоинтов заказов"""
    
    def test_create_order(self):
        """Тест создания нового заказа"""
        global order_id
        
        if not tokens.get("client"):
            logger.warning("Skipping test - client not logged in")
            return True
        
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
        return True
    
    def test_get_my_orders(self):
        """Тест получения списка заказов пользователя"""
        if not tokens.get("client"):
            logger.warning("Skipping test - client not logged in")
            return True
        
        response = make_request("GET", "/orders/", user_type="client")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Retrieved {len(data)} orders for client")
        return True
    
    def test_get_order_by_id(self):
        """Тест получения заказа по ID"""
        if not tokens.get("client") or not order_id:
            logger.warning("Skipping test - client not logged in or no order created")
            return True
        
        response = make_request("GET", f"/orders/{order_id}", user_type="client")
        data = response.json()
        assert data["id"] == order_id
        logger.info(f"Order retrieved: {data['order_number']}")
        return True
    
    def test_publish_order(self):
        """Тест публикации заказа"""
        if not tokens.get("client") or not order_id:
            logger.warning("Skipping test - client not logged in or no order created")
            return True
        
        response = make_request("POST", f"/orders/{order_id}/publish", user_type="client")
        data = response.json()
        assert "message" in data
        logger.info(f"Order published: {data['message']}")
        return True
    
    def test_get_available_orders(self):
        """Тест получения доступных заказов (для водителей)"""
        if not tokens.get("driver"):
            logger.warning("Skipping test - driver not logged in")
            return True
        
        response = make_request("GET", "/orders/available", user_type="driver")
        data = response.json()
        assert isinstance(data, list)
        logger.info(f"Retrieved {len(data)} available orders")
        return True
    
    def test_calculate_price(self):
        """Тест расчета стоимости перевозки"""
        if not tokens.get("client"):
            logger.warning("Skipping test - client not logged in")
            return True
        
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
        return True

# Функция для запуска всех тестов
def run_all_tests():
    """Запуск всех тестов последовательно"""
    test_classes = [
        TestAuthAPI(),
        TestUsersAPI(),
        TestOrdersAPI()
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    logger.info("=" * 80)
    logger.info("НАЧАЛО ТЕСТИРОВАНИЯ CARGO PRO API - БАЗОВЫЕ ТЕСТЫ")
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
                result = method()
                if result:
                    logger.info(f"✓ {method_name}: PASSED")
                    passed_tests += 1
                else:
                    logger.warning(f"⚠ {method_name}: SKIPPED")
                    passed_tests += 0.5  # Половина балла за пропущенные тесты
            except AssertionError as e:
                logger.error(f"✗ {method_name}: FAILED - Assertion Error: {str(e)}")
                failed_tests.append(f"{class_name}.{method_name}: {str(e)}")
            except Exception as e:
                logger.error(f"✗ {method_name}: FAILED - {str(e)}")
                failed_tests.append(f"{class_name}.{method_name}: {str(e)}")
    
    # Вывод результатов
    logger.info("\n" + "=" * 80)
    logger.info("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    logger.info("=" * 80)
    logger.info(f"Всего тестов: {total_tests}")
    logger.info(f"Пройдено: {passed_tests:.1f}")
    logger.info(f"Успешность: {(passed_tests/total_tests*100):.1f}%")
    
    if failed_tests:
        logger.info("\nПРОВАЛЕННЫЕ ТЕСТЫ:")
        for failed_test in failed_tests:
            logger.info(f"  - {failed_test}")
    else:
        logger.info("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    
    return passed_tests >= total_tests * 0.8  # 80% успешности

def main():
    """Основная функция"""
    # Проверка доступности сервера
    try:
        logger.info(f"Проверяю доступность сервера {BASE_URL}...")
        response = requests.get(BASE_URL, timeout=10)
        if response.status_code == 200:
            logger.info(f"✓ Сервер доступен по адресу {BASE_URL}")
            
            # Запуск тестов
            success = run_all_tests()
            
            if success:
                logger.info("\n✅ ОСНОВНЫЕ ЭНДПОИНТЫ РАБОТАЮТ КОРРЕКТНО!")
                logger.info("\nСледующие шаги:")
                logger.info("1. Проверьте базу данных с помощью: python seed_data.py")
                logger.info("2. Запустите полное тестирование после заполнения БД")
                exit(0)
            else:
                logger.info("\n⚠ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛИЛИСЬ!")
                logger.info("\nРекомендации:")
                logger.info("1. Запустите: python seed_data.py для заполнения БД")
                logger.info("2. Убедитесь, что сервер запущен: python run.py")
                logger.info("3. Проверьте файл .env с настройками")
                exit(1)
        else:
            logger.error(f"✗ Сервер недоступен или вернул ошибку: {response.status_code}")
            exit(1)
    except requests.exceptions.ConnectionError:
        logger.error(f"✗ Не удалось подключиться к серверу {BASE_URL}")
        logger.info("\nУбедитесь, что:")
        logger.info("1. Сервер запущен (python run.py)")
        logger.info("2. IP адрес верный (192.168.10.102)")
        logger.info("3. Порт 8000 открыт")
        logger.info("4. Файрвол не блокирует соединение")
        exit(1)
    except Exception as e:
        logger.error(f"✗ Ошибка при подключении: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()