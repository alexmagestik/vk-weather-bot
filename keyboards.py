"""Клавиатуры VK-бота: главное меню, ввод текста и запрос геолокации."""

from vkbottle import Keyboard, KeyboardButtonColor, Location, Text

# Тексты кнопок (используются и в клавиатурах, и в правилах обработчиков).
BTN_WEATHER = "🌤 Погода в городе"
BTN_GEO = "📍 Геолокация"
BTN_COMPARE = "⚖️ Сравнить города"
BTN_FORECAST = "📅 Прогноз на 5 дней"
BTN_AIR = "🌫 Качество воздуха"
BTN_HELP = "❓ Помощь"
BTN_MENU = "🏠 Меню"
BTN_CANCEL = "✖️ Отмена"


def main_menu() -> str:
    """Главное меню бота."""
    keyboard = Keyboard(one_time=False)
    keyboard.add(Text(BTN_WEATHER), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text(BTN_GEO), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text(BTN_COMPARE), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text(BTN_FORECAST), color=KeyboardButtonColor.POSITIVE)
    keyboard.row()
    keyboard.add(Text(BTN_AIR), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Text(BTN_HELP), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def input_keyboard() -> str:
    """Клавиатура для шагов, где пользователь вводит текст."""
    keyboard = Keyboard(one_time=False)
    keyboard.add(Text(BTN_CANCEL), color=KeyboardButtonColor.NEGATIVE)
    keyboard.add(Text(BTN_MENU), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def location_keyboard() -> str:
    """Клавиатура с кнопкой отправки геолокации."""
    keyboard = Keyboard(one_time=False)
    keyboard.add(Location(), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text(BTN_CANCEL), color=KeyboardButtonColor.NEGATIVE)
    keyboard.add(Text(BTN_MENU), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()
