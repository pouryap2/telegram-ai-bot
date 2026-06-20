"""
ربات هوشمند تلگرام با Google Gemini
ساخته‌شده برای اجرای رایگان (لوکال یا روی Render.com)
"""

import os
import asyncio
import logging
import threading

from flask import Flask
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- تنظیمات اولیه ----------

load_dotenv()  # برای اجرای لوکال، مقادیر رو از فایل .env می‌خونه

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 10000))
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

if not TELEGRAM_TOKEN:
    raise SystemExit("❌ متغیر TELEGRAM_BOT_TOKEN تنظیم نشده. توکن رو از BotFather بگیر.")
if not GEMINI_API_KEY:
    raise SystemExit("❌ متغیر GEMINI_API_KEY تنظیم نشده. کلید رو از aistudio.google.com بگیر.")

genai.configure(api_key=GEMINI_API_KEY)


# ---------- بارگذاری اطلاعات اختصاصی ربات ----------

def load_knowledge() -> str:
    """اطلاعاتی که می‌خوای ربات بلد باشه رو از فایل knowledge.txt می‌خونه."""
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


KNOWLEDGE = load_knowledge()

SYSTEM_PROMPT = f"""تو یک دستیار هوشمند، دوستانه و مودب هستی که به زبان فارسی پاسخ می‌دی.
وظیفه‌ات اینه که با تکیه بر اطلاعاتی که در پایین آورده شده، به کاربر کمک کنی.

قوانین مهم:
- اگه سوال کاربر با اطلاعات زیر مرتبطه، دقیق و بر اساس همون اطلاعات جواب بده.
- اگه سوالی عمومی بود (مثل سلام و احوال‌پرسی یا سوالات عمومی)، عادی و دوستانه جواب بده.
- اگه جواب دقیق سوال رو توی اطلاعات زیر نداری و موضوع تخصصی/اختصاصیه، صادقانه بگو نمی‌دونی؛ حدس نزن.
- کوتاه، خوانا و مودبانه پاسخ بده.

اطلاعات اختصاصی:
{KNOWLEDGE if KNOWLEDGE else "(فعلاً هیچ اطلاعاتی تعریف نشده. فایل knowledge.txt رو پر کن.)"}
"""

# حافظه گفتگو برای هر کاربر (در حافظه برنامه؛ با ری‌استارت ربات پاک می‌شه)
user_sessions: dict[int, "genai.ChatSession"] = {}


def get_chat_session(user_id: int):
    if user_id not in user_sessions:
        model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
        user_sessions[user_id] = model.start_chat(history=[])
    return user_sessions[user_id]


# ---------- دستورات ربات ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋\n"
        "من یه ربات هوشمندم و آماده‌ام بهت کمک کنم.\n\n"
        "فقط پیامت رو بنویس و بفرست.\n\n"
        "دستورات:\n"
        "/reset — پاک کردن حافظه گفتگو\n"
        "/help — راهنما"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "کافیه پیامت رو عادی بنویسی، من جواب می‌دم.\n"
        "اگه می‌خوای ربات همه‌چیز رو فراموش کنه و از نو شروع کنیم: /reset"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("حافظه گفتگو پاک شد ✅ از نو شروع می‌کنیم.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        chat = get_chat_session(user_id)
        # send_message کتابخونه جمینای sync هست، با to_thread جلوی بلاک‌شدن ربات رو می‌گیریم
        response = await asyncio.to_thread(chat.send_message, text)
        reply = response.text
    except Exception:
        logger.exception("خطا در گرفتن پاسخ از هوش مصنوعی")
        reply = "ببخشید، یه مشکلی پیش اومد 🙏 لطفاً دوباره امتحان کن."

    await update.message.reply_text(reply)


# ---------- یک سرور کوچک Flask فقط برای زنده نگه‌داشتن سرویس روی Render ----------

def run_flask():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "ربات روشن و فعاله ✅"

    app.run(host="0.0.0.0", port=PORT)


def main():
    threading.Thread(target=run_flask, daemon=True).start()

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ ربات شروع به کار کرد...")
    application.run_polling()


if __name__ == "__main__":
    main()