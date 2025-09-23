"""
🔍 OCR Платформа
"""
import streamlit as st
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from PIL import Image

# Добавляем путь к модулям core
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))

try:
    from core.config import get_available_configs, get_config, get_field_description
    from core.ocr_engine import OCREngine, DocumentProcessor
    from core.display import ImageDisplay, ThumbnailCreator, StyleManager, InteractiveMarkup
    from core.processors import SimpleImageProcessor, ResultsManager
except ImportError as e:
    st.error(f"❌ Ошибка импорта: {e}")
    st.error("Убедитесь, что все модули находятся в папке core/")
    st.stop()

# Конфигурация страницы
st.set_page_config(
    page_title="🔍 OCR Платформа", 
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

TESSERACT_PATH = None # r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def main():
    """Главная функция приложения"""
    # Применение стилей в начале
    StyleManager.add_styles()
    
    # Инициализация состояния сессии
    init_session_state()
    
    # Основной интерфейс
    render_sidebar()
    
    if st.session_state.images:
        render_main_interface()
    else:
        st.info("📁 Загрузите PDF документ через боковую панель для начала работы")

def init_session_state():
    """Инициализация состояния сессии"""
    if 'uploaded_file' not in st.session_state:
        st.session_state.uploaded_file = None
    if 'images' not in st.session_state:
        st.session_state.images = []
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'selected_config' not in st.session_state:
        st.session_state.selected_config = None
    if 'results' not in st.session_state:
        st.session_state.results = {}
    if 'manual_mode' not in st.session_state:
        st.session_state.manual_mode = False
    if 'field_coords' not in st.session_state:
        st.session_state.field_coords = {}
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    if 'rotation_angle' not in st.session_state:
        st.session_state.rotation_angle = 0
    if 'json_editor_content' not in st.session_state:
        st.session_state.json_editor_content = ""
    if 'page_approved' not in st.session_state:
        st.session_state.page_approved = {}
    if 'show_all_pages' not in st.session_state:
        st.session_state.show_all_pages = False

def render_sidebar():
    """Отображение боковой панели"""
    with st.sidebar:
        st.header("🎛️ Управление")
        
        # 1. Загрузка файла
        uploaded = st.file_uploader("📁 Загрузить PDF документ:", type=['pdf'])
        
        if uploaded and uploaded != st.session_state.uploaded_file:
            st.session_state.uploaded_file = uploaded
            load_pdf(uploaded)
        
        if st.session_state.uploaded_file:
            st.success(f"✅ Загружен: {st.session_state.uploaded_file.name}")
            st.info(f"📄 Страниц: {len(st.session_state.images)}")
        
        st.markdown("---")
        
        # 2. Выбор конфигурации
        st.subheader("⚙️ Конфигурация документа")
        
        try:
            configs = get_available_configs()
            options = ["🔧 Ручная разметка"] + [get_config(key).name for key in configs]
            
            selected = st.selectbox("Выберите тип документа:", options)
            
            if selected == "🔧 Ручная разметка":
                st.session_state.manual_mode = True
                st.session_state.selected_config = None
            elif selected != st.session_state.get('selected_config_name'):
                # Найдем ключ конфигурации по имени
                config_key = None
                for key in configs:
                    if get_config(key).name == selected:
                        config_key = key
                        break
                
                st.session_state.manual_mode = False
                st.session_state.selected_config = config_key
                st.session_state.selected_config_name = selected
                
        except Exception as e:
            st.error(f"❌ Ошибка загрузки конфигураций: {e}")
            st.session_state.manual_mode = True
            st.session_state.selected_config = None
        
        st.markdown("---")
        
        # 3. Поворот изображения
        if st.session_state.images:
            st.subheader("🔄 Поворот изображения")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("↻ Повернуть на 90°"):
                    rotate_image(90)
            with col2:
                if st.button("🔄 Сбросить поворот"):
                    reset_rotation()
            
            if st.session_state.rotation_angle != 0:
                st.caption(f"Угол поворота: {st.session_state.rotation_angle}°")
        
        st.markdown("---")
        
        # 4. Обработка документа
        if st.session_state.images and (st.session_state.selected_config or st.session_state.manual_mode):
            st.subheader("🔍 OCR Обработка")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 Обработать текущую страницу", type="primary"):
                    process_current_page()
            with col2:
                if st.button("📋 Обработать все страницы", type="primary"):
                    process_all_pages()
        
        # 5. Экспорт результатов
        if st.session_state.processing_complete and st.session_state.results:
            st.markdown("---")
            st.subheader("💾 Экспорт результатов")
            
            if st.button("📥 Скачать JSON", type="primary"):
                export_clean_results()

def load_pdf(uploaded_file):
    """Загрузка PDF файла"""
    try:
        with st.spinner("📄 Обработка PDF файла..."):
            pdf_bytes = uploaded_file.read()
            processor = SimpleImageProcessor(max_dimension=1200)
            images = processor.convert_pdf_to_images(pdf_bytes)
            
            if images:
                st.session_state.images = images
                st.session_state.current_page = 0
                st.session_state.results = {}
                st.session_state.processing_complete = False
                st.session_state.rotation_angle = 0
                st.session_state.page_approved = {}
                st.session_state.show_all_pages = False
                st.success(f"✅ Загружено {len(images)} страниц")
            else:
                st.error("❌ Не удалось извлечь изображения из PDF")
                
    except Exception as e:
        st.error(f"❌ Ошибка загрузки PDF: {e}")

def rotate_image(angle: int):
    """Поворот изображения на заданный угол"""
    st.session_state.rotation_angle = (st.session_state.rotation_angle + angle) % 360
    st.rerun()

def reset_rotation():
    """Сброс поворота изображения"""
    if st.session_state.rotation_angle != 0:
        st.session_state.rotation_angle = 0
        st.rerun()

def render_main_interface():
    """Отображение основного интерфейса"""
    current_image = st.session_state.images[st.session_state.current_page]
    
    # Применяем поворот к изображению для отображения
    display_image = current_image
    if st.session_state.rotation_angle != 0:
        processor = SimpleImageProcessor()
        display_image = processor.rotate_image(current_image, st.session_state.rotation_angle)
    
    # Селектор страниц
    if len(st.session_state.images) > 1 and not st.session_state.show_all_pages:
        page = st.selectbox(
            "📄 Выберите страницу:",
            range(len(st.session_state.images)),
            format_func=lambda x: f"Страница {x + 1}",
            index=st.session_state.current_page
        )
        
        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.rerun()
    
    # Получение полей для отображения
    field_boxes = get_field_boxes()
    
    # Отображение изображения с полями
    if not st.session_state.show_all_pages:
        try:
            display = ImageDisplay()
            fig = display.create_figure(display_image, field_boxes)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        except Exception as e:
            st.error(f"❌ Ошибка отображения: {e}")
            st.image(display_image)
        
        st.caption(f"Размер изображения: {display_image.width}×{display_image.height} пикселей")
    
    # Вкладки интерфейса
    if st.session_state.results and st.session_state.manual_mode:
        tab1, tab2, tab3 = st.tabs(["📋 Результаты", "📝 JSON Редактор", "🎯 Разметка полей"])
        with tab1:
            render_results()
        with tab2:
            render_json_editor()
        with tab3:
            render_manual_markup(current_image)
    elif st.session_state.results:
        tab1, tab2 = st.tabs(["📋 Результаты", "📝 JSON Редактор"])
        with tab1:
            render_results()
        with tab2:
            render_json_editor()
    elif st.session_state.manual_mode:
        render_manual_markup(current_image)

def get_field_boxes() -> Dict[str, List[int]]:
    """Получение координат полей для отображения - ОБНОВЛЕНО для series_and_number"""
    if st.session_state.manual_mode:
        return st.session_state.field_coords
    elif st.session_state.selected_config:
        config = get_config(st.session_state.selected_config)
        if config:
            # Адаптация для отображения: series_and_number показываем как единое поле
            display_fields = config.fields.copy()
            return display_fields
    return {}

def render_manual_markup(image: Image.Image):
    """Отображение интерфейса ручной разметки - ОБНОВЛЕНО"""
    st.markdown("### 🎯 Ручная разметка полей")
    
    markup = InteractiveMarkup()
    # Обновляем список полей для ручной разметки
    markup.field_names = ["full_name", "series_and_number", "registration_number", "issue_date"]
    field_name = markup.render_field_selector()
    
    # Текущие координаты поля
    current_coords = st.session_state.field_coords.get(field_name, [100, 100, 300, 200])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        x1 = st.number_input("X1", value=current_coords[0], key=f"x1_{field_name}")
    with col2:
        y1 = st.number_input("Y1", value=current_coords[1], key=f"y1_{field_name}")
    with col3:
        x2 = st.number_input("X2", value=current_coords[2], key=f"x2_{field_name}")
    with col4:
        y2 = st.number_input("Y2", value=current_coords[3], key=f"y2_{field_name}")
    
    new_coords = [int(x1), int(y1), int(x2), int(y2)]
    st.session_state.field_coords[field_name] = new_coords
    
    # Предварительный просмотр поля
    if st.button(f"🔍 Предварительный просмотр поля {field_name}"):
        creator = ThumbnailCreator()
        thumbnail = creator.create_thumbnail(image, new_coords, height=40)
        if thumbnail:
            st.markdown(f'<img src="{thumbnail}" class="thumbnail-image">', unsafe_allow_html=True)

def process_current_page():
    """Обработка текущей страницы"""
    try:
        with st.spinner("🔍 Выполнение OCR распознавания..."):
            if st.session_state.manual_mode:
                if not st.session_state.field_coords:
                    st.error("❌ Сначала настройте координаты полей в ручном режиме")
                    return
                # Создаем временную конфигурацию для ручного режима
                from core.config import DocumentConfig
                temp_config = DocumentConfig(
                    name="Ручная разметка",
                    organization="MANUAL",
                    document_type="manual",
                    fields=st.session_state.field_coords,
                    ocr_params={'scale_factor': 3, 'contrast_boost': 1.5}
                )
                config = temp_config
            else:
                config = get_config(st.session_state.selected_config)
                if not config:
                    st.error("❌ Конфигурация не найдена")
                    return
            
            processor = DocumentProcessor(TESSERACT_PATH)
            image = st.session_state.images[st.session_state.current_page]
            
            # Применяем поворот если нужно
            if st.session_state.rotation_angle != 0:
                img_processor = SimpleImageProcessor()
                image = img_processor.rotate_image(image, st.session_state.rotation_angle)
            
            results = processor.process_single_image(image, config)
            
            if not st.session_state.results:
                st.session_state.results = {}
                
            st.session_state.results[st.session_state.current_page] = results
            st.session_state.processing_complete = True
            
            update_json_editor()
            st.success("✅ OCR обработка завершена!")
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Ошибка при OCR обработке: {e}")

def process_all_pages():
    """Обработка всех страниц"""
    try:
        if st.session_state.manual_mode:
            if not st.session_state.field_coords:
                st.error("❌ Сначала настройте координаты полей в ручном режиме")
                return
            # Создаем временную конфигурацию
            from core.config import DocumentConfig
            temp_config = DocumentConfig(
                name="Ручная разметка",
                organization="MANUAL", 
                document_type="manual",
                fields=st.session_state.field_coords,
                ocr_params={'scale_factor': 3, 'contrast_boost': 1.5}
            )
            config = temp_config
        else:
            config = get_config(st.session_state.selected_config)
            if not config:
                st.error("❌ Конфигурация не найдена")
                return
        
        processor = DocumentProcessor(TESSERACT_PATH)
        img_processor = SimpleImageProcessor()
        
        results = {}
        
        # Прогресс бар
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, image in enumerate(st.session_state.images):
            progress = (i + 1) / len(st.session_state.images)
            progress_bar.progress(progress)
            status_text.text(f"Обрабатывается страница {i + 1} из {len(st.session_state.images)}...")
            
            processing_image = image
            if st.session_state.rotation_angle != 0:
                processing_image = img_processor.rotate_image(image, st.session_state.rotation_angle)
            
            result = processor.process_single_image(processing_image, config)
            results[i] = result
        
        st.session_state.results = results
        st.session_state.processing_complete = True
        st.session_state.show_all_pages = True
        
        update_json_editor()
        
        # Убираем прогресс бар
        progress_bar.empty()
        status_text.empty()
        
        st.success(f"✅ Обработано {len(results)} страниц!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Ошибка при обработке: {e}")

def get_confidence_icon(field_name: str, page_results: Dict[str, Any]) -> str:
    """Получение пиктограммы уверенности для поля - НОВАЯ ФУНКЦИЯ"""
    # Проверяем есть ли значение
    if field_name not in page_results:
        return "❌"  # Нет значения
    
    value = page_results[field_name]
    if not str(value).strip():
        return "❌"  # Пустое значение
    
    # Проверяем флаг неопределённости
    uncertain_key = f"uncertain_{field_name}"
    if uncertain_key in page_results and page_results[uncertain_key]:
        return "⚠️"  # Неуверенное распознавание
    
    return "✅"  # Уверенное распознавание

def render_results():
    """Отображение результатов OCR"""
    st.markdown("### 📋 Результаты распознавания")
    
    if not st.session_state.results:
        st.warning("Результаты отсутствуют. Выполните обработку документа.")
        return
    
    if st.session_state.show_all_pages:
        render_all_pages_results()
    else:
        render_single_page_results()

def render_all_pages_results():
    """Отображение результатов для всех страниц"""
    # Кнопка "Одобрить все"
    all_approved = all(st.session_state.page_approved.get(i, False) for i in st.session_state.results.keys())
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("✅ Одобрить все страницы", disabled=all_approved):
            for page_num in st.session_state.results.keys():
                st.session_state.page_approved[page_num] = True
            st.success("Все страницы одобрены!")
            st.rerun()
    
    with col2:
        approved_count = sum(1 for approved in st.session_state.page_approved.values() if approved)
        total_pages = len(st.session_state.results)
        st.info(f"Одобрено: {approved_count}/{total_pages} страниц")
    
    st.markdown("---")
    
    # Результаты по страницам
    for page_num in sorted(st.session_state.results.keys()):
        page_results = st.session_state.results[page_num]
        approved = st.session_state.page_approved.get(page_num, False)
        
        st.markdown(f"#### 📄 Страница {page_num + 1}")
        render_page_results_table(page_num, page_results)
        
        # Кнопка одобрения страницы
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button(f"✅ Одобрить страницу {page_num + 1}", 
                        key=f"approve_{page_num}", disabled=approved):
                st.session_state.page_approved[page_num] = True
                st.rerun()
        with col2:
            if approved:
                st.success("✅ Страница одобрена")
        
        st.markdown("---")

def render_single_page_results():
    """Отображение результатов текущей страницы"""
    page_results = st.session_state.results.get(st.session_state.current_page, {})
    
    if not page_results:
        st.warning("Результаты для текущей страницы отсутствуют.")
        return
    
    render_page_results_table(st.session_state.current_page, page_results)

def render_page_results_table(page_num: int, page_results: Dict[str, Any]):
    """Отображение таблицы результатов страницы - ОБНОВЛЕНО с 4 столбцами"""
    # Порядок полей для отображения - ОБНОВЛЕН
    display_fields = ['full_name', 'series', 'number', 'registration_number', 'issue_date']
    
    for field_name in display_fields:
        if field_name in page_results:
            value = page_results[field_name]
            description = get_field_description(field_name if field_name != 'series' and field_name != 'number' else 'series_and_number')
            
            # Для серии и номера показываем отдельные описания
            if field_name == 'series':
                description = "Серия документа"
            elif field_name == 'number':
                description = "Номер документа"
            
            st.markdown(f'<div class="result-row">', unsafe_allow_html=True)
            
            # НОВЫЙ МАКЕТ: 4 столбца
            col1, col2, col3, col4 = st.columns([0.15, 0.45, 0.3, 0.1])
            
            with col1:
                # Название поля
                st.markdown(f'<div class="field-title" style="word-wrap: break-word; hyphens: auto;">{description}</div>', 
                          unsafe_allow_html=True)
            
            with col2:
                # Миниатюра поля - показываем series_and_number для обеих полей
                field_boxes = get_field_boxes()
                thumbnail_field = 'series_and_number' if field_name in ['series', 'number'] else field_name
                
                if thumbnail_field in field_boxes:
                    image = st.session_state.images[page_num]
                    display_image = image
                    if st.session_state.rotation_angle != 0:
                        processor = SimpleImageProcessor()
                        display_image = processor.rotate_image(image, st.session_state.rotation_angle)
                    
                    creator = ThumbnailCreator()
                    thumbnail = creator.create_thumbnail(display_image, field_boxes[thumbnail_field], height=40)
                    if thumbnail:
                        st.markdown(
                            f'<div class="thumbnail-container">'
                            f'<img src="{thumbnail}" class="thumbnail-image">'
                            f'</div>', 
                            unsafe_allow_html=True
                        )
            
            with col3:
                # Редактируемое значение
                new_val = st.text_area(
                    "Значение:",
                    value=str(value), 
                    height=60,
                    key=f"result_{field_name}_{page_num}",
                    label_visibility="collapsed"
                )
                
                if new_val != str(value):
                    st.session_state.results[page_num][field_name] = new_val
                    update_json_editor()
            
            with col4:
                # НОВЫЙ СТОЛБЕЦ: Пиктограмма уверенности
                confidence_icon = get_confidence_icon(field_name, page_results)
                st.markdown(
                    f'<div style="text-align: center; font-size: 24px; padding-top: 15px;">{confidence_icon}</div>', 
                    unsafe_allow_html=True
                )
            
            st.markdown('</div>', unsafe_allow_html=True)

def render_json_editor():
    """Отображение JSON редактора"""
    st.markdown("### 📝 JSON Редактор")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔄 Обновить JSON"):
            update_json_editor()
            st.success("JSON обновлен!")
    with col2:
        if st.button("💾 Применить изменения"):
            apply_json_changes()
    with col3:
        if st.button("📋 Копировать JSON"):
            st.code(st.session_state.json_editor_content)
    with col4:
        st.caption("JSON формат данных")
    
    # Обновляем JSON если пуст
    if not st.session_state.json_editor_content:
        update_json_editor()
    
    new_json = st.text_area(
        "JSON данные:", 
        value=st.session_state.json_editor_content,
        height=400,
        key="json_editor"
    )
    
    if new_json != st.session_state.json_editor_content:
        st.session_state.json_editor_content = new_json
    
    # Валидация JSON
    try:
        if st.session_state.json_editor_content:
            parsed = json.loads(st.session_state.json_editor_content)
            st.success(f"✅ JSON корректен, найдено {len(parsed)} записей")
    except json.JSONDecodeError as e:
        st.error(f"❌ Ошибка JSON: {e}")

def update_json_editor():
    """Обновление содержимого JSON редактора"""
    if st.session_state.results:
        clean_export = get_clean_results()
        st.session_state.json_editor_content = json.dumps(clean_export, ensure_ascii=False, indent=2)

def apply_json_changes():
    """Применение изменений из JSON редактора"""
    try:
        new_data = json.loads(st.session_state.json_editor_content)
        new_results = {}
        
        for page_key, page_data in new_data.items():
            if page_key.startswith('page_'):
                page_num = int(page_key.split('_')[1]) - 1
                new_results[page_num] = page_data
        
        st.session_state.results = new_results
        st.success("✅ Изменения JSON применены!")
        st.rerun()
        
    except json.JSONDecodeError:
        st.error("❌ Некорректный JSON формат")
    except Exception as e:
        st.error(f"❌ Ошибка применения изменений: {e}")

def get_clean_results() -> Dict[str, Any]:
    """Получение очищенных результатов для экспорта - ОБНОВЛЕНО"""
    clean_export = {}
    
    for page_idx, page_data in st.session_state.results.items():
        page_key = f"page_{page_idx + 1}"
        clean_page_data = {}
        
        # Отбираем только основные поля (исключаем uncertain_ поля)
        for field_name in ['full_name', 'series', 'number', 'registration_number', 'issue_date']:
            if field_name in page_data:
                clean_page_data[field_name] = page_data[field_name]
        
        clean_export[page_key] = clean_page_data
    
    return clean_export

def export_clean_results():
    """Экспорт очищенных результатов в JSON"""
    if not st.session_state.results:
        st.warning("Нет результатов для экспорта")
        return
    
    try:
        clean_export = get_clean_results()
        json_str = json.dumps(clean_export, ensure_ascii=False, indent=2)
        filename = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        st.download_button(
            "📥 Скачать результаты",
            data=json_str,
            file_name=filename,
            mime="application/json",
            type="primary"
        )
        
        st.success("✅ Файл готов к скачиванию!")
        
    except Exception as e:
        st.error(f"❌ Ошибка экспорта: {e}")

if __name__ == "__main__":
    main()
