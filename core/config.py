"""
Загрузка конфигурации из JSON файла
"""
import json
import os
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

@dataclass
class DocumentConfig:
    """Конфигурация документа с интеграцией парсеров"""
    name: str
    organization: str
    document_type: str
    fields: Dict[str, List[int]]  # {field_name: [x1, y1, x2, y2]}
    ocr_params: Dict[str, Any]
    patterns: Optional[Dict[str, Callable]] = None  # Парсеры для каждого поля
    
    @property
    def config_id(self) -> str:
        return f"{self.organization}_{self.document_type}".upper()

class ConfigManager:
    """Менеджер конфигураций с поддержкой парсеров"""
    
    def __init__(self):
        self.configs = {}
        self.field_descriptions = {}
        self.parsers_map = {}
        self.load_configs()
        self._setup_parsers()
    
    def load_configs(self):
        """Загрузка конфигураций из JSON файла"""
        try:
            # Ищем файл конфигурации
            config_paths = [
                'data/configs.json',
                '../data/configs.json', 
                os.path.join(os.path.dirname(__file__), '..', 'data', 'configs.json'),
                'configs.json'
            ]
            
            config_file = None
            for path in config_paths:
                if os.path.exists(path):
                    config_file = path
                    break
            
            if not config_file:
                print("⚠️ Файл data/configs.json не найден. Создаю базовые конфигурации...")
                self._create_default_configs()
                return
            
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Загружаем описания полей
            self.field_descriptions = data.get('field_descriptions', {})
            
            # Загружаем конфигурации документов
            for config_key, config_data in data.items():
                if config_key == 'field_descriptions':
                    continue
                    
                try:
                    self.configs[config_key] = DocumentConfig(
                        name=config_data['name'],
                        organization=config_data['organization'],
                        document_type=config_data['document_type'],
                        fields=config_data['fields'],
                        ocr_params=config_data['ocr_params']
                    )
                except KeyError as e:
                    print(f"⚠️ Некорректная конфигурация {config_key}: отсутствует поле {e}")
                    continue
            
            print(f"✅ Загружено {len(self.configs)} конфигураций документов")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигураций: {e}")
            self._create_default_configs()
    
    def _setup_parsers(self):
        """Настройка парсеров для каждой конфигурации"""
        try:
            from .parsers import OneTParsers, RosNouParsers, FinUnivParsers, CommonParsers
            
            # Маппинг парсеров для каждого типа документа
            parsers_mapping = {
                '1T_CERTIFICATE': {
                    'series_and_number': OneTParsers.parse_series_and_number,
                    'registration_number': OneTParsers.parse_reg_number,
                    'issue_date': OneTParsers.parse_date_certificate,
                    'full_name': CommonParsers.parse_fullname_simple
                },
                '1T_DIPLOMA': {
                    'series_and_number': OneTParsers.parse_series_and_number,
                    'registration_number': OneTParsers.parse_reg_number,
                    'issue_date': OneTParsers.parse_date_diploma,
                    'full_name': CommonParsers.parse_fullname_simple
                },
                'ROSNOU_DIPLOMA': {
                    'series_and_number': RosNouParsers.parse_series_and_number,
                    'registration_number': RosNouParsers.parse_reg_number_diploma,
                    'issue_date': CommonParsers.parse_date_standard,
                    'full_name': RosNouParsers.parse_fullname_diploma
                },
                'ROSNOU_CERTIFICATE': {
                    'series_and_number': RosNouParsers.parse_series_and_number,
                    'registration_number': RosNouParsers.parse_reg_number_certificate,
                    'issue_date': CommonParsers.parse_date_standard,
                    'full_name': RosNouParsers.parse_fullname_certificate
                },
                # Правильные ключи из configs.json
                'FINUNIVCERTV1': {
                    'series_and_number': FinUnivParsers.parse_series_and_number_v1,
                    'registration_number': FinUnivParsers.parse_reg_number_v1,
                    'issue_date': FinUnivParsers.parse_date_from_text,
                    'full_name': FinUnivParsers.parse_fullname_simple
                },
                'FINUNIVCERTV2': {
                    'series_and_number': FinUnivParsers.parse_series_and_number_v2,
                    'registration_number': FinUnivParsers.parse_reg_number_v2,
                    'issue_date': FinUnivParsers.parse_date_from_text,
                    'full_name': FinUnivParsers.parse_fullname_complex
                }
            }
            
            # Присваиваем парсеры каждой конфигурации
            for config_key, config in self.configs.items():
                if config_key in parsers_mapping:
                    config.patterns = parsers_mapping[config_key]
                    print(f"✅ Парсеры подключены для {config_key}")
                else:
                    print(f"⚠️ Нет парсеров для {config_key}")
                    
            print("✅ Парсеры успешно интегрированы в конфигурации")
            
        except ImportError as e:
            print(f"⚠️ Не удалось загрузить парсеры: {e}")
    
    def _create_default_configs(self):
        """Создание базовых конфигураций при отсутствии файла"""
        self.field_descriptions = {
            'full_name': 'ФИО получателя документа',
            'series_and_number': 'Серия и номер документа',
            'registration_number': 'Регистрационный номер',
            'issue_date': 'Дата выдачи документа'
        }
        
        # Базовая конфигурация
        self.configs['DEFAULT'] = DocumentConfig(
            name='Базовая конфигурация',
            organization='GENERIC',
            document_type='default',
            fields={
                'full_name': [100, 100, 400, 140],
                'series_and_number': [100, 200, 300, 230],
                'registration_number': [100, 300, 300, 330],
                'issue_date': [100, 400, 300, 430]
            },
            ocr_params={'scale_factor': 3, 'contrast_boost': 1.5}
        )

# Глобальный менеджер конфигураций
_config_manager = ConfigManager()

def get_available_configs() -> List[str]:
    """Получить список доступных конфигураций"""
    return list(_config_manager.configs.keys())

def get_config(config_key: str) -> Optional[DocumentConfig]:
    """Получить конфигурацию по ключу"""
    return _config_manager.configs.get(config_key)

def get_field_description(field_name: str) -> str:
    """Получить описание поля"""
    return _config_manager.field_descriptions.get(field_name, field_name)

def get_all_configs() -> Dict[str, DocumentConfig]:
    """Получить все конфигурации"""
    return _config_manager.configs.copy()

def reload_configs():
    """Перезагрузить конфигурации"""
    global _config_manager
    _config_manager = ConfigManager()
