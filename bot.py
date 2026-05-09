import os
import logging
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

user_chat_ids = {}
logging.basicConfig(level=logging.INFO)
flask_app = Flask(__name__)


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


@flask_app.route('/webhook/order', methods=['POST'])
def receive_order():
    data = request.json
    telegram_user = data.get('telegram_username', '').lstrip('@').lower()
    order_id = data.get('order_id', 'غير محدد')
    email = data.get('customer_email', '')
    product_name = data.get('product_name', '')
    digital_code = data.get('digital_code', 'غير متاح')
    file_url = data.get('file_url', '')
    amount = data.get('amount', '')
    currency = data.get('currency', 'SAR')

    chat_id = user_chat_ids.get(telegram_user)
    if not chat_id:
        return jsonify({"status": "user_not_found"}), 404

    message = (
        "تم تاكيد طلبك!\n\n"
        "رقم الطلب: " + str(order_id) + "\n"
        "المنتج: " + str(product_name) + "\n"
        "المبلغ: " + str(amount) + " " + str(currency) + "\n"
        "البريد: " + str(email) + "\n\n"
        "كود التفعيل:\n" + str(digital_code) + "\n\n"
        "شكرا لشرائك!"
    )

    send_message(chat_id, message)

    if file_url:
        send_document(chat_id, file_url, "ملف طلبك #" + str(order_id))

    return jsonify({"status": "sent"}), 200


@flask_app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200


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
            user_chat_ids[username] = chat_id
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
