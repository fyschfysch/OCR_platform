"""
Обработчики документов и менеджеры координат для Streamlit приложения
С исправленными импортами и типизацией
"""
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance
import io
from typing import List, Tuple, Dict, Optional, Any
import json
from datetime import datetime

class SimpleImageProcessor:
    """
    Упрощенный обработчик изображений для Streamlit с строгим масштабированием
    """
    
    def __init__(self, max_dimension: Optional[int] = None):
        """
        Инициализация обработчика
        Args:
            max_dimension: Максимальный размер. Если None, то 1200px по умолчанию
        """
        self.max_dimension = max_dimension if max_dimension and max_dimension <= 3000 else 1200
    
    def convert_pdf_to_images(self, pdf_bytes: bytes) -> List[Image.Image]:
        """
        Конвертация PDF в список PIL изображений
        """
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            images = []
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # Увеличиваем разрешение для лучшего качества OCR
                mat = fitz.Matrix(2.0, 2.0)  # 2x масштабирование
                pix = page.get_pixmap(matrix=mat)
                
                # Конвертация в PIL Image
                img_data = pix.pil_tobytes(format="PNG")
                img = Image.open(io.BytesIO(img_data))
                
                # Масштабирование если нужно
                if self.max_dimension and max(img.size) > self.max_dimension:
                    img = self._resize_if_needed(img)
                
                images.append(img)
            
            pdf_document.close()
            return images
            
        except ImportError as e:
            raise ImportError("PyMuPDF не установлен. Установите командой: pip install PyMuPDF") from e
        except Exception as e:
            raise Exception(f"Ошибка обработки PDF: {e}") from e
    
    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        """Масштабирование изображения до MAX_DIMENSION если больше"""
        width, height = img.size
        max_current = max(width, height)
        
        if max_current > self.max_dimension:
            scale_factor = self.max_dimension / max_current
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            print(f"🔧 Масштабирование: {width}x{height} -> {new_width}x{new_height}")
            return img.resize((new_width, new_height), Image.LANCZOS)
        
        print(f"✅ Размер изображения корректный: {width}x{height}")
        return img
    
    def enhance_image(self, img: Image.Image) -> Image.Image:
        """Улучшение изображения для OCR"""
        # Размер изображения не должен превышать max_dimension по любой стороне
        if max(img.size) > self.max_dimension:
            img = self._resize_if_needed(img)
        
        # Улучшение контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        
        # Улучшение резкости
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.1)
        
        return img
    
    def rotate_image(self, img: Image.Image, angle: int) -> Image.Image:
        """Поворот изображения"""
        if angle % 360 == 0:
            return img
        
        # Поворот с белой заливкой
        return img.rotate(-angle, expand=True, fillcolor='white')
    
    def get_image_info(self, img: Image.Image) -> Dict[str, Any]:
        """Получение информации об изображении"""
        return {
            'size': img.size,
            'width': img.width,
            'height': img.height,
            'mode': img.mode,
            'format': img.format,
            'max_dimension': max(img.size),
            'is_properly_scaled': max(img.size) <= self.max_dimension
        }

class CoordinateManager:
    """Менеджер координат полей документа"""
    
    def __init__(self):
        # Дефолтные координаты для различных полей
        self.default_coords = {
            'full_name': [220, 446, 833, 496],
            'series_and_number': [220, 800, 420, 830],
            'registration_number': [700, 800, 900, 830],
            'issue_date': [600, 880, 800, 910]
        }
    
    def validate_coordinates(self, coords: Tuple[int, int, int, int], 
                           image_size: Tuple[int, int]) -> bool:
        """Валидация координат относительно размера изображения"""
        if len(coords) != 4:
            return False
        
        x1, y1, x2, y2 = coords
        width, height = image_size
        
        # Проверка логичности координат
        if x1 >= x2 or y1 >= y2:
            return False
        
        # Проверка границ изображения
        if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
            return False
        
        # Минимальный размер поля
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            return False
        
        return True
    
    def normalize_coordinates(self, coords: Tuple[int, int, int, int], 
                            image_size: Tuple[int, int]) -> Tuple[int, int, int, int]:
        """Нормализация координат в пределах изображения"""
        x1, y1, x2, y2 = coords
        width, height = image_size
        
        # Ограничение координат размерами изображения
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(x1 + 1, min(x2, width))
        y2 = max(y1 + 1, min(y2, height))
        
        return (x1, y1, x2, y2)

class ResultsManager:
    """Менеджер результатов OCR с улучшенным форматированием"""
    
    def __init__(self):
        # Fallback описания полей
        self.field_descriptions = {
            'full_name': 'ФИО получателя документа',
            'series': 'Серия документа',
            'number': 'Номер документа',
            'registration_number': 'Регистрационный номер',
            'issue_date': 'Дата выдачи документа'
        }
        
        # Попытка импорта функции описаний полей
        self.get_description = self._get_field_description
    
    def _get_field_description(self, field_name: str) -> str:
        """Получение описания поля"""
        try:
            # Попытка импорта функции из config
            from .config import get_field_description
            return get_field_description(field_name)
        except ImportError:
            # Использование fallback описаний
            return self.field_descriptions.get(field_name, field_name)
    
    def format_results_for_display(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Форматирование результатов OCR для отображения"""
        formatted = []
        uncertainties = results.get('uncertainties', [])
        
        for field_name, value in results.items():
            if field_name.startswith('uncertain_'):
                continue  # Пропускаем служебные поля
            
            uncertain = any(u == field_name for u in uncertainties)
            
            formatted.append({
                'field_name': field_name,
                'description': self.get_description(field_name),
                'value': str(value),
                'uncertain': uncertain,
                'confidence': 'low' if uncertain else 'high'
            })
        
        return formatted
    
    def export_results_json(self, results: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Экспорт результатов в JSON формат"""
        export_data = {
            'export_info': {
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
                'filename': filename
            },
            'results': results
        }
        
        return json.dumps(export_data, ensure_ascii=False, indent=2)
    
    def get_statistics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Получение статистики по результатам OCR"""
        total_fields = len([k for k in results.keys() if not k.startswith('uncertain_')])
        empty_fields = len([k for k, v in results.items() 
                          if not k.startswith('uncertain_') and not str(v).strip()])
        uncertainties = len(results.get('uncertainties', []))
        
        return {
            'total_fields': total_fields,
            'successful_fields': total_fields - empty_fields,
            'empty_fields': empty_fields, 
            'uncertain_fields': uncertainties,
            'success_rate': ((total_fields - empty_fields) / total_fields * 100) if total_fields > 0 else 0,
            'confidence_rate': ((total_fields - uncertainties) / total_fields * 100) if total_fields > 0 else 0
        }
