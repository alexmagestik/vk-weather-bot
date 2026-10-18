"""Клавиатуры бота: главное меню, каталог, карточка услуги и навигация."""

from typing import Any

from vkbottle import Keyboard, KeyboardButtonColor, Text

# Тексты кнопок (используются и в клавиатурах, и в правилах обработчиков)
BTN_CATALOG = "🤖 Каталог услуг"
BTN_PRICE_LIST = "💰 Прайс-лист"
BTN_CONTACT = "📩 Связаться"
BTN_ABOUT = "ℹ️ О компании"
BTN_BACK = "⬅️ Назад"
BTN_MAIN_MENU = "🏠 Главное меню"
BTN_PRICE = "💰 Прайс"
BTN_ORDER = "📩 Заказать"


def _service_button(service: dict[str, Any]) -> Text:
    """Создаёт кнопку услуги с payload, содержащим её id."""
    return Text(
        label=str(service["short_name"]),
        payload={"service_id": service.get("id", "")},
    )


def main_menu() -> str:
    """Клавиатура главного меню."""
    keyboard = Keyboard()
    keyboard.add(Text(BTN_CATALOG), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text(BTN_PRICE_LIST), color=KeyboardButtonColor.POSITIVE)
    keyboard.row()
    keyboard.add(Text(BTN_CONTACT), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Text(BTN_ABOUT), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def catalog(services: list[dict[str, Any]]) -> str:
    """Клавиатура каталога: по кнопке на каждую услугу плюс навигация."""
    keyboard = Keyboard()
    for index, service in enumerate(services):
        if index > 0:
            keyboard.row()
        keyboard.add(_service_button(service), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text(BTN_MAIN_MENU), color=KeyboardButtonColor.PRIMARY)
    return keyboard.get_json()


def service_card() -> str:
    """Клавиатура карточки услуги."""
    keyboard = Keyboard()
    keyboard.add(Text(BTN_PRICE), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text(BTN_ORDER), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text(BTN_BACK), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Text(BTN_MAIN_MENU), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def back_to_menu() -> str:
    """Клавиатура с единственной кнопкой возврата в главное меню."""
    keyboard = Keyboard()
    keyboard.add(Text(BTN_MAIN_MENU), color=KeyboardButtonColor.PRIMARY)
    return keyboard.get_json()
