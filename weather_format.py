"""Форматирование данных OpenWeatherMap в человекочитаемый текст.

Модуль не делает HTTP-запросов и не зависит от интерфейса: его функции
принимают ``weather_api.WeatherResult`` и возвращают готовую строку. Флаг
``emoji`` позволяет получить оформление для VK-бота (с иконками) или более
строгий текст для CLI.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from datetime import datetime

import weather_api

MONTHS_RU = [
    "янв", "фев", "мар", "апр", "мая", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]
WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def _prefixer(emoji: bool):
    """Возвращает функцию, добавляющую иконку к строке (или нет)."""

    def prefix(icon: str, text: str) -> str:
        return f"{icon} {text}" if emoji else text

    return prefix


def _temp(value) -> str:
    """Форматирует температуру: 8.23 -> '+8°C'."""
    try:
        return f"{float(value):+.0f}°C"
    except (TypeError, ValueError):
        return "?"


def humanize_age(seconds: float | None) -> str:
    """Человекочитаемый возраст данных кэша."""
    if seconds is None:
        return "неизвестно когда"
    minutes = int(seconds // 60)
    if minutes < 1:
        return "только что"
    if minutes < 60:
        return f"{minutes} мин назад"
    return f"{minutes // 60} ч назад"


def _format_date(raw: str) -> str:
    """'2026-10-18' -> '18 окт, сб'."""
    try:
        date = datetime.strptime(raw, "%Y-%m-%d")
    except (TypeError, ValueError):
        return raw
    return f"{date.day} {MONTHS_RU[date.month - 1]}, {WEEKDAYS_RU[date.weekday()]}"


def format_current_weather(result: weather_api.WeatherResult, emoji: bool = True) -> str:
    """Текущая погода одним сообщением."""
    data = result.data
    main = data.get("main", {}) or {}
    weather = (data.get("weather") or [{}])[0]
    wind = data.get("wind", {}) or {}
    p = _prefixer(emoji)

    lines = [
        p("🌤", f"Погода в «{result.city}»"),
        p("📍", f"Координаты: {result.lat:.2f}, {result.lon:.2f}"),
        p(
            "🌡",
            f"Температура: {_temp(main.get('temp'))} "
            f"(ощущается как {_temp(main.get('feels_like'))})",
        ),
        p("📝", f"Состояние: {weather.get('description', 'нет данных')}"),
        p(
            "💧",
            f"Влажность: {main.get('humidity', '?')}%, "
            f"давление {main.get('pressure', '?')} гПа",
        ),
        p("💨", f"Ветер: {wind.get('speed', '?')} м/с"),
    ]

    if result.from_cache:
        lines.append(p("🕒", f"Данные из кэша ({humanize_age(result.age_seconds)})"))

    return "\n".join(lines)


def format_forecast(
    result: weather_api.WeatherResult, emoji: bool = True, days: int = 5
) -> str:
    """Прогноз на несколько дней: мин/макс температура и основное состояние."""
    p = _prefixer(emoji)
    grouped: "OrderedDict[str, list[dict]]" = OrderedDict()

    for item in result.data.get("list", []):
        date = (item.get("dt_txt") or "")[:10]
        if date:
            grouped.setdefault(date, []).append(item)

    lines = [p("📅", f"Прогноз на {days} дней — «{result.city}»"), ""]

    for date, items in list(grouped.items())[:days]:
        temps = [
            (item.get("main") or {}).get("temp")
            for item in items
            if (item.get("main") or {}).get("temp") is not None
        ]
        descriptions = Counter(
            (item.get("weather") or [{}])[0].get("description", "") for item in items
        )
        description = descriptions.most_common(1)[0][0] if descriptions else ""

        if temps:
            temperature_range = f"{min(temps):+.0f}…{max(temps):+.0f}°C"
        else:
            temperature_range = "?"

        extra = f", {description}" if description else ""
        lines.append(p("•", f"{_format_date(date)}: {temperature_range}{extra}"))

    return "\n".join(lines).rstrip()


def _city_block(result: weather_api.WeatherResult, emoji: bool) -> list[str]:
    """Блок с погодой одного города для сравнения."""
    data = result.data
    main = data.get("main", {}) or {}
    weather = (data.get("weather") or [{}])[0]
    wind = data.get("wind", {}) or {}

    if emoji:
        return [
            f"🌍 {result.city}",
            f"🌡 {_temp(main.get('temp'))} (ощущается как {_temp(main.get('feels_like'))})",
            f"📝 {weather.get('description', '?')}",
            f"💧 {main.get('humidity', '?')}%, {main.get('pressure', '?')} гПа",
            f"💨 {wind.get('speed', '?')} м/с",
        ]
    return [
        f"{result.city}",
        f"  Температура: {_temp(main.get('temp'))} "
        f"(ощущается как {_temp(main.get('feels_like'))})",
        f"  Состояние: {weather.get('description', '?')}",
        f"  Влажность: {main.get('humidity', '?')}%, {main.get('pressure', '?')} гПа",
        f"  Ветер: {wind.get('speed', '?')} м/с",
    ]


def format_comparison(results: list[weather_api.WeatherResult], emoji: bool = True) -> str:
    """Сравнение погоды в нескольких городах с выводом «победителя»."""
    p = _prefixer(emoji)
    lines = [p("⚖️", "Сравнение городов"), ""]

    for index, result in enumerate(results):
        if index:
            lines.append("")
        lines.extend(_city_block(result, emoji))

    temperatures = []
    for result in results:
        temp = (result.data.get("main") or {}).get("temp")
        if temp is not None:
            temperatures.append((result, temp))

    if len(temperatures) == 2:
        warmer, warmest = max(temperatures, key=lambda pair: pair[1])
        colder, coldest = min(temperatures, key=lambda pair: pair[1])
        lines.append("")
        lines.append(
            p(
                "🏆",
                f"Теплее: {warmer.city} ({_temp(warmest)} против {_temp(coldest)} "
                f"у «{colder.city}»)",
            )
        )

    return "\n".join(lines)


def format_air_quality(result: weather_api.WeatherResult, emoji: bool = True) -> str:
    """Качество воздуха: индекс AQI и основные вещества."""
    p = _prefixer(emoji)
    entry = (result.data.get("list") or [{}])[0]
    aqi = (entry.get("main") or {}).get("aqi")
    components = entry.get("components", {}) or {}

    lines = [
        p("🌫", f"Качество воздуха — «{result.city}»"),
        p("📊", f"Индекс AQI: {aqi} — {weather_api.describe_aqi(aqi)}"),
    ]

    for key, label in (
        ("pm2_5", "PM2.5"),
        ("pm10", "PM10"),
        ("no2", "NO₂"),
        ("o3", "O₃"),
        ("so2", "SO₂"),
        ("co", "CO"),
    ):
        value = components.get(key)
        if value is not None:
            lines.append(p("🧪", f"{label}: {value} мкг/м³"))

    return "\n".join(lines)
