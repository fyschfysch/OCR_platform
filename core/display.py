"""
Отображение с корректным подключением внешних CSS стилей
"""
import streamlit as st
from PIL import Image
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple
import io
import base64
import os

class ImageDisplay:
    """Отображение изображений с полями"""
    
    @staticmethod
    def create_figure(image: Image.Image, field_boxes: Dict[str, List[int]] = None,
                     selected_field: str = None, interactive: bool = False) -> go.Figure:
        """Создание Plotly фигуры с изображением и полями"""
        import numpy as np
        
        img_array = np.array(image)
        fig = go.Figure()
        fig.add_trace(go.Image(z=img_array))
        
        colors = {
            'full_name': 'red',
            'series': 'blue', 
            'number': 'blue',
            'registration_number': 'green',
            'issue_date': 'orange'
        }
        
        if field_boxes:
            for field_name, box in field_boxes.items():
                if len(box) == 4:
                    x1, y1, x2, y2 = box
                    color = colors.get(field_name, 'gray')
                    line_width = 4 if field_name == selected_field else 2
                    
                    fig.add_shape(
                        type="rect",
                        x0=x1, y0=y1, x1=x2, y1=y2,
                        line=dict(color=color, width=line_width),
                        fillcolor=color,
                        opacity=0.1
                    )
                    
                    fig.add_annotation(
                        x=x1,
                        y=max(0, y1-20),
                        text=field_name,
                        showarrow=False,
                        font=dict(color=color, size=12),
                        bgcolor="white",
                        bordercolor=color,
                        borderwidth=1
                    )
        
        fig.update_layout(
            showlegend=False,
            xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[0, image.width]),
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[image.height, 0], scaleanchor="x", scaleratio=1),
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=900,
            width=None
        )
        
        return fig

class ThumbnailCreator:
    """Создание миниатюр для полей"""
    
    @staticmethod
    def create_thumbnail(image: Image.Image, box: List[int], height: int = 40) -> Optional[str]:
        """Создание миниатюры поля в формате base64"""
        try:
            if not box or len(box) != 4:
                return None
                
            x1, y1, x2, y2 = box
            
            # Валидация координат
            img_width, img_height = image.size
            x1 = max(0, min(x1, img_width))
            y1 = max(0, min(y1, img_height))
            x2 = max(x1+1, min(x2, img_width))
            y2 = max(y1+1, min(y2, img_height))
            
            # Извлечение и обработка региона
            region = image.crop((x1, y1, x2, y2))
            region.thumbnail((2000, height), Image.LANCZOS)
            
            # Улучшение качества
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(region)
            region = enhancer.enhance(1.2)
            enhancer = ImageEnhance.Sharpness(region)
            region = enhancer.enhance(1.1)
            
            # Конвертация в base64
            buffer = io.BytesIO()
            region.save(buffer, format='PNG')
            img_data = buffer.getvalue()
            img_base64 = base64.b64encode(img_data).decode()
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            print(f"❌ Ошибка создания миниатюры: {e}")
            return None
    
    @staticmethod
    def create_enhanced_thumbnail(image: Image.Image, box: List[int], height: int = 40) -> Optional[str]:
        """Создание улучшенной миниатюры"""
        return ThumbnailCreator.create_thumbnail(image, box, height)

