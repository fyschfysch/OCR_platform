"""
OCR движок на базе Tesseract
"""
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from typing import Dict, Any, List, Optional, Tuple
import re

from .config import DocumentConfig
from .parsers import OneTParsers, RosNouParsers, FinUnivParsers, CommonParsers, UncertaintyEngine

class OCREngine:
    """OCR движок на базе Tesseract"""
    
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
    
    def preprocess_region(self, region: Image.Image, ocr_params: Dict, field_name: str) -> Image.Image:
        """Предобработка региона"""
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
        
        # Дополнительная резкость для важных полей
        if field_name in ['series_and_number', 'full_name']:
            enhancer = ImageEnhance.Sharpness(region)
            region = enhancer.enhance(1.3)
        
        return region
    
    def remove_lines_from_region(self, img: Image.Image, aggressive: bool = False) -> Image.Image:
        """Упрощенная версия удаления линий без OpenCV"""
        if aggressive:
            # Простое размытие вместо сложной OpenCV обработки
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
        return img
    
    def extract_text_from_region(self, image: Image.Image, box: List[int],
                                ocr_params: Dict[str, Any] = None, field_name: str = "") -> str:
        """Извлечение текста из региона изображения"""
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
            
            # Простая обработка для номеров с линиями
            if field_name == 'registration_number':
                region = self.remove_lines_from_region(region, aggressive=True)
            
            # Конвертация в оттенки серого
            region = region.convert('L')
            
            # Медианный фильтр для шума
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
            return ""
    
    def get_psm_for_field(self, field_name: str, ocr_params: Dict = None) -> int:
        """Получение PSM для поля"""
        if ocr_params and 'psm_configs' in ocr_params:
            return ocr_params['psm_configs'].get(field_name, 7)
        
        if field_name == 'full_name':
            return 7  # Единая строка текста
        elif field_name == 'issue_date':
            return 6  # Единый блок текста
        elif field_name == 'series_and_number':
            return 7  # Единая строка текста
        elif field_name == 'registration_number':
            return 8  # Единое слово
        else:
            return 7
    
    def get_language_for_field(self, field_name: str) -> str:
        """Получение языка для поля"""
        if field_name == 'full_name':
            return 'rus'
        elif field_name == 'series_and_number':
            return 'rus+eng'  # Для буквенно-цифровых серий
        elif field_name == 'registration_number':
            return 'rus+eng'
        elif field_name == 'issue_date':
            return 'rus'
        else:
            return 'rus+eng'
    
    def process_document_with_parser(self, image: Image.Image, config: DocumentConfig) -> Dict[str, Any]:
        """Обработка документа с парсерами"""
        results = {}
        uncertainty_engine = UncertaintyEngine(config.organization)
        
        print(f"🔍 Обработка документа: {config.name}")
        print(f"🔧 Конфигурация: {config.config_id}")
        print(f"🎯 Парсеры подключены: {bool(config.patterns)}")
        
        for field_name, box in config.fields.items():
            print(f"\n📋 Обрабатываем поле: {field_name}")
            
            # Извлечение текста
            raw_text = self.extract_text_from_region(image, box, config.ocr_params, field_name)
            print(f"🔤 OCR текст: '{raw_text}'")
            
            if not raw_text.strip():
                # Пустой текст
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
                # Специальная обработка для series_and_number
                if config.patterns and 'series_and_number' in config.patterns:
                    parser = config.patterns['series_and_number']
                    print(f"🎯 Используем парсер: {parser.__name__}")
                    try:
                        parsed_result = parser(raw_text)
                        if len(parsed_result) == 3:
                            series, number, uncertain = parsed_result
                            results['series'] = series
                            results['number'] = number
                            
                            print(f"✅ Парсер результат: серия='{series}', номер='{number}', uncertain={uncertain}")
                            
                            if uncertain:
                                results['uncertain_series'] = True
                                results['uncertain_number'] = True
                        else:
                            # Неожиданный формат ответа парсера
                            print(f"❌ Неожиданный формат парсера: {parsed_result}")
                            results['series'] = ""
                            results['number'] = raw_text
                            results['uncertain_series'] = True
                            results['uncertain_number'] = True
                    except Exception as e:
                        print(f"❌ Ошибка парсера: {e}")
                        results['series'] = ""
                        results['number'] = raw_text
                        results['uncertain_series'] = True
                        results['uncertain_number'] = True
                else:
                    # Нет парсера для series_and_number
                    print("⚠️ Парсер для series_and_number не найден")
                    results['series'] = ""
                    results['number'] = raw_text
                    results['uncertain_series'] = True
                    results['uncertain_number'] = True
            else:
                # Обычные поля
                if config.patterns and field_name in config.patterns:
                    parser = config.patterns[field_name]
                    print(f"🎯 Используем парсер: {parser.__name__}")
                    try:
                        parsed_result = parser(raw_text)
                        if isinstance(parsed_result, tuple) and len(parsed_result) == 2:
                            value, uncertain = parsed_result
                            results[field_name] = value
                            print(f"✅ Парсер результат: '{value}', uncertain={uncertain}")
                            if uncertain:
                                results[f'uncertain_{field_name}'] = True
                        else:
                            # Парсер вернул не tuple
                            results[field_name] = str(parsed_result)
                            results[f'uncertain_{field_name}'] = True
                    except Exception as e:
                        print(f"❌ Ошибка парсера для {field_name}: {e}")
                        results[field_name] = raw_text
                        results[f'uncertain_{field_name}'] = True
                else:
                    # Нет парсера для поля
                    print(f"⚠️ Парсер для {field_name} не найден")
                    results[field_name] = raw_text
                    results[f'uncertain_{field_name}'] = True
        
        print(f"\n🎉 Обработка завершена: {len(results)} полей")
        return results

class DocumentProcessor:
    """Процессор документов"""
    
    def __init__(self, tesseract_path: str = None):
        self.ocr_engine = OCREngine(tesseract_path)
    
    def process_single_image(self, image: Image.Image, config: DocumentConfig, 
                           rotation_angle: int = 0) -> Dict[str, Any]:
        """Обработка одного изображения"""
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
        """Извлечение полей (совместимость)"""
        return self.process_single_image(img, config)
