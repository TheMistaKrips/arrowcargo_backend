"""
Основной файл приложения FastAPI
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os

from .database import engine, Base
from .config import settings
from .routes import (
    auth_router,
    users_router,
    drivers_router,
    orders_router,
    bids_router,
    chat_router,
    track_router,
    admin_router,
    health_router,
    integration_router
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание таблиц базы данных
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Error creating database tables: {e}")

# Создание FastAPI приложения
app = FastAPI(
    title="CargoPro Backend API",
    description="""
    🚚 Backend для платформы грузоперевозок CargoPro
    
    ## Основные возможности:
    
    ### Для клиентов:
    * 📦 Создание и управление заказами
    * 💬 Чат с водителями
    * 📍 Отслеживание груза в реальном времени
    * 💳 Оплата заказов
    
    ### Для водителей:
    * 🚗 Просмотр доступных заказов
    * 💰 Размещение ставок
    * 📍 Отправка геолокации
    * 📱 Мобильное приложение
    
    ### Для администраторов:
    * 👥 Управление пользователями
    * ✅ Верификация водителей
    * 📊 Аналитика и статистика
    * ⚙️ Системные настройки
    
    ## Интеграция:
    * 🌐 Основной сайт
    * 📱 Мобильное приложение
    * 🛠️ Админ-панель
    """,
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для сжатия ответов
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Подключение статических файлов (для загруженных файлов)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Подключение роутеров
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(drivers_router)
app.include_router(orders_router)
app.include_router(bids_router)
app.include_router(chat_router)
app.include_router(track_router)
app.include_router(admin_router)
app.include_router(health_router)
app.include_router(integration_router)

# Основные эндпоинты
@app.get("/")
async def root():
    """
    Корневой эндпоинт
    """
    return {
        "message": "🚚 Добро пожаловать в CargoPro API",
        "version": "1.0.0",
        "docs": "/api/docs" if settings.DEBUG else None,
        "status": "operational",
        "services": {
            "authentication": "active",
            "orders": "active",
            "tracking": "active",
            "chat": "active",
            "payments": "active"
        }
    }

@app.get("/api")
async def api_info():
    """
    Информация о API
    """
    return {
        "name": "CargoPro API",
        "version": "1.0.0",
        "description": "API для платформы грузоперевозок CargoPro",
        "endpoints": {
            "auth": "/api/auth",
            "users": "/api/users",
            "drivers": "/api/drivers",
            "orders": "/api/orders",
            "bids": "/api/bids",
            "admin": "/api/admin",
            "health": "/health",
            "integration": "/api/integration"
        },
        "websockets": {
            "chat": "/ws/chat/{order_id}",
            "tracking": "/ws/track/{driver_id}",
            "notifications": "/ws/notifications"
        }
    }

# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request, call_next):
    """
    Middleware для логирования HTTP запросов
    """
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# Обработка ошибок
@app.exception_handler(404)
async def not_found_exception_handler(request, exc):
    """
    Обработка 404 ошибок
    """
    return {
        "error": "Not Found",
        "message": "Запрошенный ресурс не найден",
        "path": request.url.path
    }

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    """
    Обработка 500 ошибок
    """
    logger.error(f"Internal Server Error: {exc}")
    return {
        "error": "Internal Server Error",
        "message": "Внутренняя ошибка сервера",
        "request_id": request.headers.get("X-Request-ID", "unknown")
    }

# Запуск приложения (для разработки)
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🚀 Starting CargoPro Backend on {settings.HOST}:{settings.PORT}")
    logger.info(f"📊 API Documentation: http://{settings.HOST}:{settings.PORT}/api/docs")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )