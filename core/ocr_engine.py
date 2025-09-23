"""
OCR движок с обновленной логикой для series_and_number и отслеживанием неопределённости
"""
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np
import re

from .config import DocumentConfig
from .parsers import OneTParsers, RosNouParsers, FinUnivParsers, CommonParsers, UncertaintyEngine

class OCREngine:
    """OCR движок на базе Tesseract с интеграцией парсеров"""
    
    def __init__(self, tesseract_path: str = None):
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        self.verify_tesseract()
    
    def verify_tesseract(self):
        """Проверка Tesseract"""
        try:
            version = pytesseract.get_tesseract_version()
            print(f"✅ Tesseract OCR готов, версия: {version}")
        except Exception as e:
            print(f"❌ Tesseract недоступен: {e}")
            raise RuntimeError("Tesseract OCR недоступен")
    
    def preprocess_region(self, region: Image.Image, ocr_params: Dict, field_name: str) -> Image.Image:
        """Предобработка региона перед OCR"""
        scale_factor = ocr_params.get('scale_factor', 3)
        contrast_boost = ocr_params.get('contrast_boost', 1.5)
        
        # Масштабирование для улучшения OCR
        if scale_factor > 1:
            width, height = region.size
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            region = region.resize((new_width, new_height), Image.LANCZOS)
        
        # Улучшение контраста
        if contrast_boost > 1:
            enhancer = ImageEnhance.Contrast(region)
            region = enhancer.enhance(contrast_boost)
        
        # Специальная обработка для FinUniv ФИО
        if field_name == 'full_name' and 'FINUNIV' in str(ocr_params):
            enhancer = ImageEnhance.Sharpness(region)
            region = enhancer.enhance(1.5)
        
        # Дополнительная резкость для серии и номера
        if field_name == 'series_and_number':
            enhancer = ImageEnhance.Sharpness(region)
            region = enhancer.enhance(1.3)
        
        return region
    
    def remove_lines_from_region(self, img: Image.Image, aggressive: bool = False) -> Image.Image:
        """Удаление линий из изображения для улучшения OCR"""
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        if aggressive:
            # Создание ядра для горизонтальных линий
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            # Выделение линий
            lines_mask = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
            # Удаление линий
            gray_no_lines = cv2.subtract(gray, lines_mask)
            # Улучшение изображения
            gray_no_lines = cv2.addWeighted(gray_no_lines, 1.5, gray_no_lines, 0, 0)
        else:
            # Мягкое размытие для уменьшения шума
            gray_no_lines = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Конвертация обратно в PIL
        img_processed = Image.fromarray(gray_no_lines)
        return img_processed
    
    def extract_text_from_region(self, image: Image.Image, box: List[int],
                                ocr_params: Dict[str, Any] = None, field_name: str = "") -> str:
        """Извлечение текста из региона изображения с улучшениями"""
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
            
            # Предобработка
            if ocr_params:
                region = self.preprocess_region(region, ocr_params, field_name)
            
            # Удаление линий для некоторых полей
            if field_name in ['registration_number']:
                region = self.remove_lines_from_region(region, aggressive=True)
            
            # Конвертация в оттенки серого
            region = region.convert('L')
            
            # Медианный фильтр для уменьшения шума
            region = region.filter(ImageFilter.MedianFilter(size=3))
            
            # Получение PSM и языка
            psm = self.get_psm_for_field(field_name, ocr_params)
            lang = self.get_language_for_field(field_name)
            
            # Конфигурация Tesseract
            config_str = f'--oem 3 --psm {psm}'
            
            # OCR распознавание
            text = pytesseract.image_to_string(region, lang=lang, config=config_str)
            return text.strip()
            
        except Exception as e:
            print(f"❌ Ошибка OCR для поля {field_name}: {e}")
            return ""
    
    def get_psm_for_field(self, field_name: str, ocr_params: Dict = None) -> int:
        """Получение PSM конфигурации для поля"""
        if ocr_params and 'psm_configs' in ocr_params:
            return ocr_params['psm_configs'].get(field_name, 7)
        
        # Базовые PSM по типу поля
        if field_name == 'full_name':
            return 7  # Single text line
        elif field_name == 'issue_date':
            return 6  # Uniform block of text
        elif field_name == 'series_and_number':
            return 7  # Single text line
        elif field_name == 'registration_number':
            return 8  # Single word
        else:
            return 7  # Default
    
    def get_language_for_field(self, field_name: str) -> str:
        """Получение языка для поля"""
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
        """Обработка документа с применением парсеров - ОБНОВЛЕНО для series_and_number"""
        results = {}
        uncertainty_engine = UncertaintyEngine(config.organization)
        
        print(f"🔍 Обработка документа: {config.name}")
        
        for field_name, box in config.fields.items():
            print(f"📋 Обрабатываем поле: {field_name}, координаты: {box}")
            
            # Извлечение сырого текста
            raw_text = self.extract_text_from_region(image, box, config.ocr_params, field_name)
            print(f"🔤 Сырой OCR текст: '{raw_text}'")
            
            if not raw_text.strip():
                print(f"⚠️ Пустой текст для поля {field_name}")
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
                # НОВАЯ ЛОГИКА: обработка series_and_number как единого поля
                if config.patterns and 'series_and_number' in config.patterns:
                    parser = config.patterns['series_and_number']
                    try:
                        parsed_result = parser(raw_text)
                        if len(parsed_result) == 3:  # (series, number, uncertain)
                            series, number, uncertain = parsed_result
                            results['series'] = series
                            results['number'] = number
                            print(f"✅ Серия и номер: '{series}', '{number}', uncertain: {uncertain}")
                            
                            # Проверка неопределённости
                            if uncertain or uncertainty_engine.should_flag_uncertainty('series_and_number', raw_text, (series, number)):
                                results['uncertain_series'] = True
                                results['uncertain_number'] = True
                        else:
                            # Fallback если парсер вернул не то что ожидалось
                            results['series'] = ""
                            results['number'] = raw_text
                            results['uncertain_series'] = True
                            results['uncertain_number'] = True
                    except Exception as e:
                        print(f"❌ Ошибка парсера для series_and_number: {e}")
                        # Попытка простого разбора регулярными выражениями
                        series, number = self._parse_series_number_fallback(raw_text)
                        results['series'] = series
                        results['number'] = number
                        results['uncertain_series'] = True
                        results['uncertain_number'] = True
                else:
                    # Fallback без парсера
                    series, number = self._parse_series_number_fallback(raw_text)
                    results['series'] = series
                    results['number'] = number
                    results['uncertain_series'] = True
                    results['uncertain_number'] = True
                        
            else:
                # Обработка остальных полей
                if config.patterns and field_name in config.patterns:
                    parser = config.patterns[field_name]
                    try:
                        parsed_result = parser(raw_text)
                        if isinstance(parsed_result, tuple) and len(parsed_result) == 2:
                            value, uncertain = parsed_result
                            results[field_name] = value
                            print(f"✅ {field_name}: '{value}', uncertain: {uncertain}")
                            
                            # Проверка неопределённости
                            if uncertain or uncertainty_engine.should_flag_uncertainty(field_name, raw_text, value, uncertain):
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
        """Fallback парсер для series_and_number регулярными выражениями"""
        # Простые паттерны для разных типов документов
        patterns = [
            r'(\d{2})\s*(\d{6})',  # 1T: "02 123456"
            r'(\d{2})-?\w?\s*(\d{8,10})',  # ROSNOU: "12-Д 2024000010"
            r'(\d{2,4})\s+(\d{8,})',  # FinUniv: "7733 01156696"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1), match.group(2)
        
        # Если ничего не найдено, пытаемся разделить по пробелам/дефисам
        parts = re.split(r'[\s\-]+', text.strip())
        if len(parts) >= 2:
            return parts[0], parts[1]
        
        return "", text.strip()

class DocumentProcessor:
    """Обработчик документов с интеграцией OCR движка"""
    
    def __init__(self, tesseract_path: str = None):
        self.ocr_engine = OCREngine(tesseract_path)
    
    def process_single_image(self, image: Image.Image, config: DocumentConfig, 
                           rotation_angle: int = 0) -> Dict[str, Any]:
        """Обработка одного изображения"""
        try:
            # Поворот изображения при необходимости
            if rotation_angle != 0:
                image = image.rotate(-rotation_angle, expand=True, fillcolor='white')
            
            # Обработка с парсерами
            results = self.ocr_engine.process_document_with_parser(image, config)
            
            return results
            
        except Exception as e:
            print(f"❌ Ошибка обработки изображения: {e}")
            return {}
    
    def extract_fields(self, img: Image.Image, config: DocumentConfig, 
                      uncertainty_engine) -> Dict[str, Any]:
        """Совместимость с старым API"""
        return self.process_single_image(img, config)
