import requests
from loguru import logger
import re
from django.conf import settings

# Get Telegram configuration from Django settings
ALERTBOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
ALERT_GROUP_ID = settings.TELEGRAM_ALERT_GROUP_ID
THREAD_ID = settings.TELEGRAM_THREAD_ID


def tg_send_adminalert(tg_message, clean_html=True):
    if clean_html:
        clean_message = check_html_exit_symbols(tg_message)
    else:
        clean_message = tg_message

    # Quick debug - just log if token is missing
    if not ALERTBOT_TOKEN:
        logger.error("ALERTBOT_TOKEN is not set!")
        return

    url = f"https://api.telegram.org/bot{ALERTBOT_TOKEN}/sendMessage"
    params = {
        'chat_id': ALERT_GROUP_ID,
        'text': clean_message,
        'parse_mode': 'HTML'
    }
    
    if THREAD_ID:
        params['message_thread_id'] = THREAD_ID
    
    response = requests.get(url, params=params)
    logger.warning(f"Sent alert to Admin with: {tg_message}")
    
    # Only log if there's an error
    if response.status_code != 200:
        logger.error(f"Telegram API error: {response.status_code} - {response.text}")


def check_html_exit_symbols(incoming_message):
    if '<' in incoming_message:
        outgoing_message = re.sub('<', '&lt;', incoming_message)
    else:
        outgoing_message = incoming_message
    return outgoing_message