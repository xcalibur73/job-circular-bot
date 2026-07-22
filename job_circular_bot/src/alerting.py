"""
Sends you a quick Telegram message when something needs your attention:
  - a source failed to fetch (site changed its layout, went down, etc.)
  - a notice got flagged by the guardrails and was skipped instead of posted

This is what replaces "manual approval of every post" in fully-automatic
mode: you don't review the good posts, but you do get pinged about the
weird ones, same day, so you can fix the config before it happens again.

Setup: message @BotFather on Telegram to create a bot and get a token,
then message your new bot once and call
https://api.telegram.org/bot<token>/getUpdates to find your chat_id.
Both go into environment variables / GitHub Actions secrets.
"""

import os
import logging
import requests

logger = logging.getLogger("alerting")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured, alert not sent: %s", message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        logger.error("Failed to send Telegram alert: %s", e)
