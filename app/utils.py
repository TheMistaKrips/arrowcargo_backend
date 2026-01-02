"""
Вспомогательные функции
"""
import math
from typing import Tuple
from datetime import datetime, timedelta
import re
import secrets
import string
from pathlib import Path

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Расчет расстояния между двумя координатами по формуле Хаверсина
    Возвращает расстояние в километрах
    """
    R = 6371  # Радиус Земли в километрах
    
    # Конвертация градусов в радианы
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    # Формула Хаверсина
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return round(distance, 2)

def calculate_price(
    distance_km: float,
    weight: float,
    volume: float,
    base_rate_per_km: float = 15.0,
    weight_rate_per_ton: float = 10.0,
    volume_rate_per_cubic: float = 5.0,
    min_price: float = 500.0
) -> Tuple[float, float, float]:
    """
    Расчет стоимости перевозки
    Возвращает: (финальная_цена, комиссия_платформы, сумма_водителю)
    """
    # Базовая цена за километр
    base_price = max(distance_km * base_rate_per_km, 100)
    
    # Надбавки за вес и объем
    weight_adjustment = weight * weight_rate_per_ton
    volume_adjustment = volume * volume_rate_per_cubic
    
    # Финальная цена
    final_price = base_price + weight_adjustment + volume_adjustment
    final_price = max(final_price, min_price)
    
    # Комиссия платформы (5%)
    platform_fee = final_price * 0.05
    
    # Сумма водителю
    driver_amount = final_price - platform_fee
    
    return round(final_price, 2), round(platform_fee, 2), round(driver_amount, 2)

def validate_phone_number(phone: str) -> bool:
    """Валидация номера телефона"""
    pattern = r'^\+?[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone))

def validate_coordinates(lat: float, lng: float) -> bool:
    """Валидация координат"""
    return -90 <= lat <= 90 and -180 <= lng <= 180

def generate_verification_code(length: int = 6) -> str:
    """Генерация кода верификации"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))

def format_datetime(dt: datetime) -> str:
    """Форматирование даты-времени"""
    return dt.strftime("%d.%m.%Y %H:%M")

def format_price(price: float) -> str:
    """Форматирование цены"""
    return f"{price:,.2f}".replace(",", " ").replace(".", ",") + " ₽"

def calculate_eta(distance_km: float, avg_speed_kmh: float = 60) -> timedelta:
    """Расчет примерного времени прибытия"""
    hours = distance_km / avg_speed_kmh
    return timedelta(hours=hours)

def get_file_extension(filename: str) -> str:
    """Получение расширения файла"""
    return Path(filename).suffix.lower()

def is_allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Проверка расширения файла"""
    return get_file_extension(filename) in allowed_extensions

def calculate_rating(current_rating: float, new_rating: int, total_ratings: int) -> float:
    """Расчет рейтинга"""
    if total_ratings == 0:
        return new_rating
    return round((current_rating * total_ratings + new_rating) / (total_ratings + 1), 1)

def truncate_text(text: str, max_length: int = 100) -> str:
    """Обрезка текста"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def generate_password(length: int = 12) -> str:
    """Генерация безопасного пароля"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Проверка сложности пароля"""
    if len(password) < 8:
        return False, "Пароль должен содержать минимум 8 символов"
    
    if not any(c.isupper() for c in password):
        return False, "Пароль должен содержать хотя бы одну заглавную букву"
    
    if not any(c.islower() for c in password):
        return False, "Пароль должен содержать хотя бы одну строчную букву"
    
    if not any(c.isdigit() for c in password):
        return False, "Пароль должен содержать хотя бы одну цифру"
    
    # Проверка специальных символов не обязательна, но рекомендуется
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        # Возвращаем True, но с рекомендацией
        return True, "Рекомендуется добавить специальные символы (!@#$%^&*)"
    
    return True, "Пароль надежный"

def calculate_driver_score(
    rating: float,
    total_orders: int,
    total_distance: float,
    response_time_avg: float
) -> float:
    """Расчет скора водителя для рекомендаций"""
    # Весовые коэффициенты
    rating_weight = 0.4
    experience_weight = 0.3
    distance_weight = 0.2
    response_weight = 0.1
    
    # Нормализация значений
    rating_score = rating / 5.0
    experience_score = min(total_orders / 100, 1.0)
    distance_score = min(total_distance / 10000, 1.0)
    response_score = 1.0 / (1.0 + response_time_avg / 3600)  # часы в секундах
    
    # Расчет общего скора
    total_score = (
        rating_score * rating_weight +
        experience_score * experience_weight +
        distance_score * distance_weight +
        response_score * response_weight
    )
    
    return round(total_score * 100, 2)