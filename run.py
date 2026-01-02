#!/usr/bin/env python3
"""
Запуск сервера CargoPro
"""
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("DEBUG", "True").lower() == "true"
    
    print(f"🚀 Запуск CargoPro Backend на {host}:{port}")
    print(f"📊 Документация API: http://{host}:{port}/api/docs")
    print(f"🔧 Режим разработки: {reload}")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )