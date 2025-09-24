"""
Специализированные парсеры для распознавания полей документов
"""
import re
from datetime import datetime
from typing import Tuple, Any

class UncertaintyEngine:
    """Система оценки неопределённости результатов OCR"""
    
    def __init__(self, organization: str):
        self.organization = organization
        self.thresholds = {
            "1T": {"min_reg_digits": 4, "min_name_length": 5, "min_number_length": 4},
            "ROSNOU": {"min_reg_digits": 3, "min_name_length": 8, "min_number_length": 6},
            "FINUNIVERSITY": {"min_reg_digits": 4, "min_name_length": 8, "min_number_length": 8}
        }
    
    def should_flag_uncertainty(self, field_name: str, original_text: str, 
                              parsed_result: Any, corrections_made: bool = False) -> bool:
        """Определение необходимости флага неопределённости"""
        config = self.thresholds.get(self.organization, {})
        
        if corrections_made:
            return True
            
        if field_name == "registration_number":
            digits_count = len(re.findall(r'\d', original_text))
            return digits_count < config.get("min_reg_digits", 3)
        elif field_name == "full_name":
            return len(str(parsed_result).strip()) < config.get("min_name_length", 5)
        elif field_name in ["series_and_number", "series", "number"]:
            if isinstance(parsed_result, tuple) and len(parsed_result) >= 2:
                number_length = len(str(parsed_result[1]))
                return number_length < config.get("min_number_length", 4)
            elif isinstance(parsed_result, str):
                return len(parsed_result) < config.get("min_number_length", 4)
        
        return False

class CommonParsers:
    """Общие парсеры для всех типов документов"""
    
    @staticmethod
    def parse_date_standard(text: str) -> Tuple[str, bool]:
        """Стандартный парсер даты в формате 'DD месяц YYYY г.'"""
        match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text, re.IGNORECASE)
        if match:
            day, month_str, year = match.groups()
            months = {
                'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
                'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08', 
                'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
            }
            month = months.get(month_str.lower())
            if month:
                try:
                    result = datetime(int(year), int(month), int(day)).date().isoformat()
                    return result, False
                except ValueError:
                    pass
        return text.strip(), True
    
    @staticmethod 
    def parse_fullname_simple(text: str) -> Tuple[str, bool]:
        """Простой парсер ФИО - возвращает как есть"""
        result = text.strip()
        return result, len(result) < 8

class OneTParsers:
    """Парсеры для документов 1Т"""
    
    @staticmethod
    def parse_series_and_number(text: str) -> Tuple[str, str, bool]:
        """Парсер серии и номера документа 1Т в формате '02 123456'"""
        text = re.sub(r'[^\d\s]', ' ', text.strip())
        
        patterns = [r'(\d{2})\s*(\d{6})', r'(\d{2})[\s-]*(\d{6})', r'(\d{2})(\d{6})']
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                series, number = match.group(1), match.group(2)
                uncertain = len(number) < 4
                return series, number, uncertain
                
        return "", "", True
    
    @staticmethod
    def parse_reg_number(text: str) -> Tuple[str, bool]:
        """Парсер регистрационного номера 1Т"""
        digits = ''.join(re.findall(r'\d', text))
        
        if not digits:
            return "000000", True
        
        if len(digits) <= 6:
            result = digits.zfill(6)
        else:
            result = digits
        
        uncertain = len(digits) < 4
        return result, uncertain
    
    @staticmethod
    def parse_date_certificate(text: str) -> Tuple[str, bool]:
        """Парсер даты для удостоверений 1Т"""
        return CommonParsers.parse_date_standard(text)
    
    @staticmethod
    def parse_date_diploma(text: str) -> Tuple[str, bool]:
        """Парсер даты для дипломов 1Т в формате '20.12.2024'"""
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
        if match:
            day, month, year = match.groups()
            try:
                result = datetime(int(year), int(month), int(day)).date().isoformat()
                return result, False
            except ValueError:
                return text.strip(), True
        return text.strip(), True

class RosNouParsers:
    """Парсеры для документов РОСНОУ"""
    
    @staticmethod
    def parse_series_and_number(text: str) -> Tuple[str, str, bool]:
        """Парсер серии и номера РОСНОУ в формате '12-Д 2024000010'"""
        digits = ''.join(re.findall(r'\d', text))
        corrections_made = False
        
        if len(digits) >= 10:
            series = digits[:2]
            number = digits[2:12] if len(digits) >= 12 else digits[2:10]
            
            # Исправление OCR ошибки: '71', '11', '17' часто ошибочно распознаются как '77'
            if series in ['71', '11', '17']:
                series = '77'
                corrections_made = True
                print(f"🔧 Исправлена серия OCR: {digits[:2]} -> 77")
                
            uncertain = len(number) < 8 or corrections_made
            return series, number, uncertain
            
        return digits[:2].zfill(2) if len(digits) >= 2 else "00", \
               digits[2:] if len(digits) > 2 else "", True
    
    @staticmethod
    def parse_reg_number_diploma(text: str) -> Tuple[str, bool]:
        """Парсер регистрационного номера дипломов РОСНОУ в формате 'NNNNN-Д'"""
        original_text = text.upper()
        corrections_made = False
        
        # Исправления OCR ошибок
        ocr_corrections = {
            'БАС': 'Д', 'ВАС': 'Д', '8АС': 'Д', 'АС': 'Д', '8': 'Д', '4': 'Д', '0': 'Д'
        }
        text_upper = original_text
        
        for wrong, correct in ocr_corrections.items():
            if wrong in text_upper:
                text_upper = text_upper.replace(wrong, correct)
                corrections_made = True
                print(f"🔧 OCR исправление: {wrong} -> {correct}")
        
        # Поиск шаблона NNNNN-Д
        match = re.search(r'(\d{5})-[ДД]', text_upper, re.UNICODE)
        if match:
            result = f"{match.group(1)}-Д"
            return result, corrections_made
        
        # Если точный шаблон не найден, пытаемся извлечь цифры
        digits = re.findall(r'\d', text)
        if digits:
            number_part = ''.join(digits[:5])
            if len(number_part) < 5:
                number_part = number_part.zfill(5)
            result = f"{number_part}-Д"
            print(f"🔧 Восстановлен номер: {result}")
            return result, True
            
        return "00000-Д", True
    
    @staticmethod
    def parse_reg_number_certificate(text: str) -> Tuple[str, bool]:
        """Парсер регистрационного номера удостоверений РОСНОУ в формате 'ПК-243'"""
        match = re.search(r'([А-Я]{2,3})-(\d{2,3})', text.upper(), re.IGNORECASE)
        if match:
            letters = match.group(1)
            number = match.group(2)
            corrections_made = False
            
            # Исправление букв
            letter_corrections = {"ПАД": "ПК", "А": "К", "4": "К"}
            if letters in letter_corrections:
                letters = letter_corrections[letters]
                corrections_made = True
                print(f"🔧 Исправлено: {match.group(1)} -> {letters}")
                
            return f"{letters}-{number}", corrections_made
            
        return "ПК-000", True
    
    @staticmethod
    def parse_fullname_diploma(text: str) -> Tuple[str, bool]:
        """Парсер ФИО для дипломов РОСНОУ (многострочный)"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if len(lines) >= 2:
            result = f"{lines[0]} {lines[1]}"
            uncertain = any(len(line) < 2 for line in lines[:2])
            return result, uncertain
        elif len(lines) == 1:
            result = lines[0].strip()
            uncertain = len(result) < 8
            return result, uncertain
            
        return text.strip(), True
    
    @staticmethod 
    def parse_fullname_certificate(text: str) -> Tuple[str, bool]:
        """Парсер ФИО для удостоверений РОСНОУ"""
        result = text.strip()
        return result, len(result) < 8

class FinUnivParsers:
    """Парсеры для документов Финансового университета"""
    
    @staticmethod
    def parse_series_and_number_v1(text: str) -> Tuple[str, str, bool]:
        """Парсер серии и номера ФинУнив вариант 1: 'ПК 771804095780' или '7733 01156696'"""
        # Основной паттерн: буквы + пробел + цифры
        match = re.search(r'([А-ЯA-Z]{2,4})\s+(\d{8,})', text.upper())
        if match:
            series = match.group(1)
            number = match.group(2)
            uncertain = len(number) < 8
            print(f"🔧 FinUniv v1 парсинг: '{text}' -> серия: '{series}', номер: '{number}'")
            return series, number, uncertain
        
        # Альтернативный паттерн: цифры + пробел + цифры
        match = re.search(r'(\d{2,4})\s+(\d{8,})', text.upper())
        if match:
            series = match.group(1)
            number = match.group(2)
            uncertain = len(number) < 8
            print(f"🔧 FinUniv v1 цифры: '{text}' -> серия: '{series}', номер: '{number}'")
            return series, number, uncertain
            
        # Еще один паттерн: буквы без пробела + цифры
        match = re.search(r'([А-ЯA-Z]{2,4})(\d{8,})', text.upper())
        if match:
            series = match.group(1)
            number = match.group(2)
            uncertain = len(number) < 8
            print(f"🔧 FinUniv v1 без пробела: '{text}' -> серия: '{series}', номер: '{number}'")
            return series, number, uncertain
            
        print(f"⚠️ FinUniv v1 не смог распознать: '{text}'")
        return "", "", True
    
    @staticmethod
    def parse_series_and_number_v2(text: str) -> Tuple[str, str, bool]:
        """Парсер серии и номера ФинУнив вариант 2"""
        return FinUnivParsers.parse_series_and_number_v1(text)
    
    @staticmethod
    def parse_reg_number_v1(text: str) -> Tuple[str, bool]:
        """Парсер регистрационного номера ФинУнив v1: '06.11373'"""
        match = re.search(r'(\d+\.?\d*)', text, re.IGNORECASE)
        if match:
            result = match.group(1)
            return result, len(result) < 5
        return text.strip(), True
    
    @staticmethod
    def parse_reg_number_v2(text: str) -> Tuple[str, bool]:
        """Парсер регистрационного номера ФинУнив v2"""
        return FinUnivParsers.parse_reg_number_v1(text)
    
    @staticmethod
    def parse_fullname_simple(text: str) -> Tuple[str, bool]:
        """Простой парсер ФИО для ФинУнив (одна строка)"""
        result = text.strip()
        return result, len(result) < 8
    
    @staticmethod
    def parse_fullname_complex(text: str) -> Tuple[str, bool]:
        """Сложный парсер ФИО для ФинУнив v2 (ФИО на трёх строках в дательном падеже)"""
        # Очистка текста от лишних символов
        cleaned_text = re.sub(r'[^\w\s\-А-Яа-яЁё]', ' ', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text.strip())
        
        # Попытка разобрать ФИО по строкам/словам
        patterns = [
            r'(\w+\-?\w*)\s+(\w+\-?\w*)\s+(\w+\-?\w*)',  # Три слова подряд
            r'(\w+)\s+(\w+)\s+(\w+)',  # Три слова
            r'(\w+)\s+(\w+)'  # Два слова
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                surname, name = groups[0], groups[1]
                patronymic = groups[2] if len(groups) > 2 else ""
                
                # Удаление лишних дефисов в конце
                surname = surname.rstrip('-')
                name = name.rstrip('-')
                patronymic = patronymic.rstrip('-')
                    
                if patronymic:
                    result = f"{surname} {name} {patronymic}"
                else:
                    result = f"{surname} {name}"
                    
                print(f"🔧 Разобрано ФИО: {result}")
                return result, True
        
        result = cleaned_text.strip()
        print(f"⚠️ ФИО требует ручной проверки: {result}")
        return result, True
    
    @staticmethod
    def parse_date_from_text(text: str) -> Tuple[str, bool]:
        """Парсер даты из текста ФинУнив с OCR-коррекциями"""
        date_patterns = [
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # '30 мая 2024'
            r'«?(\d{1,2})\s*»?\s+(\w+)\s+(\d{4})',  # '«30» мая 2024'
        ]
        
        months = {
            'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
            'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
            'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
        }
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                day, month_str, year = match.groups()
                month = months.get(month_str.lower())
                
                if month:
                    try:
                        result = datetime(int(year), int(month), int(day)).date().isoformat()
                        print(f"🔧 Дата распознана: {text.strip()} -> {result}")
                        return result, False
                    except ValueError:
                        continue
                        
        return text.strip(), True