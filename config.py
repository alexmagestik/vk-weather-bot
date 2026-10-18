"""Конфигурация VK-бота: загрузка .env, токен и HTTP-клиент."""

from __future__ import annotations

import os
import ssl

import certifi
from aiohttp import TCPConnector
from dotenv import load_dotenv
from vkbottle import AiohttpClient

# Загружаем переменные окружения из файла .env (если он существует).
load_dotenv()


def get_vk_token() -> str:
    """Возвращает токен сообщества VK из переменной окружения VK_TOKEN."""
    token = os.getenv("VK_TOKEN")
    if not token:
        raise RuntimeError(
            "Переменная VK_TOKEN не найдена. "
            "Создайте файл .env и добавьте строку: VK_TOKEN=ваш_токен"
        )
    return token


def get_openweather_key() -> str | None:
    """Возвращает ключ OpenWeatherMap из переменной окружения."""
    return os.getenv("OPENWEATHER_API_KEY")


def create_http_client() -> AiohttpClient:
    """Создаёт HTTP-клиент с корневыми SSL-сертификатами из certifi.

    Это нужно, например, на macOS с Python от python.org, где стандартный
    SSL-контекст не видит корневые сертификаты и запросы к api.vk.ru падают
    с ошибкой CERTIFICATE_VERIFY_FAILED.
    """
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return AiohttpClient(connector=TCPConnector(ssl=ssl_context))
