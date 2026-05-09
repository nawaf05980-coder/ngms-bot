import os
import json
import logging
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
STORE_API_KEY = os.getenv("STORE_API_KEY")
PORT = int(os.getenv("PORT", 8080))
DATA_FILE = "users.json"
STORE_API = "https://api.rzpos.com/api/v1"

logging.basicConfig(level=logging.INFO)
flask_app = Flask(__name__)


def load_users():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


def send_message(chat_id, text):
    requests.post(
        "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )


def send_document(chat_id, file_url, caption):
    requests.post(
        "https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument",
        json={"chat_id": chat_id, "document": file_url, "caption": caption}
    )


def get_order_cards(order_id):
    """يجيب البطاقات الرقمية من API المتجر"""
    try:
        headers = {
            "Authorization": "Bearer " + STORE_API_KEY,
            "Accept": "application/json"
        }
        url = STORE_API + "/orders/" + str(order_id)
        resp = requests.get(url, headers=headers, timeout=10)
        logging.info("Store API response: " + str(resp.status_code) + " " + resp.text[:500])

        if resp.status_code == 200:
            data = resp.json()
            order = data.get('data', data)

            # البطاقات الرقمية
            serials = order.get('serial_numbers', []) or []
            if serials:
                return serials

            cards = order.get('cards', []) or []
            if cards:
                return cards

            digital_codes = order.get('digital_codes', []) or []
            if digital_codes:
                return digital_codes

            # من items
            items = order.get('items', []) or []
            for item in items:
                serials = item.get('serial_numbers', []) or []
                if serials:
                    return serials
                codes = item.get('digital_codes', []) or []
                if codes:
                    return codes

    except Exception as e:
        logging.error("Error fetching order: " + str(e))
    return []


def format_card(card):
    """يحول البطاقة لنص"""
    if isinstance(card, str):
        return card
    if isinstance(card, dict):
        email = card.get('email', '') or card.get('username', '') or ''
        password = card.get('password', '') or card.get('code', '') or ''
        if email and password:
            return "الايميل: " + email + "\nالباسورد: " + password
        elif email:
            return email
        elif password:
            return password
        else:
            return str(card)
    return str(card)


@flask_app.route('/webhook/order', methods=['POST'])
def receive_order():
    data = request.json
    logging.info("Order received: " + str(data)[:200])

    inner = data.get('data', data)

    order_id = str(inner.get('id', ''))
    amount = str(inner.get('total', '0.00'))
    currency = str(inner.get('currency', 'SAR'))

    # اليوزر من items -> fields
    telegram_user = ''
    items = inner.get('items', []) or []
    for item in items:
        fields = item.get('fields', []) or []
        for field in fields:
            value = str(field.get('value', '') or '').lstrip('@').strip().lower()
            if value:
                telegram_user = value
                break

    logging.info("Telegram user: '" + telegram_user + "'")

    # اسم المنتج
    product_names = []
    for item in items:
        name = (item.get('item') or {}).get('name', '') or item.get('name', '')
        if name:
            product_names.append(str(name))
    product_name = ', '.join(product_names) if product_names else 'منتج'

    # بيانات العميل
    customer = inner.get('customer', {}) or {}
    email = str(customer.get('email', ''))

    if not telegram_user:
        logging.warning("No telegram user found")
        return jsonify({"status": "no_telegram_user"}), 400

    users = load_users()
    chat_id = users.get(telegram_user)

    if not chat_id:
        logging.warning("User not found: " + telegram_user)
        return jsonify({"status": "user_not_found", "user": telegram_user}), 404

    # جيب البطاقة من API المتجر
    cards = get_order_cards(order_id)
    logging.info("Cards found: " + str(cards))

    if cards:
        card_text = format_card(cards[0])
    else:
        card_text = 'سيتم التواصل معك قريباً'

    message = (
        "✅ تم تاكيد طلبك!\n\n"
        "رقم الطلب: " + order_id + "\n"
        "المنتج: " + product_name + "\n"
        "المبلغ: " + amount + " " + currency + "\n\n"
        "━━━━━━━━━━━━━\n"
        "بيانات التسليم:\n"
        + card_text + "\n"
        "━━━━━━━━━━━━━\n\n"
        "شكرا لشرائك! 🎉"
    )

    send_message(chat_id, message)

    return jsonify({"status": "sent"}), 200


@flask_app.route('/', methods=['GET'])
def home():
    users = load_users()
    return "Bot is running! Users: " + str(len(users)), 200


@flask_app.route('/telegram', methods=['POST'])
def telegram_webhook():
    data = request.json
    if not data or 'message' not in data:
        return 'ok'

    message = data['message']
    chat_id = message['chat']['id']
    username = message.get('from', {}).get('username', '').lower()
    text = message.get('text', '')
    first_name = message.get('from', {}).get('first_name', '')

    if text == '/start':
        if username:
            users = load_users()
            users[username] = chat_id
            save_users(users)
            send_message(chat_id,
                "مرحبا " + first_name + "!\n"
                "تم تسجيلك بنجاح ✅\n"
                "سيتم ارسال تفاصيل طلباتك هنا تلقائيا.\n"
                "يوزرك: @" + username
            )
        else:
            send_message(chat_id,
                "حسابك ما عنده يوزر.\n"
                "اضف username من اعدادات تيليجرام ثم اكتب /start."
            )
    elif text == '/help':
        send_message(chat_id,
            "كيفية الاستخدام:\n"
            "١. اكتب /start لتسجيل حسابك\n"
            "٢. عند الطلب من المتجر ادخل يوزرك\n"
            "٣. ستصلك تفاصيل الطلب هنا فور الدفع"
        )

    return 'ok'


def set_webhook():
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    if domain:
        url = "https://" + domain + "/telegram"
        requests.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/setWebhook",
            json={"url": url}
        )
        print("Webhook set: " + url)


if __name__ == '__main__':
    set_webhook()
    flask_app.run(host='0.0.0.0', port=PORT)
