"""
Роутер для проверки здоровья системы
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging
from datetime import datetime
import psutil
import os
import sys

from ..database import get_db
from .. import crud

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """
    Базовая проверка здоровья API
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "CargoPro Backend",
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Детальная проверка здоровья системы
    """
    checks = {
        "api": {"status": "healthy", "message": "API доступен"},
        "database": {"status": "unknown", "message": "Не проверено"},
        "memory": {"status": "unknown", "message": "Не проверено"},
        "disk": {"status": "unknown", "message": "Не проверено"}
    }
    
    # Проверка базы данных
    try:
        db.execute("SELECT 1")
        checks["database"]["status"] = "healthy"
        checks["database"]["message"] = "База данных доступна"
        
        # Проверка количества таблиц (для SQLite)
        try:
            result = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_count = len(result)
            checks["database"]["tables"] = table_count
        except:
            checks["database"]["tables"] = "unknown"
        
    except Exception as e:
        checks["database"]["status"] = "unhealthy"
        checks["database"]["message"] = f"Ошибка базы данных: {str(e)}"
    
    # Проверка памяти
    try:
        memory = psutil.virtual_memory()
        checks["memory"]["status"] = "healthy" if memory.percent < 90 else "warning"
        checks["memory"]["message"] = f"Использовано {memory.percent}% памяти"
        checks["memory"]["details"] = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "percent_used": memory.percent
        }
    except Exception as e:
        checks["memory"]["status"] = "unhealthy"
        checks["memory"]["message"] = f"Ошибка проверки памяти: {str(e)}"
    
    # Проверка диска
    try:
        disk = psutil.disk_usage('/')
        checks["disk"]["status"] = "healthy" if disk.percent < 90 else "warning"
        checks["disk"]["message"] = f"Использовано {disk.percent}% диска"
        checks["disk"]["details"] = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": disk.percent
        }
    except Exception as e:
        checks["disk"]["status"] = "unhealthy"
        checks["disk"]["message"] = f"Ошибка проверки диска: {str(e)}"
    
    # Определение общего статуса
    all_healthy = all(check["status"] in ["healthy", "warning"] for check in checks.values())
    overall_status = "healthy" if all_healthy else "unhealthy"
    
    # Проверка есть ли предупреждения
    has_warnings = any(check["status"] == "warning" for check in checks.values())
    
    return {
        "status": overall_status,
        "has_warnings": has_warnings,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "system_info": {
            "python_version": sys.version,
            "platform": sys.platform,
            "cpu_count": psutil.cpu_count() if hasattr(psutil, 'cpu_count') else "unknown"
        }
    }

@router.get("/health/database")
async def database_health_check(db: Session = Depends(get_db)):
    """
    Проверка здоровья базы данных
    """
    try:
        # Проверка соединения
        db.execute("SELECT 1")
        
        # Получение статистики
        stats = {
            "connection": "ok",
            "tables": {},
            "statistics": {}
        }
        
        # Количество записей в основных таблицах
        tables = ["users", "orders", "bids", "messages", "payments"]
        for table in tables:
            try:
                count = db.execute(f"SELECT COUNT(*) FROM {table}").scalar()
                stats["tables"][table] = count
            except:
                stats["tables"][table] = "error"
        
        # Статистика пользователей
        try:
            user_stats = crud.get_system_stats(db)
            stats["statistics"]["users"] = user_stats
        except:
            stats["statistics"]["users"] = "error"
        
        return {
            "status": "healthy",
            "database": "connected",
            "details": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/health/endpoints")
async def endpoints_health_check():
    """
    Проверка доступности основных эндпоинтов
    """
    endpoints = [
        {"name": "API Documentation", "path": "/api/docs", "method": "GET"},
        {"name": "Authentication", "path": "/api/auth/login", "method": "POST"},
        {"name": "User Profile", "path": "/api/users/me", "method": "GET"},
        {"name": "Orders List", "path": "/api/orders", "method": "GET"},
        {"name": "Admin Statistics", "path": "/api/admin/stats", "method": "GET"}
    ]
    
    return {
        "status": "healthy",
        "endpoints": endpoints,
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Эта проверка только перечисляет основные эндпоинты. Для реальной проверки нужны тестовые запросы."
    }

@router.get("/metrics")
async def system_metrics():
    """
    Метрики системы для мониторинга
    """
    try:
        # Системные метрики
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Сетевые метрики
        net_io = psutil.net_io_counters()
        
        # Метрики процесса
        process = psutil.Process()
        process_memory = process.memory_info()
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu": {
                    "percent": cpu_percent,
                    "cores": psutil.cpu_count(),
                    "cores_logical": psutil.cpu_count(logical=True)
                },
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "percent": memory.percent
                },
                "disk": {
                    "total_bytes": disk.total,
                    "free_bytes": disk.free,
                    "used_bytes": disk.used,
                    "percent": disk.percent
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                }
            },
            "process": {
                "pid": process.pid,
                "name": process.name(),
                "memory_rss_bytes": process_memory.rss,
                "memory_vms_bytes": process_memory.vms,
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads()
            }
        }
        
        return metrics
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "status": "partial"
        }

@router.get("/version")
async def version_info():
    """
    Информация о версии приложения
    """
    return {
        "service": "CargoPro Backend",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "build_date": "2024-01-01",
        "api_version": "v1",
        "features": [
            "authentication",
            "order_management",
            "driver_tracking",
            "real_time_chat",
            "payment_processing",
            "admin_panel"
        ]
    }