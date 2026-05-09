import os
import json
import logging
import threading
import requests
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("8770116377:AAE5PjXbZUuNnBe39NgUSYYpi40xV3Pm7n0")
WEBHOOK_PORT = int(os.getenv("PORT", 5000))

user_chat_ids = {}
logging.basicConfig(level=logging.INFO)
flask_app = Flask(__name__)

@flask_app.route('/webhook/order', methods=['POST'])
def receive_order():
    data = request.json
    telegram_user = data.get('telegram_username', '').lstrip('@').lower()
    order_id      = data.get('order_id', 'غير محدد')
    email         = data.get('customer_email', '')
    product_name  = data.get('product_name', '')
    digital_code  = data.get('digital_code', 'غير متاح')
    file_url      = data.get('file_url', '')
    amount        = data.get('amount', '')
    currency      = data.get('currency', 'SAR')

    chat_id = user_chat_ids.get(telegram_user)
    if not chat_id:
        return jsonify({"status": "user_not_found"}), 404

    message = (
        f"✅ *تم تأكيد طلبك!*\n\n"
        f"📦 *تفاصيل الطلب*\n"
        f"• رقم الطلب: `{order_id}`\n"
        f"• المنتج: {product_name}\n"
        f"• المبلغ: {amount} {currency}\n"
        f"• البريد: {email}\n\n"
        f"🔑 *كود التفعيل*\n"
        f"`{digital_code}`\n\n"
        f"شكراً لشرائك! 🎉"
    )

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    )

    if file_url:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            json={"chat_id": chat_id, "document": file_url, "caption": f"📎 ملف طلبك #{order_id}"}
        )

    return jsonify({"status": "sent"}), 200

@flask_app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = (user.username or "").lower()
    chat_id = update.effective_chat.id
    if username:
        user_chat_ids[username] = chat_id
        await update.message.reply_text(
            f"مرحباً {user.first_name}! 👋\n\n"
            f"تم تسجيلك بنجاح ✅\n"
            f"سيتم إرسال تفاصيل طلباتك هنا تلقائياً.\n\n"
            f"يوزرك المسجل: @{username}"
        )
    else:
        await update.message.reply_text(
            "⚠️ حسابك ما عنده يوزر.\n"
            "أضف username من إعدادات تيليجرام ثم اكتب /start مجدداً."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *كيفية الاستخدام:*\n\n"
        "١. اكتب /start لتسجيل حسابك\n"
        "٢. عند الطلب من المتجر أدخل يوزرك\n"
        "٣. ستصلك تفاصيل الطلب هنا فور الدفع",
        parse_mode="Markdown"
    )

def run_flask():
    flask_app.run(host='0.0.0.0', port=WEBHOOK_PORT)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    print("🤖 البوت شغال!")
    app.run_polling()
