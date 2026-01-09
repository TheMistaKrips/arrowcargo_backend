"""
Работа с файловым хранилищем - ОБНОВЛЕННЫЙ ВАРИАНТ
"""
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from fastapi import UploadFile, HTTPException, BackgroundTasks
import shutil
from PIL import Image
import magic
from datetime import datetime
import asyncio

from .config import settings
from .utils import is_allowed_file

class FileStorage:
    def __init__(self):
        self.base_dir = Path(settings.UPLOAD_DIR)
        self.max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Конвертируем в байты
        
        # Разрешенные типы файлов
        self.allowed_extensions = {
            # Изображения
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff',
            # Документы
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.rtf',
            # Архивы
            '.zip', '.rar', '.7z',
            # Прочие
            '.json', '.xml'
        }
        
        # MIME типы
        self.allowed_mime_types = {
            # Изображения
            'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 
            'image/webp', 'image/tiff',
            # Документы
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain', 'text/rtf',
            # Архивы
            'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
            # Прочие
            'application/json', 'application/xml', 'text/xml'
        }
        
        # Создаем структуру директорий
        self._create_directories()
    
    def _create_directories(self):
        """Создание структуры директорий"""
        directories = [
            "drivers",
            "orders",
            "cargo",
            "contracts",
            "company",
            "temp"
        ]
        
        for directory in directories:
            dir_path = self.base_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _generate_filename(self, original_filename: str, prefix: str = "") -> str:
        """Генерация уникального имени файла"""
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if prefix:
            return f"{prefix}_{timestamp}_{unique_id}{ext}"
        return f"{timestamp}_{unique_id}{ext}"
    
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
            return False, f"Размер файла превышает максимально допустимый ({settings.MAX_FILE_SIZE_MB}MB)"
        
        # Проверка расширения
        if not is_allowed_file(file.filename, self.allowed_extensions):
            return False, f"Тип файла не разрешен. Разрешенные типы: {', '.join(self.allowed_extensions)}"
        
        # Сохраняем временный файл для проверки MIME типа
        temp_path = self.base_dir / "temp" / f"temp_{uuid.uuid4()}.tmp"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Проверка MIME типа
            mime_type = self._get_mime_type(str(temp_path))
            if mime_type not in self.allowed_mime_types:
                return False, f"MIME тип {mime_type} не разрешен"
            
            # Дополнительная проверка для изображений
            if mime_type.startswith('image/'):
                try:
                    with Image.open(temp_path) as img:
                        img.verify()  # Проверка целостности изображения
                except Exception as e:
                    return False, f"Неверный формат изображения: {str(e)}"
            
            # Проверка PDF файлов
            if mime_type == 'application/pdf':
                try:
                    # Простая проверка PDF (может быть расширена)
                    with open(temp_path, 'rb') as f:
                        header = f.read(5)
                        if header != b'%PDF-':
                            return False, "Неверный формат PDF файла"
                except:
                    pass
        
        finally:
            # Удаляем временный файл
            if temp_path.exists():
                temp_path.unlink()
            
            # Возвращаем указатель файла в начало
            file.file.seek(0)
        
        return True, "Файл прошел проверку"
    
    async def save_file(self, file: UploadFile, subdirectory: str, user_id: int = None, 
                       prefix: str = "", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Сохранение файла с метаданными
        Возвращает словарь с информацией о файле
        """
        # Валидация
        is_valid, message = self.validate_file(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        # Создание директории
        if user_id:
            user_dir = self.base_dir / subdirectory / str(user_id)
        else:
            user_dir = self.base_dir / subdirectory
        
        # Добавляем дату в путь
        date_path = datetime.now().strftime("%Y/%m/%d")
        full_dir = user_dir / date_path
        full_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерация имени файла
        filename = self._generate_filename(file.filename, prefix)
        file_path = full_dir / filename
        
        # Сохранение файла
        try:
            with open(file_path, "wb") as buffer:
                # Для больших файлов читаем частями
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    buffer.write(chunk)
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Ошибка сохранения файла: {str(e)}"
            )
        
        # Получаем информацию о файле
        file_size = os.path.getsize(file_path)
        file_ext = Path(file.filename).suffix.lower()
        mime_type = self._get_mime_type(str(file_path))
        
        # Собираем метаданные
        file_info = {
            "original_filename": file.filename,
            "saved_filename": filename,
            "relative_path": str(file_path.relative_to(self.base_dir)),
            "absolute_path": str(file_path),
            "file_size": file_size,
            "file_extension": file_ext,
            "mime_type": mime_type,
            "upload_date": datetime.now().isoformat(),
            "user_id": user_id,
            "subdirectory": subdirectory,
            "metadata": metadata or {}
        }
        
        # Для изображений получаем размеры
        if mime_type.startswith('image/'):
            try:
                with Image.open(file_path) as img:
                    file_info.update({
                        "width": img.width,
                        "height": img.height,
                        "format": img.format
                    })
            except Exception as e:
                print(f"Error getting image info: {e}")
        
        return file_info
    
    async def save_cargo_document(self, file: UploadFile, user_id: int, 
                                 order_id: int, document_type: str, 
                                 description: str = None) -> Dict[str, Any]:
        """Сохранение документа на груз"""
        metadata = {
            "document_type": document_type,
            "order_id": order_id,
            "description": description,
            "category": "cargo"
        }
        
        return await self.save_file(
            file=file,
            subdirectory=f"cargo/{order_id}",
            user_id=user_id,
            prefix=f"cargo_{document_type}",
            metadata=metadata
        )
    
    async def save_driver_document(self, file: UploadFile, driver_id: int, 
                                  document_type: str) -> Dict[str, Any]:
        """Сохранение документа водителя"""
        metadata = {
            "document_type": document_type,
            "category": "driver"
        }
        
        return await self.save_file(
            file=file,
            subdirectory=f"drivers/{document_type}",
            user_id=driver_id,
            prefix=f"driver_{document_type}",
            metadata=metadata
        )
    
    async def save_order_image(self, file: UploadFile, user_id: int, 
                              order_id: int) -> Dict[str, Any]:
        """Сохранение изображения груза"""
        metadata = {
            "order_id": order_id,
            "category": "order_image"
        }
        
        return await self.save_file(
            file=file,
            subdirectory=f"orders/{order_id}/images",
            user_id=user_id,
            prefix="order_image",
            metadata=metadata
        )
    
    async def save_contract_pdf(self, content: bytes, contract_id: int, 
                               order_id: int) -> Dict[str, Any]:
        """Сохранение PDF договора"""
        # Генерация имени файла
        filename = f"contract_{contract_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Создание директории
        contract_dir = self.base_dir / "contracts" / str(order_id)
        contract_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = contract_dir / filename
        
        # Сохранение файла
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        metadata = {
            "contract_id": contract_id,
            "order_id": order_id,
            "category": "contract"
        }
        
        return {
            "original_filename": filename,
            "saved_filename": filename,
            "relative_path": str(file_path.relative_to(self.base_dir)),
            "absolute_path": str(file_path),
            "file_size": len(content),
            "file_extension": ".pdf",
            "mime_type": "application/pdf",
            "upload_date": datetime.now().isoformat(),
            "metadata": metadata
        }
    
    async def save_company_document(self, file: UploadFile, company_id: int, 
                                   document_type: str) -> Dict[str, Any]:
        """Сохранение документа компании"""
        metadata = {
            "document_type": document_type,
            "company_id": company_id,
            "category": "company"
        }
        
        return await self.save_file(
            file=file,
            subdirectory=f"company/{document_type}",
            user_id=company_id,
            prefix=f"company_{document_type}",
            metadata=metadata
        )
    
    def get_file_path(self, relative_path: str) -> Optional[Path]:
        """Получение полного пути к файлу"""
        file_path = self.base_dir / relative_path
        if file_path.exists() and file_path.is_file():
            return file_path
        return None
    
    async def get_file_info(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """Получение информации о файле"""
        file_path = self.get_file_path(relative_path)
        if not file_path:
            return None
        
        try:
            file_info = {
                "relative_path": relative_path,
                "absolute_path": str(file_path),
                "file_size": os.path.getsize(file_path),
                "created_at": datetime.fromtimestamp(os.path.getctime(file_path)).isoformat(),
                "modified_at": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                "mime_type": self._get_mime_type(str(file_path))
            }
            
            # Для изображений добавляем размеры
            if file_info["mime_type"].startswith('image/'):
                try:
                    with Image.open(file_path) as img:
                        file_info.update({
                            "width": img.width,
                            "height": img.height,
                            "format": img.format
                        })
                except:
                    pass
            
            return file_info
            
        except Exception as e:
            print(f"Error getting file info: {e}")
            return None
    
    async def delete_file(self, relative_path: str) -> Tuple[bool, str]:
        """Удаление файла"""
        file_path = self.get_file_path(relative_path)
        if not file_path:
            return False, "Файл не найден"
        
        try:
            # Делаем резервную копию перед удалением (опционально)
            backup_dir = self.base_dir / "deleted"
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_path.name}"
            shutil.copy2(file_path, backup_path)
            
            # Удаляем основной файл
            file_path.unlink()
            
            # Удаляем пустые родительские директории
            self._cleanup_empty_directories(file_path.parent)
            
            return True, "Файл успешно удален"
            
        except Exception as e:
            return False, f"Ошибка удаления файла: {str(e)}"
    
    def _cleanup_empty_directories(self, directory: Path):
        """Рекурсивное удаление пустых директорий"""
        try:
            # Проверяем, пуста ли директория
            if directory.exists() and directory.is_dir():
                if not any(directory.iterdir()):
                    # Удаляем пустую директорию
                    directory.rmdir()
                    # Проверяем родительскую директорию
                    self._cleanup_empty_directories(directory.parent)
        except:
            pass
    
    async def list_files(self, subdirectory: str, user_id: int = None, 
                        file_type: str = None) -> List[Dict[str, Any]]:
        """Получение списка файлов в директории"""
        if user_id:
            base_dir = self.base_dir / subdirectory / str(user_id)
        else:
            base_dir = self.base_dir / subdirectory
        
        if not base_dir.exists():
            return []
        
        files_info = []
        
        # Рекурсивный обход директории
        for file_path in base_dir.rglob("*"):
            if file_path.is_file():
                try:
                    # Фильтрация по типу файла
                    if file_type and not file_path.suffix.lower() == file_type:
                        continue
                    
                    file_info = {
                        "filename": file_path.name,
                        "relative_path": str(file_path.relative_to(self.base_dir)),
                        "absolute_path": str(file_path),
                        "file_size": os.path.getsize(file_path),
                        "created_at": datetime.fromtimestamp(os.path.getctime(file_path)).isoformat(),
                        "modified_at": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                        "mime_type": self._get_mime_type(str(file_path))
                    }
                    
                    files_info.append(file_info)
                    
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
        
        # Сортировка по дате изменения (новые сверху)
        files_info.sort(key=lambda x: x["modified_at"], reverse=True)
        
        return files_info
    
    async def compress_files(self, file_paths: List[str], output_filename: str) -> Optional[str]:
        """Создание архива из нескольких файлов"""
        try:
            import zipfile
            
            # Создаем временный архив
            temp_dir = self.base_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            archive_path = temp_dir / f"{output_filename}.zip"
            
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for relative_path in file_paths:
                    file_path = self.get_file_path(relative_path)
                    if file_path and file_path.exists():
                        # Добавляем файл в архив с сохранением структуры директорий
                        arcname = relative_path.replace('/', '_').replace('\\', '_')
                        zipf.write(file_path, arcname)
            
            return str(archive_path.relative_to(self.base_dir))
            
        except Exception as e:
            print(f"Error creating archive: {e}")
            return None
    
    async def generate_preview(self, relative_path: str, 
                              width: int = 300, height: int = 200) -> Optional[str]:
        """Генерация превью для изображений"""
        file_path = self.get_file_path(relative_path)
        if not file_path:
            return None
        
        try:
            # Проверяем, является ли файл изображением
            mime_type = self._get_mime_type(str(file_path))
            if not mime_type.startswith('image/'):
                return None
            
            # Создаем превью
            with Image.open(file_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Изменяем размер
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                
                # Сохраняем превью
                preview_dir = self.base_dir / "previews"
                preview_dir.mkdir(exist_ok=True)
                
                preview_filename = f"preview_{file_path.stem}.jpg"
                preview_path = preview_dir / preview_filename
                
                img.save(preview_path, 'JPEG', quality=85)
                
                return str(preview_path.relative_to(self.base_dir))
                
        except Exception as e:
            print(f"Error generating preview: {e}")
            return None
    
    async def cleanup_old_files(self, days: int = 30):
        """Очистка старых временных файлов"""
        temp_dir = self.base_dir / "temp"
        if not temp_dir.exists():
            return
        
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for file_path in temp_dir.rglob("*"):
            if file_path.is_file():
                try:
                    if os.path.getmtime(file_path) < cutoff_date:
                        file_path.unlink()
                except:
                    pass
        
        # Очистка пустых директорий
        self._cleanup_empty_directories(temp_dir)

# Глобальный экземпляр хранилища
file_storage = FileStorage()