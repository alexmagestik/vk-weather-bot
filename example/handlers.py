"""Обработчики сообщений и кнопок бота."""

import logging
from typing import Any

from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules import ABCRule
from vkbottle.dispatch.rules.base import TextRule

import keyboards
import services

labeler = BotLabeler()
logger = logging.getLogger(__name__)

# Эмодзи-нумерация для списка услуг в каталоге
NUMBER_EMOJI = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")

GREETING = (
    "👋 Привет!\n\n"
    "Я AI-бот разработчика.\n\n"
    "Помогу узнать больше об услугах по разработке AI-решений, "
    "автоматизации и созданию ботов.\n\n"
    "Выберите нужный раздел:"
)

CATALOG_HEADER = "🤖 Каталог AI-услуг\n\nВыберите интересующую услугу:\n\n"

PRICE_HEADER = "💰 ПРАЙС-ЛИСТ\n\n"

PRICE_FOOTER = "💡 Итоговая стоимость зависит от сложности проекта."

ABOUT_TEXT = (
    "ℹ️ Об AI-разработке\n\n"
    "Разрабатываем AI-решения для бизнеса:\n\n"
    "🤖 интеллектуальные боты;\n"
    "⚙️ автоматизация рутинных процессов;\n"
    "🧠 интеграция LLM;\n"
    "📚 RAG-системы;\n"
    "🌐 AI-консультанты;\n"
    "🔌 интеграция внешних API.\n\n"
    "Основная цель — автоматизировать рутинные задачи\n"
    "и сделать работу с клиентами быстрее и удобнее."
)

CONTACT_TEXT = (
    "📩 Связаться с разработчиком\n\n"
    "Если вас заинтересовала разработка AI-решения,\n"
    "напишите сообщение с описанием вашей задачи.\n\n"
    "В сообщении желательно указать:\n\n"
    "• какую задачу нужно автоматизировать;\n"
    "• какие системы используются сейчас;\n"
    "• примерный объём проекта;\n"
    "• желаемые сроки.\n\n"
    "После этого мы сможем оценить проект и предложить решение.\n\n"
    "✉️ VK: @alex_magestik"
)

UNKNOWN_TEXT = (
    "🤔 Я пока не умею отвечать на произвольные вопросы.\n\n"
    "Используйте кнопки меню, чтобы посмотреть каталог услуг\n"
    "и прайс-лист."
)

CATALOG_UNAVAILABLE = "⚠️ Каталог услуг временно недоступен. Попробуйте позже."

SERVICE_NOT_FOUND = "⚠️ Услуга не найдена. Откройте каталог и выберите услугу из списка."


class ServiceRule(ABCRule[Message]):
    """Срабатывает, если текст сообщения совпадает с названием услуги из каталога.

    Названия услуг не хардкодятся: правило каждый раз сверяется с JSON-файлом.
    """

    async def check(self, message: Message) -> dict[str, Any] | bool:
        service = services.get_service_by_name(message.text)
        if service is None:
            return False
        return {"service": service}


def build_catalog_text(all_services: list[dict[str, Any]]) -> str:
    """Формирует текст списка услуг с нумерацией."""
    lines = []
    for index, service in enumerate(all_services):
        number = NUMBER_EMOJI[index] if index < len(NUMBER_EMOJI) else f"{index + 1}."
        lines.append(f"{number} {service['name']}")
    return CATALOG_HEADER + "\n".join(lines)


def build_service_card(service: dict[str, Any]) -> str:
    """Формирует текст карточки услуги."""
    price = services.format_price(
        service["price_from"], service.get("currency", "RUB")
    )
    lines = [
        str(service["short_name"]),
        "",
        "Описание:",
        str(service["description"]),
        "",
        f"💰 Цена: от {price}",
        "",
        f"⏱ Срок: {service['duration']}",
        "",
        "Используем:",
    ]
    lines.extend(f"• {tech}" for tech in service.get("technologies", []))
    lines.extend(["", "Выберите действие:"])
    return "\n".join(lines)


def build_price_list(all_services: list[dict[str, Any]]) -> str:
    """Формирует текст прайс-листа по всем услугам."""
    lines = [PRICE_HEADER]
    for service in all_services:
        price = services.format_price(
            service["price_from"], service.get("currency", "RUB")
        )
        lines.extend([f"{service['short_name']}", f"от {price}", ""])
    lines.append(PRICE_FOOTER)
    return "\n".join(lines)


@labeler.message(command=("start", 0))
@labeler.message(TextRule("начать", ignore_case=True))
async def start_handler(message: Message) -> None:
    """Показывает приветствие и главное меню."""
    await message.answer(GREETING, keyboard=keyboards.main_menu())


@labeler.message(TextRule(keyboards.BTN_MAIN_MENU, ignore_case=True))
async def main_menu_handler(message: Message) -> None:
    """Возвращает пользователя в главное меню."""
    await message.answer(GREETING, keyboard=keyboards.main_menu())


@labeler.message(TextRule(keyboards.BTN_CATALOG, ignore_case=True))
async def catalog_handler(message: Message) -> None:
    """Показывает каталог услуг из JSON-файла."""
    all_services = services.get_all_services()
    if not all_services:
        await message.answer(CATALOG_UNAVAILABLE, keyboard=keyboards.back_to_menu())
        return
    await message.answer(
        build_catalog_text(all_services),
        keyboard=keyboards.catalog(all_services),
    )


@labeler.message(ServiceRule())
async def service_handler(message: Message, service: dict[str, Any]) -> None:
    """Показывает карточку выбранной услуги."""
    await message.answer(
        build_service_card(service),
        keyboard=keyboards.service_card(),
    )


@labeler.message(TextRule([keyboards.BTN_PRICE_LIST, keyboards.BTN_PRICE], ignore_case=True))
async def price_list_handler(message: Message) -> None:
    """Показывает прайс-лист по всем услугам."""
    all_services = services.get_all_services()
    if not all_services:
        await message.answer(CATALOG_UNAVAILABLE, keyboard=keyboards.back_to_menu())
        return
    await message.answer(
        build_price_list(all_services),
        keyboard=keyboards.back_to_menu(),
    )


@labeler.message(TextRule([keyboards.BTN_CONTACT, keyboards.BTN_ORDER], ignore_case=True))
async def contact_handler(message: Message) -> None:
    """Показывает контактную информацию."""
    await message.answer(CONTACT_TEXT, keyboard=keyboards.back_to_menu())


@labeler.message(TextRule(keyboards.BTN_ABOUT, ignore_case=True))
async def about_handler(message: Message) -> None:
    """Показывает информацию о компании."""
    await message.answer(ABOUT_TEXT, keyboard=keyboards.back_to_menu())


@labeler.message(TextRule(keyboards.BTN_BACK, ignore_case=True))
async def back_handler(message: Message) -> None:
    """Возвращает пользователя в каталог услуг."""
    all_services = services.get_all_services()
    if not all_services:
        await message.answer(CATALOG_UNAVAILABLE, keyboard=keyboards.back_to_menu())
        return
    await message.answer(
        build_catalog_text(all_services),
        keyboard=keyboards.catalog(all_services),
    )


@labeler.message()
async def unknown_message_handler(message: Message) -> None:
    """Отвечает на любое неизвестное сообщение и показывает главное меню."""
    logger.info("Неизвестное сообщение от пользователя: %r", message.text)
    await message.answer(UNKNOWN_TEXT, keyboard=keyboards.main_menu())
