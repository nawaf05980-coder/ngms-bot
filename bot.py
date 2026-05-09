import os
import logging
import threading
import requests
from flask import Flask, request, jsonify
from telegram.ext import Updater, CommandHandler
from telegram import Update

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

user_chat_ids = {}
logging.basicConfig(level=logging.INFO)
flask_app = Flask(__name__)


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
        "تفاصيل الطلب:\n"
        "رقم الطلب: " + str(order_id) + "\n"
        "المنتج: " + str(product_name) + "\n"
        "المبلغ: " + str(amount) + " " + str(currency) + "\n"
        "البريد: " + str(email) + "\n\n"
        "كود التفعيل:\n"
        + str(digital_code) + "\n\n"
        "شكرا لشرائك!"
    )

    requests.post(
        "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
        json={"chat_id": chat_id, "text": message}
    )

    if file_url:
        requests.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument",
            json={"chat_id": chat_id, "document": file_url}
        )

    return jsonify({"status": "sent"}), 200


@flask_app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200


def start(update, context):
    user = update.effective_user
    username = (user.username or "").lower()
    chat_id = update.effective_chat.id
    if username:
        user_chat_ids[username] = chat_id
        update.message.reply_text(
            "مرحبا " + user.first_name + "!\n"
            "تم تسجيلك بنجاح\n"
            "سيتم ارسال تفاصيل طلباتك هنا تلقائيا.\n"
            "يوزرك: @" + username
        )
    else:
        update.message.reply_text(
            "حسابك ما عنده يوزر.\n"
            "اضف username من اعدادات تيليجرام ثم اكتب /start."
        )


def help_command(update, context):
    update.message.reply_text(
        "كيفية الاستخدام:\n"
        "١. اكتب /start لتسجيل حسابك\n"
        "٢. عند الطلب من المتجر ادخل يوزرك\n"
        "٣. ستصلك تفاصيل الطلب هنا فور الدفع"
    )


def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT)


if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    print("البوت شغال!")
    updater.start_polling()
    updater.idle()
