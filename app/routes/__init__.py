"""
Инициализация роутеров
"""
from .auth import router as auth_router
from .users import router as users_router
from .drivers import router as drivers_router
from .orders import router as orders_router
from .bids import router as bids_router
from .chat import router as chat_router
from .track import router as track_router
from .admin import router as admin_router
from .health import router as health_router
from .integration import router as integration_router

__all__ = [
    "auth_router",
    "users_router",
    "drivers_router",
    "orders_router",
    "bids_router",
    "chat_router",
    "track_router",
    "admin_router",
    "health_router",
    "integration_router"
]