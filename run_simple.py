# run_simple.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CargoPro Test")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "CargoPro API работает!"}

@app.post("/api/auth/login")
async def login(username: str, password: str):
    # Простой тест логина
    if username == "admin@cargopro.com" and password == "admin123":
        return {
            "access_token": "test_token_123",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "email": "admin@cargopro.com",
                "role": "admin",
                "full_name": "Администратор"
            }
        }
    return {"error": "Invalid credentials"}

if __name__ == "__main__":
    print("🚀 Запуск тестового сервера на http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)