class StyleManager:
    """Менеджер CSS стилей с корректным подключением внешнего файла"""
    
    @staticmethod
    def add_styles():
        """Загрузка и применение CSS стилей"""
        # Поиск файла стилей в нескольких локациях
        css_paths = [
            'static/styles.css',
            'styles.css',
            os.path.join(os.path.dirname(__file__), '..', 'static', 'styles.css'),
            os.path.join(os.path.dirname(__file__), '..', 'styles.css'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'styles.css')
        ]
        
        css_loaded = False
        
        for css_path in css_paths:
            if os.path.exists(css_path):
                try:
                    with open(css_path, 'r', encoding='utf-8') as f:
                        css_content = f.read()
                    
                    # Применение стилей через Streamlit
                    st.markdown(f'<style>{css_content}</style>', unsafe_allow_html=True)
                    print(f"✅ CSS стили загружены из: {css_path}")
                    css_loaded = True
                    break
                except Exception as e:
                    print(f"⚠️ Ошибка загрузки CSS из {css_path}: {e}")
                    continue
        
        if not css_loaded:
            # Базовые стили, если файл не найден
            print("⚠️ Внешний CSS файл не найден. Применяю базовые стили...")
            fallback_css = """
            /* Базовые стили OCR платформы */
            .main > div {
                padding-top: 0.5rem;
            }
            
            /* Стили для кнопок обработки */
            .stButton > button[data-testid="baseButton-primary"] {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                border: none !important;
                color: white !important;
                font-weight: 600 !important;
                padding: 0.75rem 1.5rem !important;
                border-radius: 8px !important;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
                transition: all 0.3s ease !important;
                width: 100% !important;
            }
            
            .stButton > button[data-testid="baseButton-primary"]:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 6px 16px rgba(102, 126, 234, 0.6) !important;
            }
            
            /* Контейнеры полей */
            .field-container {
                background: #f8f9fa;
                padding: 1rem;
                border-radius: 8px;
                border-left: 4px solid #4ECDC4;
                margin: 1rem 0;
            }
            
            /* Миниатюры */
            .thumbnail-container {
                display: flex;
                align-items: center;
                justify-content: center;
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 5px;
                min-height: 50px;
                width: 100%;
            }
            
            .thumbnail-image {
                height: 40px;
                max-width: 100%;
                border-radius: 2px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border: 1px solid #4ECDC4;
                object-fit: contain;
            }
            
            /* Результаты */
            .result-row {
                background: white;
                padding: 1rem;
                margin: 0.5rem 0;
                border-radius: 8px;
                border: 1px solid #e1e5e9;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                display: flex;
                align-items: flex-start;
                gap: 1rem;
            }
            
            .field-title {
                font-weight: 600;
                color: #495057;
                font-size: 14px;
                line-height: 1.2;
                word-wrap: break-word;
                hyphens: auto;
                margin-bottom: 0.5rem;
                min-width: 80px;
                max-width: 120px;
            }
            """
            
            st.markdown(f'<style>{fallback_css}</style>', unsafe_allow_html=True)

class InteractiveMarkup:
    """Интерактивная разметка полей"""
    
    def __init__(self):
        self.field_names = ["full_name", "series", "number", "registration_number", "issue_date"]
        
        # Импорт функции получения описаний
        try:
            from .config import get_field_description
            self.get_description = get_field_description
        except ImportError:
            # Fallback описания полей
            self.field_descriptions = {
                'full_name': 'ФИО получателя документа',
                'series': 'Серия документа',
                'number': 'Номер документа',
                'registration_number': 'Регистрационный номер',
                'issue_date': 'Дата выдачи документа'
            }
            self.get_description = lambda x: self.field_descriptions.get(x, x)
    
    def render_field_selector(self) -> str:
        """Отображение селектора полей"""
        return st.selectbox(
            "🎯 Выберите поле для разметки:",
            self.field_names,
            format_func=lambda x: self.get_description(x),
            key="active_markup_field"
        )
    
    def render_coordinate_inputs(self, field_name: str, default_coords: List[int] = None) -> List[int]:
        """Отображение полей ввода координат"""
        default_coords = default_coords or [100, 100, 300, 140]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            x1 = st.number_input("X1", value=default_coords[0], key=f"{field_name}_x1")
        with col2:
            y1 = st.number_input("Y1", value=default_coords[1], key=f"{field_name}_y1")
        with col3:
            x2 = st.number_input("X2", value=default_coords[2], key=f"{field_name}_x2")
        with col4:
            y2 = st.number_input("Y2", value=default_coords[3], key=f"{field_name}_y2")
        
        return [int(x1), int(y1), int(x2), int(y2)]
