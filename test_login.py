# test_login.py
import requests

def test_login():
    """Тест логина через API"""
    print("🔍 Тестирование логина через API...")
    
    test_cases = [
        ("admin@cargopro.com", "admin123", "Администратор"),
        ("client1@example.com", "client1", "Клиент"),
        ("driver1@example.com", "driver1", "Водитель"),
    ]
    
    for email, password, role in test_cases:
        print(f"\nПопытка входа: {email} ({role})")
        
        try:
            response = requests.post(
                'http://localhost:8000/api/auth/login',
                data={'username': email, 'password': password},
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Успешно!")
                print(f"   Токен: {data['access_token'][:50]}...")
                print(f"   Роль: {data['user']['role']}")
                print(f"   Email: {data['user']['email']}")
            else:
                print(f"❌ Ошибка {response.status_code}")
                print(f"   Ответ: {response.text}")
                
        except Exception as e:
            print(f"❌ Исключение: {e}")

if __name__ == "__main__":
    # Проверяем доступность сервера
    try:
        response = requests.get('http://localhost:8000/', timeout=5)
        print(f"🌐 Сервер доступен: {response.status_code}")
        test_login()
    except:
        print("❌ Сервер не запущен. Сначала запустите: python run.py")