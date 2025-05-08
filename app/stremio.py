import glob
import importlib
from app.main import app
import logging
import os

logger = logging.getLogger(__name__)

# Log the current working directory to verify correct path resolution
logger.info(f"Current working directory: {os.getcwd()}")

# Find all `api.py` modules inside `app/parsers`
# Використовуємо os.path.join для кращої сумісності
search_pattern = os.path.join("app", "parsers", "**", "api.py")
module_paths = glob.glob(search_pattern, recursive=True)

# Import each found module
for module_path in module_paths:
    # --- Оновлена логіка конвертації шляху в назву модуля ---
    # Нормалізуємо шлях для поточної ОС (напр., замінить / на \ на Windows)
    normalized_path = os.path.normpath(module_path)
    # Розділяємо шлях на компоненти
    path_parts = normalized_path.split(os.sep)
    # Видаляємо розширення .py з останнього компонента
    path_parts[-1] = path_parts[-1][:-3]
    # Об'єднуємо компоненти через крапку, щоб отримати назву модуля
    module_name = ".".join(path_parts)
    # --- Кінець оновленої логіки ---

    logger.info(f"Found module path: {module_path}")
    logger.info(f"Attempting to import module: {module_name}")
    try:
        # Динамічно імпортуємо модуль
        imported_module = importlib.import_module(module_name)
        logger.info(f"Successfully imported {module_name}")

        # --- Додатково: Перевірка та включення роутера ---
        # Перевіряємо, чи є в імпортованому модулі змінна 'router'
        # і чи є вона екземпляром APIRouter (потрібно імпортувати APIRouter)
        from fastapi import APIRouter
        if hasattr(imported_module, 'router') and isinstance(imported_module.router, APIRouter):
             # Потрібно мати доступ до об'єкту 'app' з main.py
             # Якщо 'app' не імпортується напряму, цей підхід може не спрацювати
             # і реєстрацію роутерів краще залишити в main.py
             # Якщо app імпортовано:
             # from app.main import app
             # app.include_router(imported_module.router)
             # logger.info(f"Included router from {module_name}")
             pass # Поки що просто логуємо імпорт, реєстрацію залишимо в main.py
        # --- Кінець додаткової перевірки ---

    except ImportError as e:
        logger.error(f"Failed to import {module_name}: {e}")
        # Можна проігнорувати помилку або підняти її далі, якщо потрібно
        # raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred importing {module_name}: {e}")
