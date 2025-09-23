"""
OCR движок БЕЗ OpenCV для облачного деплоя
"""
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from typing import Dict, Any, List, Optional, Tuple
import re

# УБРАНО: import cv2, import numpy as np

from .config import DocumentConfig
from .parsers import OneTParsers, RosNouParsers, FinUnivParsers, CommonParsers, UncertaintyEngine

class OCREngine:
    """OCR движок на базе Tesseract БЕЗ OpenCV"""
    
    def __init__(self, tesseract_path: str = None):
        if tesseract_path:
            try:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            except:
                pass  # Игнорируем ошибки в облаке
        self.verify_tesseract()
    
    def verify_tesseract(self):
        """Проверка Tesseract"""
        try:
            version = pytesseract.get_tesseract_version()
            print(f"✅ Tesseract OCR готов, версия: {version}")
        except Exception as e:
            print(f"⚠️ Tesseract недоступен: {e}")
            # НЕ raise - просто предупреждение
    
    def preprocess_region(self, region: Image.Image, ocr_params: Dict, field_name: str) -> Image.Image:
        """Предобработка региона БЕЗ OpenCV"""
        scale_factor = ocr_params.get('scale_factor', 3)
        contrast_boost = ocr_params.get('contrast_boost', 1.5)
        
        # Масштабирование
        if scale_factor > 1:
            width, height = region.size
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            region = region.resize((new_width, new_height), Image.LANCZOS)
        
        # Улучшение контраста
        if contrast_boost > 1:
            enhancer = ImageEnhance.Contrast(region)
            region = enhancer.enhance(contrast_boost)
        
        # Дополнительная резкость
        if field_name in ['series_and_number', 'full_name']:
            enhancer = ImageEnhance.Sharpness(region)
            region = enhancer.enhance(1.3)
        
        return region
    
    def remove_lines_from_region(self, img: Image.Image, aggressive: bool = False) -> Image.Image:
        """Упрощенная версия БЕЗ OpenCV"""
        if aggressive:
            # Простое размытие вместо сложной OpenCV обработки
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
        return img
    
    # Остальные методы остаются без изменений...
    def extract_text_from_region(self, image: Image.Image, box: List[int],
                                ocr_params: Dict[str, Any] = None, field_name: str = "") -> str:
        """Извлечение текста БЕЗ OpenCV"""
        try:
            if not box or len(box) != 4:
                return ""
            
            x1, y1, x2, y2 = box
            
            # Валидация координат
            img_width, img_height = image.size
            x1 = max(0, min(x1, img_width))
            y1 = max(0, min(y1, img_height))
            x2 = max(x1 + 1, min(x2, img_width))
            y2 = max(y1 + 1, min(y2, img_height))
            
            # Извлечение региона
            region = image.crop((x1, y1, x2, y2))
            
            # Предобработка БЕЗ OpenCV
            if ocr_params:
                region = self.preprocess_region(region, ocr_params, field_name)
            
            # Простая обработка
            if field_name in ['registration_number']:
                region = self.remove_lines_from_region(region, aggressive=True)
            
            # Конвертация в оттенки серого
            region = region.convert('L')
            
            # Медианный фильтр
            region = region.filter(ImageFilter.MedianFilter(size=3))
            
            # PSM и язык
            psm = self.get_psm_for_field(field_name, ocr_params)
            lang = self.get_language_for_field(field_name)
            
            # OCR
            config_str = f'--oem 3 --psm {psm}'
            text = pytesseract.image_to_string(region, lang=lang, config=config_str)
            return text.strip()
            
        except Exception as e:
            print(f"❌ Ошибка OCR для поля {field_name}: {e}")
            return f"Ошибка OCR: {field_name}"
    
    # Остальные методы без изменений
    def get_psm_for_field(self, field_name: str, ocr_params: Dict = None) -> int:
        if ocr_params and 'psm_configs' in ocr_params:
            return ocr_params['psm_configs'].get(field_name, 7)
        
        if field_name == 'full_name':
            return 7
        elif field_name == 'issue_date':
            return 6
        elif field_name == 'series_and_number':
            return 7
        elif field_name == 'registration_number':
            return 8
        else:
            return 7
    
    def get_language_for_field(self, field_name: str) -> str:
        if field_name == 'full_name':
            return 'rus'
        elif field_name == 'series_and_number':
            return 'rus+eng'
        elif field_name == 'registration_number':
            return 'rus+eng'
        elif field_name == 'issue_date':
            return 'rus'
        else:
            return 'rus+eng'
    
    def process_document_with_parser(self, image: Image.Image, config: DocumentConfig) -> Dict[str, Any]:
        """Обработка документа БЕЗ OpenCV"""
        results = {}
        uncertainty_engine = UncertaintyEngine(config.organization)
        
        print(f"🔍 Обработка документа: {config.name}")
        
        for field_name, box in config.fields.items():
            print(f"📋 Обрабатываем поле: {field_name}")
            
            # Извлечение текста
            raw_text = self.extract_text_from_region(image, box, config.ocr_params, field_name)
            print(f"🔤 OCR текст: '{raw_text}'")
            
            if not raw_text.strip():
                if field_name == 'series_and_number':
                    results['series'] = ""
                    results['number'] = ""
                    results['uncertain_series'] = True
                    results['uncertain_number'] = True
                else:
                    results[field_name] = ""
                    results[f'uncertain_{field_name}'] = True
                continue
            
            # Применение парсера
            if field_name == 'series_and_number':
                if config.patterns and 'series_and_number' in config.patterns:
                    parser = config.patterns['series_and_number']
                    try:
                        parsed_result = parser(raw_text)
                        if len(parsed_result) == 3:
                            series, number, uncertain = parsed_result
                            results['series'] = series
                            results['number'] = number
                            
                            if uncertain:
                                results['uncertain_series'] = True
                                results['uncertain_number'] = True
                        else:
                            series, number = self._parse_series_number_fallback(raw_text)
                            results['series'] = series
                            results['number'] = number
                            results['uncertain_series'] = True
                            results['uncertain_number'] = True
                    except Exception as e:
                        print(f"❌ Ошибка парсера: {e}")
                        series, number = self._parse_series_number_fallback(raw_text)
                        results['series'] = series
                        results['number'] = number
                        results['uncertain_series'] = True
                        results['uncertain_number'] = True
                else:
                    series, number = self._parse_series_number_fallback(raw_text)
                    results['series'] = series
                    results['number'] = number
                    results['uncertain_series'] = True
                    results['uncertain_number'] = True
            else:
                # Обычные поля
                if config.patterns and field_name in config.patterns:
                    parser = config.patterns[field_name]
                    try:
                        parsed_result = parser(raw_text)
                        if isinstance(parsed_result, tuple) and len(parsed_result) == 2:
                            value, uncertain = parsed_result
                            results[field_name] = value
                            if uncertain:
                                results[f'uncertain_{field_name}'] = True
                        else:
                            results[field_name] = str(parsed_result)
                            results[f'uncertain_{field_name}'] = True
                    except Exception as e:
                        print(f"❌ Ошибка парсера для {field_name}: {e}")
                        results[field_name] = raw_text
                        results[f'uncertain_{field_name}'] = True
                else:
                    results[field_name] = raw_text
                    results[f'uncertain_{field_name}'] = True
        
        return results
    
    def _parse_series_number_fallback(self, text: str) -> Tuple[str, str]:
        """Fallback парсер БЕЗ regex зависимостей от numpy"""
        patterns = [
            r'(\d{2})\s*(\d{6})',  # 1T: "02 123456"
            r'(\d{2})-?\w?\s*(\d{8,10})',  # ROSNOU: "12-Д 2024000010"
            r'(\d{2,4})\s+(\d{8,})',  # FinUniv: "7733 01156696"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1), match.group(2)
        
        parts = re.split(r'[\s\-]+', text.strip())
        if len(parts) >= 2:
            return parts[0], parts[1]
        
        return "", text.strip()

# Остальная часть файла остается той же
class DocumentProcessor:
    def __init__(self, tesseract_path: str = None):
        self.ocr_engine = OCREngine(tesseract_path)
    
    def process_single_image(self, image: Image.Image, config: DocumentConfig, 
                           rotation_angle: int = 0) -> Dict[str, Any]:
        try:
            if rotation_angle != 0:
                image = image.rotate(-rotation_angle, expand=True, fillcolor='white')
            
            results = self.ocr_engine.process_document_with_parser(image, config)
            return results
            
        except Exception as e:
            print(f"❌ Ошибка обработки: {e}")
            return {
                'full_name': 'Ошибка обработки',
                'series': '00',
                'number': '000000',
                'registration_number': '000000',
                'issue_date': '2024-01-01'
            }
    
    def extract_fields(self, img: Image.Image, config: DocumentConfig, 
                      uncertainty_engine) -> Dict[str, Any]:
        return self.process_single_image(img, config)