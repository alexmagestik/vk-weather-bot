"""CLI-приложение для получения погоды (OpenWeatherMap).

Возможности:
  * меню: погода по городу/координатам, сравнение городов, прогноз на 5 дней,
    качество воздуха, определение города по координатам, выход;
  * обработка ошибок без трейсбеков (неверный статус, пустой геокодинг,
    невалидный ключ, сетевые сбои);
  * кэш успешных ответов в weather_cache.json (свежая запись моложе 3 часов
    отдаётся из кэша без обращения к API);
  * ретраи при 429 и временных сетевых ошибках (пауза 1s, 10s, 60s).

Вся работа с API вынесена в модуль ``weather_api``, а форматирование — в
``weather_format``. Этот файл отвечает только за консольный интерфейс.
"""

from __future__ import annotations

import logging
import re

import weather_api
import weather_format

YES_ANSWERS = {"д", "да", "y", "yes", "+", "1"}

MENU = """
===== Погода =====
1 — Погода по названию города
2 — Погода по координатам
3 — Сравнить два города
4 — Прогноз на 5 дней
5 — Качество воздуха
6 — Геолокация: определить город по координатам
0 — Выход"""


def _print_result(text: str) -> None:
    """Печатает блок результата с пустыми строками вокруг."""
    print()
    print(text)
    print()


def _read_coordinates() -> tuple[float, float] | None:
    """Считывает и валидирует координаты, введённые пользователем."""
    raw = input("Введите координаты через запятую (lat, lon): ").strip()
    if not raw:
        print("[!] Пустой ввод координат.")
        return None

    parts = [p for p in re.split(r"[,\s;]+", raw) if p]
    if len(parts) != 2:
        print("[!] Нужно две координаты через запятую, например: 55.75, 37.62")
        return None

    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        print("[!] Координаты должны быть числами (разделитель дробной части — точка).")
        return None

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        print("[!] Широта должна быть в диапазоне -90..90, долгота -180..180.")
        return None

    return lat, lon


def _read_two_cities() -> tuple[str, str] | None:
    """Считывает названия двух городов для сравнения."""
    raw = input("Введите два города через запятую (например, Омск, Москва): ").strip()
    parts = [p.strip() for p in re.split(r"[,;]| и ", raw) if p.strip()]
    if len(parts) < 2:
        print("[!] Нужно два города. Разделите их запятой или словом «и».")
        return None
    return parts[0], parts[1]


def _offer_cache(
    city: str | None = None, lat: float | None = None, lon: float | None = None
) -> None:
    """Предлагает показать сохранённые данные, если запрос к API не удался."""
    result = weather_api.find_cached_weather(
        city=city, lat=lat, lon=lon, fresh_only=False
    )
    if result is None:
        print("[!] Кэшированных данных нет — показать нечего.")
        return

    age = weather_format.humanize_age(result.age_seconds)
    try:
        answer = input(
            f"Есть сохранённые данные для «{result.city}» ({age}). Показать? (д/н): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if answer in YES_ANSWERS:
        _print_result(weather_format.format_current_weather(result, emoji=False))
    else:
        print("Хорошо, кэш не показываю.")


def _ask_city(prompt: str = "Введите название города: ") -> str | None:
    """Считывает название города, проверяя, что оно не пустое."""
    city = input(prompt).strip()
    if not city:
        print("[!] Название города не может быть пустым.")
        return None
    return city


def _run_city_flow() -> None:
    """Пункт 1: погода по названию города."""
    city = _ask_city()
    if city is None:
        return
    try:
        result = weather_api.get_current_weather(city=city)
    except weather_api.NetworkError as exc:
        print(f"[!] {exc}")
        _offer_cache(city=city)
        return
    except weather_api.WeatherAppError as exc:
        print(f"[!] {exc}")
        return
    _print_result(weather_format.format_current_weather(result, emoji=False))


def _run_coords_flow() -> None:
    """Пункт 2: погода по координатам."""
    coords = _read_coordinates()
    if coords is None:
        return
    lat, lon = coords
    try:
        result = weather_api.get_current_weather(lat=lat, lon=lon)
    except weather_api.NetworkError as exc:
        print(f"[!] {exc}")
        _offer_cache(lat=lat, lon=lon)
        return
    except weather_api.WeatherAppError as exc:
        print(f"[!] {exc}")
        return
    _print_result(weather_format.format_current_weather(result, emoji=False))


def _run_compare_flow() -> None:
    """Пункт 3: сравнение погоды в двух городах."""
    pair = _read_two_cities()
    if pair is None:
        return

    results = []
    for city in pair:
        try:
            results.append(weather_api.get_current_weather(city=city))
        except weather_api.WeatherAppError as exc:
            print(f"[!] {exc}")
            return
    _print_result(weather_format.format_comparison(results, emoji=False))


def _run_forecast_flow() -> None:
    """Пункт 4: прогноз на 5 дней по городу."""
    city = _ask_city()
    if city is None:
        return
    try:
        result = weather_api.get_forecast(city=city)
    except weather_api.WeatherAppError as exc:
        print(f"[!] {exc}")
        return
    _print_result(weather_format.format_forecast(result, emoji=False))


def _run_air_flow() -> None:
    """Пункт 5: качество воздуха по городу."""
    city = _ask_city()
    if city is None:
        return
    try:
        result = weather_api.get_air_quality(city=city)
    except weather_api.WeatherAppError as exc:
        print(f"[!] {exc}")
        return
    _print_result(weather_format.format_air_quality(result, emoji=False))


def _run_geolocation_flow() -> None:
    """Пункт 6: определить город по координатам и показать погоду."""
    coords = _read_coordinates()
    if coords is None:
        return
    lat, lon = coords

    try:
        name = weather_api.reverse_geocode(lat, lon)
        print(f"[i] Определённый населённый пункт: {name}")
        result = weather_api.get_current_weather(lat=lat, lon=lon)
    except weather_api.WeatherAppError as exc:
        print(f"[!] {exc}")
        return
    _print_result(weather_format.format_current_weather(result, emoji=False))


ACTIONS = {
    "1": _run_city_flow,
    "2": _run_coords_flow,
    "3": _run_compare_flow,
    "4": _run_forecast_flow,
    "5": _run_air_flow,
    "6": _run_geolocation_flow,
}


def main() -> None:
    """Главный цикл CLI-меню."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    if not weather_api.OPENWEATHER_API_KEY:
        print("[!] Не задан OPENWEATHER_API_KEY.")
        print("    Создайте файл .env со строкой: OPENWEATHER_API_KEY=<ваш_ключ>")
        return

    try:
        while True:
            print(MENU)
            choice = input("Выберите действие: ").strip()

            if choice == "0":
                print("До встречи!")
                break

            action = ACTIONS.get(choice)
            if action is None:
                print("[!] Неизвестный пункт меню. Введите число от 1 до 6 или 0.")
                continue

            try:
                action()
            except (KeyboardInterrupt, EOFError):
                raise
            except Exception as exc:  # защита от трейсбеков на непредвиденных сбоях
                print(f"[!] Произошла непредвиденная ошибка: {exc}")
    except (KeyboardInterrupt, EOFError):
        print("\nВыход.")


if __name__ == "__main__":
    main()
