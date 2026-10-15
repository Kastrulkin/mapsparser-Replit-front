"""Owner-dialogue presentation values, independent of a Telegram SDK installation."""
from dataclasses import dataclass

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ForceReply
except ModuleNotFoundError:
    @dataclass
    class WebAppInfo:
        url: str

    @dataclass
    class InlineKeyboardButton:
        text: str
        callback_data: str | None = None
        url: str | None = None
        web_app: WebAppInfo | None = None

    @dataclass
    class InlineKeyboardMarkup:
        inline_keyboard: list

    @dataclass
    class ForceReply:
        selective: bool = False
        input_field_placeholder: str | None = None
