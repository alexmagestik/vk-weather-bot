"""Работа с каталогом услуг: чтение data/services.json и форматирование цен."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent / "data" / "services.json"

# Символы валют, которые мы умеем отображать
CURRENCY_SYMBOLS: dict[str, str] = {"RUB": "₽"}


def load_services() -> list[dict[str, Any]]:
    """Читает каталог услуг из JSON-файла.

    При отсутствии или повреждении файла логирует понятную ошибку
    и возвращает пустой список, чтобы бот не падал.
    """
    try:
        with open(DATA_FILE, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        logger.error("Файл каталога не найден: %s", DATA_FILE)
        return []
    except json.JSONDecodeError as error:
        logger.error("Некорректный JSON в файле %s: %s", DATA_FILE, error)
        return []

    services_list = data.get("services")
    if not isinstance(services_list, list):
        logger.error(
            "В файле %s нет списка услуг (ожидается ключ 'services' со списком)",
            DATA_FILE,
        )
        return []

    return services_list


def get_all_services() -> list[dict[str, Any]]:
    """Возвращает список всех услуг из каталога."""
    return load_services()


def get_service_by_id(service_id: str) -> dict[str, Any] | None:
    """Ищет услугу по её id. Возвращает None, если услуга не найдена."""
    for service in load_services():
        if service.get("id") == service_id:
            return service
    return None


def get_service_by_name(name: str) -> dict[str, Any] | None:
    """Ищет услугу по названию (name или short_name) без учёта регистра."""
    query = name.strip().casefold()
    if not query:
        return None
    for service in load_services():
        names = (
            str(service.get("name", "")).casefold(),
            str(service.get("short_name", "")).casefold(),
        )
        if query in names:
            return service
    return None


def format_price(price: int, currency: str = "RUB") -> str:
    """Форматирует цену: 35000 -> '35 000 ₽'."""
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    formatted_number = f"{price:,}".replace(",", " ")
    return f"{formatted_number} {symbol}"
