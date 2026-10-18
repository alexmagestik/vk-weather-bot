"""Точка входа VK-бота: создание бота, подключение обработчиков и Long Poll."""

from __future__ import annotations

import asyncio
import logging
import sys

from vkbottle import API, Bot, VKAPIError

import weather_api
from config import create_http_client, get_vk_token
from handlers import labeler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def run_bot(token: str) -> None:
    """Собирает и запускает бота в асинхронной среде."""
    api = API(token, http_client=create_http_client())
    bot = Bot(api=api)

    @bot.error_handler.register_error_handler(VKAPIError)
    async def vk_api_error_handler(error: VKAPIError) -> None:
        logger.error("Ошибка VK API %s: %s", error.code, error.error_msg)

    bot.labeler.load(labeler)

    logger.info("Бот запущен, ожидаю сообщения (Long Poll)...")
    await bot.run_polling()


def main() -> None:
    """Точка входа приложения."""
    if not weather_api.OPENWEATHER_API_KEY:
        logger.error(
            "Не задан OPENWEATHER_API_KEY. Добавьте его в файл .env: "
            "OPENWEATHER_API_KEY=ваш_ключ"
        )
        sys.exit(1)

    try:
        token = get_vk_token()
    except RuntimeError as error:
        logger.error("%s", error)
        sys.exit(1)

    try:
        asyncio.run(run_bot(token))
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")


if __name__ == "__main__":
    main()
