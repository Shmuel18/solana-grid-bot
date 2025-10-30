"""Telegram notifications handler."""

import logging
import threading

import requests

from ..config.settings import config


def send_telegram_message(message: str) -> None:
    """Send non-blocking telegram notification."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    def _send_sync() -> None:
        try:
            requests.post(url, data=payload, timeout=5)
        except Exception as e:
            logging.exception("Telegram notify failed: %s", e)

    threading.Thread(target=_send_sync, daemon=True).start()