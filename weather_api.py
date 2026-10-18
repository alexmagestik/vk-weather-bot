"""Модуль доступа к API OpenWeatherMap.

Здесь собрана вся работа с внешним сервисом: HTTP-запросы, повторы при сбоях,
разбор ответов и кэширование. Модуль не знает ничего о CLI или VK-боте, поэтому
его используют оба интерфейса:

    * ``weather_app.py`` — консольное приложение;
    * ``handlers.py``    — VK-бот.

Все функции возвращают простые структуры данных (dataclasses / dict), чтобы их
можно было форматировать отдельно (см. ``weather_format.py``).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Конечные точки OpenWeatherMap.
GEOCODING_URL = "http://api.openweathermap.org/geo/1.0/direct"
REVERSE_GEOCODING_URL = "http://api.openweathermap.org/geo/1.0/reverse"
CURRENT_WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "http://api.openweathermap.org/data/2.5/forecast"
AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

# Файл кэша и срок его «годности».
CACHE_FILE = Path(__file__).parent / "weather_cache.json"
CACHE_TTL = timedelta(hours=3)

# Паузы между повторами запроса (секунды): до len(RETRY_DELAYS) повторов.
RETRY_DELAYS = [1, 10, 60]
REQUEST_TIMEOUT = 10  # таймаут одного HTTP-запроса, секунд

# Допуск при сравнении координат (~1 км).
COORD_TOLERANCE = 0.01

# Человекочитаемые названия индекса качества воздуха (AQI).
AQI_LABELS = {
    1: "Хорошо",
    2: "Удовлетворительно",
    3: "Умеренное загрязнение",
    4: "Плохо",
    5: "Очень плохо",
}


class WeatherAppError(Exception):
    """Ошибка приложения с понятным сообщением для пользователя."""


class NetworkError(WeatherAppError):
    """Нет свежего ответа из-за сети или лимита запросов."""


class CityNotFoundError(WeatherAppError):
    """Город не найден геокодером."""


@dataclass(frozen=True)
class CityLocation:
    """Результат геокодинга: название города и его координаты."""

    name: str
    lat: float
    lon: float
    country: str | None = None


@dataclass
class WeatherResult:
    """Данные о погоде/прогнозе/воздухе вместе с метаданными."""

    city: str
    lat: float
    lon: float
    data: dict
    from_cache: bool = False
    age_seconds: float | None = None


def describe_aqi(value: int | None) -> str:
    """Возвращает словесное описание индекса качества воздуха."""
    return AQI_LABELS.get(value, "неизвестно")


# ----------------------------- HTTP-слой ---------------------------------


def _describe_status(status: int, context: str) -> str:
    """Возвращает человекочитаемое описание HTTP-статуса на русском."""
    if status == 401:
        return "Невалидный API-ключ. Проверьте OPENWEATHER_API_KEY в файле .env."
    if status == 404:
        return f"Данные не найдены (ошибка 404) при обращении к {context}."
    if status == 429:
        return "Превышен лимит запросов (ошибка 429). Повторите попытку позже."
    if 500 <= status < 600:
        return f"Ошибка на стороне сервера погоды ({status}). Повторите позже."
    return f"Сервер вернул статус {status} при обращении к {context}."


def _get_with_retries(url: str, params: dict) -> requests.Response:
    """Выполняет GET с ретраями на 429 и временные сетевые ошибки.

    При успехе или не-ретраибельном статусе возвращает Response.
    Если ретраи исчерпаны — бросает NetworkError.
    """
    attempts = len(RETRY_DELAYS) + 1  # первая попытка + повторы
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            if attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                logger.warning(
                    "Сетевая ошибка (%s). Повтор через %s сек...",
                    exc.__class__.__name__,
                    delay,
                )
                time.sleep(delay)
                continue
            raise NetworkError(
                "Нет связи с сервером погоды после нескольких попыток."
            ) from exc

        if response.status_code == 429:
            if attempt < len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt]
                logger.warning("Превышен лимит запросов (429). Повтор через %s сек...", delay)
                time.sleep(delay)
                continue
            raise NetworkError("Сервер ограничил частоту запросов (429). Повторите позже.")

        return response

    # Досюда дойти нельзя, но оставим защиту на случай изменения логики.
    raise NetworkError("Не удалось получить ответ от сервера погоды.")


def _request_json(url: str, params: dict, context: str) -> dict | list:
    """Выполняет запрос и возвращает разобранный JSON либо бросает ошибку."""
    if not OPENWEATHER_API_KEY:
        raise WeatherAppError(
            "Не задан OPENWEATHER_API_KEY. Создайте файл .env со строкой "
            "OPENWEATHER_API_KEY=<ваш_ключ>."
        )

    full_params = {**params, "appid": OPENWEATHER_API_KEY}
    response = _get_with_retries(url, full_params)

    if response.status_code != 200:
        raise WeatherAppError(_describe_status(response.status_code, context))

    try:
        return response.json()
    except ValueError as exc:
        raise WeatherAppError(
            f"Сервер вернул некорректный ответ (не JSON) при обращении к {context}."
        ) from exc


def _localized_name(entry: dict, fallback: str = "?") -> str:
    """Возвращает русское название из geocoding-ответа, если оно есть."""
    local_names = entry.get("local_names") or {}
    return str(local_names.get("ru") or entry.get("name") or fallback)


# ----------------------------- Публичные API ------------------------------


def geocode_city(city: str) -> CityLocation:
    """Превращает название города в координаты (lat, lon)."""
    query = (city or "").strip()
    if not query:
        raise WeatherAppError("Название города не может быть пустым.")

    data = _request_json(GEOCODING_URL, {"q": query, "limit": 1}, "геокодеру")
    if not data:
        raise CityNotFoundError(f"Город «{city}» не найден. Проверьте название.")

    first = data[0]
    try:
        lat = float(first["lat"])
        lon = float(first["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherAppError("Геокодер вернул некорректные координаты города.") from exc

    return CityLocation(
        name=_localized_name(first, query),
        lat=lat,
        lon=lon,
        country=first.get("country"),
    )


def reverse_geocode(lat: float, lon: float) -> str:
    """Определяет название населённого пункта по координатам."""
    data = _request_json(
        REVERSE_GEOCODING_URL,
        {"lat": lat, "lon": lon, "limit": 1},
        "обратному геокодеру",
    )
    if not data:
        return f"{lat:.2f}, {lon:.2f}"
    return _localized_name(data[0], f"{lat:.2f}, {lon:.2f}")


def get_weather_by_coordinates(lat: float, lon: float) -> dict:
    """Возвращает словарь с текущей погодой по координатам."""
    data = _request_json(
        CURRENT_WEATHER_URL,
        {"lat": lat, "lon": lon, "units": "metric", "lang": "ru"},
        "серверу погоды",
    )
    if not isinstance(data, dict) or "main" not in data or "weather" not in data:
        raise WeatherAppError("В ответе сервера не хватает данных о погоде.")
    return data


def get_forecast_by_coordinates(lat: float, lon: float) -> dict:
    """Возвращает почасовой прогноз (3 часа) на 5 дней."""
    data = _request_json(
        FORECAST_URL,
        {"lat": lat, "lon": lon, "units": "metric", "lang": "ru"},
        "серверу прогноза",
    )
    if not isinstance(data, dict) or "list" not in data:
        raise WeatherAppError("В ответе сервера не хватает данных прогноза.")
    return data


def get_air_pollution_by_coordinates(lat: float, lon: float) -> dict:
    """Возвращает данные о загрязнении воздуха."""
    data = _request_json(
        AIR_POLLUTION_URL,
        {"lat": lat, "lon": lon},
        "серверу качества воздуха",
    )
    if not isinstance(data, dict) or not data.get("list"):
        raise WeatherAppError("В ответе сервера нет данных о качестве воздуха.")
    return data


# ----------------------------- Кэш ---------------------------------------


def _coords_match(a_lat, a_lon, b_lat, b_lon) -> bool:
    """Сравнивает координаты с небольшим допуском."""
    try:
        return (
            abs(float(a_lat) - float(b_lat)) < COORD_TOLERANCE
            and abs(float(a_lon) - float(b_lon)) < COORD_TOLERANCE
        )
    except (TypeError, ValueError):
        return False


def load_cache() -> list[dict]:
    """Читает список записей кэша. Возвращает [] для отсутствующего/битого файла."""
    if not CACHE_FILE.exists():
        return []
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    # Поддержка старого формата: одна запись-словарь вместо списка.
    if isinstance(raw, dict):
        raw = [raw] if "data" in raw else []

    if not isinstance(raw, list):
        return []

    return [r for r in raw if isinstance(r, dict) and "data" in r]


def _write_cache(records: list[dict]) -> None:
    """Записывает список записей в файл кэша."""
    try:
        CACHE_FILE.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Не удалось сохранить кэш: %s", exc)


def save_cache(city: str, lat: float, lon: float, data: dict) -> None:
    """Добавляет новую запись кэша или обновляет существующую по координатам."""
    records = load_cache()
    record = {
        "city": city,
        "lat": lat,
        "lon": lon,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

    # Убираем прежние записи по этим координатам и добавляем свежую,
    # чтобы не копить дубликаты близких точек.
    records = [
        r for r in records if not _coords_match(r.get("lat"), r.get("lon"), lat, lon)
    ]
    records.append(record)

    _write_cache(records)


def cache_age_seconds(record: dict) -> float | None:
    """Возраст записи кэша в секундах или None, если метку времени не прочитать."""
    raw = record.get("fetched_at")
    if not raw:
        return None
    try:
        fetched_at = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - fetched_at).total_seconds()


def is_fresh(record: dict) -> bool:
    """Свежая ли запись (моложе CACHE_TTL)."""
    age = cache_age_seconds(record)
    return age is not None and age < CACHE_TTL.total_seconds()


def find_cache_record(
    city: str | None = None, lat: float | None = None, lon: float | None = None
) -> dict | None:
    """Ищет запись кэша по координатам (приоритетно) или по названию города."""
    records = load_cache()
    if lat is not None and lon is not None:
        for record in records:
            if _coords_match(record.get("lat"), record.get("lon"), lat, lon):
                return record
        return None
    if city is not None:
        target = city.strip().lower()
        for record in records:
            if str(record.get("city", "")).strip().lower() == target:
                return record
    return None


def _record_to_result(record: dict) -> WeatherResult:
    """Превращает запись кэша в WeatherResult."""
    return WeatherResult(
        city=str(record.get("city") or "?"),
        lat=float(record.get("lat") or 0.0),
        lon=float(record.get("lon") or 0.0),
        data=record.get("data") or {},
        from_cache=True,
        age_seconds=cache_age_seconds(record),
    )


def find_cached_weather(
    city: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    fresh_only: bool = True,
) -> WeatherResult | None:
    """Возвращает сохранённую погоду из кэша (по городу или координатам)."""
    record = find_cache_record(city=city, lat=lat, lon=lon)
    if record is None:
        return None
    if fresh_only and not is_fresh(record):
        return None
    return _record_to_result(record)


# ----------------------------- Высокоуровневые операции --------------------


def get_current_weather(
    city: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    use_cache: bool = True,
) -> WeatherResult:
    """Текущая погода по городу или координатам (с учётом кэша)."""
    if city and lat is None:
        if use_cache:
            cached = find_cached_weather(city=city)
            if cached:
                return cached
        location = geocode_city(city)
        lat, lon = location.lat, location.lon

    if lat is None or lon is None:
        raise WeatherAppError("Укажите название города или координаты.")

    if use_cache:
        cached = find_cached_weather(lat=lat, lon=lon)
        if cached:
            return cached

    data = get_weather_by_coordinates(lat, lon)
    name = data.get("name") or city or f"{lat:.2f}, {lon:.2f}"
    save_cache(name, lat, lon, data)
    return WeatherResult(city=name, lat=lat, lon=lon, data=data)


def get_forecast(
    city: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> WeatherResult:
    """Прогноз погоды (3-часовые интервалы) на 5 дней."""
    if city and lat is None:
        location = geocode_city(city)
        lat, lon = location.lat, location.lon

    if lat is None or lon is None:
        raise WeatherAppError("Укажите название города или координаты.")

    data = get_forecast_by_coordinates(lat, lon)
    name = (data.get("city") or {}).get("name") or city or f"{lat:.2f}, {lon:.2f}"
    return WeatherResult(city=name, lat=lat, lon=lon, data=data)


def get_air_quality(
    city: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> WeatherResult:
    """Данные о загрязнении воздуха по городу или координатам."""
    if city and lat is None:
        location = geocode_city(city)
        lat, lon = location.lat, location.lon

    if lat is None or lon is None:
        raise WeatherAppError("Укажите название города или координаты.")

    data = get_air_pollution_by_coordinates(lat, lon)
    name = city or reverse_geocode(lat, lon)
    return WeatherResult(city=name, lat=lat, lon=lon, data=data)
