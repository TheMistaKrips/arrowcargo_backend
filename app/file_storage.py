"""
Работа с файловым хранилищем
"""
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
import shutil
from PIL import Image
import magic

from .config import settings
from .utils import is_allowed_file

class FileStorage:
    def __init__(self):
        self.base_dir = Path(settings.UPLOAD_DIR)
        self.max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Конвертируем в байты
        
        # Разрешенные типы файлов
        self.allowed_extensions = {
            '.jpg', '.jpeg', '.png', '.gif',  # Изображения
            '.pdf', '.doc', '.docx',          # Документы
        }
        
        # MIME типы
        self.allowed_mime_types = {
            'image/jpeg', 'image/png', 'image/gif',
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
    
    def _generate_filename(self, original_filename: str) -> str:
        """Генерация уникального имени файла"""
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex
        return f"{unique_id}{ext}"
    
    def _get_mime_type(self, file_path: str) -> str:
        """Определение MIME типа файла"""
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    
    def validate_file(self, file: UploadFile) -> Tuple[bool, str]:
        """Валидация файла"""
        # Проверка размера
        file.file.seek(0, 2)  # Перемещаемся в конец файла
        file_size = file.file.tell()
        file.file.seek(0)  # Возвращаемся в начало
        
        if file_size > self.max_size:
            return False, f"File size exceeds maximum allowed size ({settings.MAX_FILE_SIZE_MB}MB)"
        
        # Проверка расширения
        if not is_allowed_file(file.filename, self.allowed_extensions):
            return False, f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}"
        
        # Сохраняем временный файл для проверки MIME типа
        temp_path = self.base_dir / f"temp_{uuid.uuid4()}.tmp"
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Проверка MIME типа
            mime_type = self._get_mime_type(str(temp_path))
            if mime_type not in self.allowed_mime_types:
                return False, f"MIME type {mime_type} not allowed"
            
            # Для изображений дополнительная проверка
            if mime_type.startswith('image/'):
                try:
                    with Image.open(temp_path) as img:
                        img.verify()  # Проверка целостности изображения
                except Exception as e:
                    return False, f"Invalid image file: {str(e)}"
        
        finally:
            # Удаляем временный файл
            if temp_path.exists():
                temp_path.unlink()
            
            # Возвращаем указатель файла в начало
            file.file.seek(0)
        
        return True, "File is valid"
    
    async def save_file(self, file: UploadFile, subdirectory: str, user_id: int) -> str:
        """
        Сохранение файла
        Возвращает относительный путь к файлу
        """
        # Валидация
        is_valid, message = self.validate_file(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        # Создание директории
        user_dir = self.base_dir / subdirectory / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерация имени файла
        filename = self._generate_filename(file.filename)
        file_path = user_dir / filename
        
        # Сохранение файла
        try:
            with open(file_path, "wb") as buffer:
                # Для больших файлов читаем частями
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    buffer.write(chunk)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
        
        # Возвращаем относительный путь
        relative_path = file_path.relative_to(self.base_dir)
        return str(relative_path)
    
    def get_file_path(self, relative_path: str) -> Optional[Path]:
        """Получение полного пути к файлу"""
        file_path = self.base_dir / relative_path
        if file_path.exists() and file_path.is_file():
            return file_path
        return None
    
    def delete_file(self, relative_path: str) -> bool:
        """Удаление файла"""
        file_path = self.get_file_path(relative_path)
        if file_path:
            try:
                file_path.unlink()
                return True
            except:
                return False
        return False
    
    def save_driver_document(
        self,
        file: UploadFile,
        user_id: int,
        document_type: str
    ) -> str:
        """Сохранение документа водителя"""
        return self.save_file(file, f"drivers/{document_type}", user_id)
    
    def save_order_image(
        self,
        file: UploadFile,
        user_id: int,
        order_id: int
    ) -> str:
        """Сохранение изображения груза"""
        return self.save_file(file, f"orders/{order_id}/images", user_id)

# Глобальный экземпляр хранилища
file_storage = FileStorage()