import os
import json
import logging
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
DATA_FILE = "users.json"

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


def extract_telegram_user(inner):
    """يحاول يسحب اليوزر من كل الحقول الممكنة"""

    # 1. من customer_note
    note = str(inner.get('customer_note', '') or '')
    if note.strip():
        return note.lstrip('@').strip().lower()

    # 2. من customization (حقل مخصص في المتجر)
    customization = inner.get('customization', '') or ''
    if isinstance(customization, dict):
        for key, val in customization.items():
            val = str(val).lstrip('@').strip().lower()
            if val:
                return val
    if isinstance(customization, str) and customization.strip():
        return customization.lstrip('@').strip().lower()

    # 3. من custom_fields
    custom_fields = inner.get('custom_fields', []) or []
    if isinstance(custom_fields, list):
        for field in custom_fields:
            val = str(field.get('value', '') or '').lstrip('@').strip().lower()
            if val:
                return val
    if isinstance(custom_fields, dict):
        for key, val in custom_fields.items():
            val = str(val).lstrip('@').strip().lower()
            if val:
                return val

    # 4. من meta
    meta = inner.get('meta', {}) or {}
    if isinstance(meta, dict):
        for key, val in meta.items():
            if 'telegram' in str(key).lower() or 'user' in str(key).lower():
                return str(val).lstrip('@').strip().lower()

    return ''


@flask_app.route('/webhook/order', methods=['POST'])
def receive_order():
    data = request.json
    logging.info("Order received: " + str(data))

    inner = data.get('data', data)

    order_id = str(inner.get('id', 'غير محدد'))
    amount = str(inner.get('total', ''))
    currency = str(inner.get('currency', 'SAR'))

    # استخراج اليوزر
    telegram_user = extract_telegram_user(inner)
    logging.info("Extracted telegram user: '" + telegram_user + "'")

    # بيانات العميل
    customer = inner.get('customer', {}) or {}
    email = str(customer.get('email', ''))

    # المنتجات
    products = inner.get('products', []) or []
    product_names = []
    for p in products:
        name = p.get('name', '')
        if name:
            product_names.append(str(name))
    product_name = ', '.join(product_names) if product_names else 'منتج'

    # كود التفعيل
    digital_code = ''
    serials = inner.get('serial_numbers', []) or []
    if serials:
        digital_code = str(serials[0])
    if not digital_code:
        codes = inner.get('digital_codes', []) or []
        if codes:
            digital_code = str(codes[0])
    if not digital_code:
        digital_code = 'سيتم الارسال قريبا'

    file_url = str(inner.get('file_url', '') or '')

    if not telegram_user:
        logging.warning("No telegram user found in order data")
        return jsonify({"status": "no_telegram_user"}), 400

    users = load_users()
    chat_id = users.get(telegram_user)

    if not chat_id:
        logging.warning("User not found: " + telegram_user)
        logging.warning("Known users: " + str(list(users.keys())))
        return jsonify({"status": "user_not_found", "user": telegram_user}), 404

    message = (
        "تم تاكيد طلبك!\n\n"
        "رقم الطلب: " + order_id + "\n"
        "المنتج: " + product_name + "\n"
        "المبلغ: " + amount + " " + currency + "\n"
        "البريد: " + email + "\n\n"
        "كود التفعيل:\n" + digital_code + "\n\n"
        "شكرا لشرائك!"
    )

    send_message(chat_id, message)

    if file_url:
        send_document(chat_id, file_url, "ملف طلبك #" + order_id)

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
                "تم تسجيلك بنجاح\n"
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
