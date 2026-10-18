"""Обработчики сообщений и кнопок VK-бота.

Логика бота отделена от работы с API OpenWeatherMap: все запросы выполняются
через модуль ``weather_api``, а подготовка текста — через ``weather_format``.
Так как API-модуль синхронный, запросы уводятся из event loop через
``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import logging
import re

from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import GeoRule, TextRule

import keyboards
import weather_api
import weather_format

labeler = BotLabeler()
logger = logging.getLogger(__name__)

# Ожидаемое действие для каждого пользователя (лёгкая замена состояний).
PENDING_WEATHER = "weather"
PENDING_FORECAST = "forecast"
PENDING_COMPARE = "compare"
PENDING_AIR = "air"

_pending: dict[int, str] = {}

WELCOME = (
    "👋 Привет! Я погодный бот.\n\n"
    "Умею показывать текущую погоду, прогноз на 5 дней и качество воздуха, "
    "определять погоду по вашей геолокации и сравнивать города.\n\n"
    "Выберите кнопку ниже 👇"
)

HELP_TEXT = (
    "❓ Как пользоваться ботом\n\n"
    "🌤 Погода в городе — текущая погода по названию города.\n"
    "📍 Геолокация — нажмите кнопку «Отправить местоположение», "
    "и бот определит погоду в вашей точке.\n"
    "⚖️ Сравнить города — погода в двух городах и кто теплее.\n"
    "📅 Прогноз на 5 дней — прогноз по 3-часовым интервалам.\n"
    "🌫 Качество воздуха — индекс AQI и основные загрязнители.\n\n"
    "В любой момент можно вернуться в меню кнопкой «🏠 Меню»."
)

UNKNOWN_TEXT = (
    "🤔 Не понял сообщение. Нажмите кнопку меню или выберите действие ниже 👇"
)

CITY_PROMPT = "🌤 Напишите название города, например: Омск"
FORECAST_PROMPT = "📅 Напишите название города для прогноза, например: Москва"
AIR_PROMPT = "🌫 Напишите название города, например: Санкт-Петербург"
COMPARE_PROMPT = "⚖️ Напишите два города через запятую, например: Омск, Москва"
LOCATION_PROMPT = (
    "📍 Нажмите кнопку «Отправить местоположение», и я определю погоду "
    "в вашей точке."
)
CANCEL_TEXT = "✖️ Отменено. Возвращаю в меню."
CITY_RETRY = "⚠️ Не нашёл город «{city}». Попробуйте другое название или «✖️ Отмена»."


async def _show_main_menu(message: Message) -> None:
    """Отправляет главное меню."""
    _pending.pop(message.peer_id, None)
    await message.answer(WELCOME, keyboard=keyboards.main_menu())


@labeler.message(command=("start", 0))
@labeler.message(
    TextRule(["начать", "start", "меню", "menu", keyboards.BTN_MENU], ignore_case=True)
)
async def start_handler(message: Message) -> None:
    """Приветствие и главное меню."""
    await _show_main_menu(message)


@labeler.message(
    TextRule([keyboards.BTN_HELP, "помощь", "help"], ignore_case=True)
)
async def help_handler(message: Message) -> None:
    """Справка по командам."""
    _pending.pop(message.peer_id, None)
    await message.answer(HELP_TEXT, keyboard=keyboards.main_menu())


@labeler.message(TextRule(keyboards.BTN_WEATHER, ignore_case=True))
async def weather_start_handler(message: Message) -> None:
    """Запускает сценарий «текущая погода»."""
    _pending[message.peer_id] = PENDING_WEATHER
    await message.answer(CITY_PROMPT, keyboard=keyboards.input_keyboard())


@labeler.message(TextRule(keyboards.BTN_FORECAST, ignore_case=True))
async def forecast_start_handler(message: Message) -> None:
    """Запускает сценарий «прогноз на 5 дней»."""
    _pending[message.peer_id] = PENDING_FORECAST
    await message.answer(FORECAST_PROMPT, keyboard=keyboards.input_keyboard())


@labeler.message(TextRule(keyboards.BTN_AIR, ignore_case=True))
async def air_start_handler(message: Message) -> None:
    """Запускает сценарий «качество воздуха»."""
    _pending[message.peer_id] = PENDING_AIR
    await message.answer(AIR_PROMPT, keyboard=keyboards.input_keyboard())


@labeler.message(TextRule(keyboards.BTN_COMPARE, ignore_case=True))
async def compare_start_handler(message: Message) -> None:
    """Запускает сценарий «сравнение городов»."""
    _pending[message.peer_id] = PENDING_COMPARE
    await message.answer(COMPARE_PROMPT, keyboard=keyboards.input_keyboard())


@labeler.message(TextRule(keyboards.BTN_GEO, ignore_case=True))
async def geo_start_handler(message: Message) -> None:
    """Просит пользователя поделиться геолокацией."""
    _pending.pop(message.peer_id, None)
    await message.answer(LOCATION_PROMPT, keyboard=keyboards.location_keyboard())


@labeler.message(TextRule(keyboards.BTN_CANCEL, ignore_case=True))
async def cancel_handler(message: Message) -> None:
    """Отменяет текущий сценарий."""
    _pending.pop(message.peer_id, None)
    await message.answer(CANCEL_TEXT, keyboard=keyboards.main_menu())


@labeler.message(GeoRule())
async def location_handler(message: Message) -> None:
    """Обрабатывает присланную геолокацию: погода по координатам."""
    coordinates = message.geo.coordinates if message.geo else None
    if coordinates is None:
        await message.answer(
            "⚠️ Не удалось получить координаты. Попробуйте ещё раз.",
            keyboard=keyboards.location_keyboard(),
        )
        return

    _pending.pop(message.peer_id, None)
    await message.answer("🔎 Определяю погоду по вашей геолокации...")

    try:
        result = await asyncio.to_thread(
            weather_api.get_current_weather,
            lat=coordinates.latitude,
            lon=coordinates.longitude,
        )
    except weather_api.WeatherAppError as exc:
        await message.answer(f"⚠️ {exc}", keyboard=keyboards.main_menu())
        return

    await message.answer(
        weather_format.format_current_weather(result), keyboard=keyboards.main_menu()
    )


async def _handle_weather(message: Message, city: str) -> None:
    """Показывает текущую погоду в городе."""
    try:
        result = await asyncio.to_thread(weather_api.get_current_weather, city=city)
    except weather_api.CityNotFoundError:
        await message.answer(
            CITY_RETRY.format(city=city), keyboard=keyboards.input_keyboard()
        )
        return
    except weather_api.WeatherAppError as exc:
        _pending.pop(message.peer_id, None)
        await message.answer(f"⚠️ {exc}", keyboard=keyboards.main_menu())
        return

    _pending.pop(message.peer_id, None)
    await message.answer(
        weather_format.format_current_weather(result), keyboard=keyboards.main_menu()
    )


async def _handle_forecast(message: Message, city: str) -> None:
    """Показывает прогноз на 5 дней."""
    try:
        result = await asyncio.to_thread(weather_api.get_forecast, city=city)
    except weather_api.CityNotFoundError:
        await message.answer(
            CITY_RETRY.format(city=city), keyboard=keyboards.input_keyboard()
        )
        return
    except weather_api.WeatherAppError as exc:
        _pending.pop(message.peer_id, None)
        await message.answer(f"⚠️ {exc}", keyboard=keyboards.main_menu())
        return

    _pending.pop(message.peer_id, None)
    await message.answer(
        weather_format.format_forecast(result), keyboard=keyboards.main_menu()
    )


async def _handle_air(message: Message, city: str) -> None:
    """Показывает качество воздуха в городе."""
    try:
        result = await asyncio.to_thread(weather_api.get_air_quality, city=city)
    except weather_api.CityNotFoundError:
        await message.answer(
            CITY_RETRY.format(city=city), keyboard=keyboards.input_keyboard()
        )
        return
    except weather_api.WeatherAppError as exc:
        _pending.pop(message.peer_id, None)
        await message.answer(f"⚠️ {exc}", keyboard=keyboards.main_menu())
        return

    _pending.pop(message.peer_id, None)
    await message.answer(
        weather_format.format_air_quality(result), keyboard=keyboards.main_menu()
    )


async def _handle_compare(message: Message, text: str) -> None:
    """Сравнивает погоду в двух городах."""
    cities = [part.strip() for part in re.split(r"[,;]| и ", text) if part.strip()]
    if len(cities) < 2:
        await message.answer(
            "⚠️ Нужно два города. Например: Омск, Москва",
            keyboard=keyboards.input_keyboard(),
        )
        return

    results = []
    for city in cities[:2]:
        try:
            results.append(
                await asyncio.to_thread(weather_api.get_current_weather, city=city)
            )
        except weather_api.CityNotFoundError:
            await message.answer(
                CITY_RETRY.format(city=city), keyboard=keyboards.input_keyboard()
            )
            return
        except weather_api.WeatherAppError as exc:
            _pending.pop(message.peer_id, None)
            await message.answer(f"⚠️ {exc}", keyboard=keyboards.main_menu())
            return

    _pending.pop(message.peer_id, None)
    await message.answer(
        weather_format.format_comparison(results), keyboard=keyboards.main_menu()
    )


PENDING_HANDLERS = {
    PENDING_WEATHER: _handle_weather,
    PENDING_FORECAST: _handle_forecast,
    PENDING_AIR: _handle_air,
    PENDING_COMPARE: _handle_compare,
}


@labeler.message()
async def fallback_handler(message: Message) -> None:
    """Обрабатывает текст, введённый в рамках активного сценария."""
    action = _pending.get(message.peer_id)
    handler = PENDING_HANDLERS.get(action) if action else None

    if handler is None:
        await message.answer(UNKNOWN_TEXT, keyboard=keyboards.main_menu())
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer(
            "⚠️ Пустое сообщение. Введите текст или нажмите «✖️ Отмена».",
            keyboard=keyboards.input_keyboard(),
        )
        return

    await handler(message, text)
