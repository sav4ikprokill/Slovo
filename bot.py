import json
import os
import logging
import pytz
from datetime import datetime, time, timedelta, timezone
from telegram import Update, ReplyKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

TOKEN = os.getenv("7829591487:AAE9S2TUleAftie5609_WfLvZbAL3ZiWIjQ")
VERSES_FILE = "verses_nrp_365.json"
USERS_FILE = "users.json"

MoscowTZ = pytz.timezone("Europe/Moscow")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHOOSING_TIME = 1

def load_verses():
    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def format_verse(verse):
    header = "🕊️ *Слово на сегодня* 🕊️\n"
    body = f"*{verse['reference']}*\n{verse['text']}"
    if verse.get("comment"):
        body += f"\n\n_{verse['comment']}_"
    prayer = "\n\n🙏 Помолись сегодня и попроси Бога быть рядом."
    return header + body + prayer

def get_verse_for_user(user_id, verses, force_new=False):
    users = load_users()
    user = users.setdefault(str(user_id), {"next_verse_index": 0})
    today = datetime.now().strftime("%Y-%m-%d")

    if force_new or user.get("last_sent") != today:
        index = user["next_verse_index"] % len(verses)
        user["current_verse"] = index
        user["next_verse_index"] = index + 1
        user["last_sent"] = today
        save_users(users)
    else:
        index = user.get("current_verse", 0)
    return verses[index]

def start(update: Update, context: CallbackContext):
    kb = [["📖 Слово на день", "🙏 Молитвенная просьба"],
          ["🤔 Почему Бог?", "❤️ Принять Иисуса"],
          ["⚙️ Настроить время"]]
    update.message.reply_text("Добро пожаловать! Я здесь, чтобы делиться с тобой Божьим Словом каждый день. ✝️", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

def slovo(update: Update, context: CallbackContext):
    verses = load_verses()
    verse = get_verse_for_user(update.effective_user.id, verses)
    update.message.reply_text(format_verse(verse), parse_mode=ParseMode.MARKDOWN)

def prayer(update: Update, context: CallbackContext):
    update.message.reply_text("✍ Напиши свою молитвенную нужду, и я передам её молитвенной команде.")

def why_god(update: Update, context: CallbackContext):
    update.message.reply_text("🤍 Бог — это Любовь. Он создал тебя не случайно, а с целью. Если хочешь, Я могу рассказать больше.")

def accept_jesus(update: Update, context: CallbackContext):
    update.message.reply_text("❤️ Если ты хочешь принять Иисуса — просто скажи от сердца:\n\n«Господь Иисус, прости мои грехи. Войди в мою жизнь. Я верю, что Ты умер и воскрес. Я принимаю Тебя как своего Господа и Спасителя. Аминь.»")

def settime_entry(update: Update, context: CallbackContext):
    update.message.reply_text("🕒 Введи удобное время в формате ЧЧ:ММ (например, 08:30):")
    return CHOOSING_TIME

def settime_received(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    users = load_users()
    text = update.message.text.strip()

    try:
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError("Неверный формат времени")

        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError("Время вне диапазона")

        users.setdefault(user_id, {})["time"] = f"{h:02d}:{m:02d}"
        save_users(users)

        context.job_queue.run_daily(
            callback=send_daily_verse,
            time=time(h, m, tzinfo=MoscowTZ),
            context=int(user_id),
            name=f"verse_{user_id}"
        )
        update.message.reply_text(f"✅ Время рассылки установлено на {h:02d}:{m:02d}")
        return ConversationHandler.END

    except Exception as e:
        logger.warning(f"[ОШИБКА УСТАНОВКИ ВРЕМЕНИ] {e}")
        update.message.reply_text("⚠️ Неверный формат. Пожалуйста, введи время в виде ЧЧ:ММ (например, 08:30):")
        return CHOOSING_TIME

def send_daily_verse(context: CallbackContext):
    user_id = context.job.context
    logger.info(f"🔔 send_daily_verse вызван для user_id={user_id}")
    verses = load_verses()
    verse = get_verse_for_user(user_id, verses, force_new=True)
    try:
        context.bot.send_message(chat_id=user_id, text=format_verse(verse), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"✅ Стих отправлен пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки стиха {user_id}: {e}")

def handle_text(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    if "слово" in text:
        return slovo(update, context)
    elif "молитв" in text:
        return prayer(update, context)
    elif "почему" in text:
        return why_god(update, context)
    elif "иисус" in text:
        return accept_jesus(update, context)
    elif "время" in text:
        return settime_entry(update, context)

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    logger.info(f"⏰ Серверное время: {datetime.now()}")

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("settime", settime_entry),
            MessageHandler(Filters.regex("(?i)настроить время"), settime_entry)
        ],
        states={CHOOSING_TIME: [MessageHandler(Filters.text & ~Filters.command, settime_received)]},
        fallbacks=[],
        allow_reentry=True
    )

    dp.add_handler(conv)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("slovo", slovo))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    users = load_users()
    for uid, info in users.items():
        try:
            if "time" in info:
                h, m = map(int, info["time"].split(":"))
                updater.job_queue.run_daily(
                    callback=send_daily_verse,
                    time=time(h, m, tzinfo=MoscowTZ),
                    context=int(uid),
                    name=f"verse_{uid}"
                )
                logger.info(f"[ЗАДАЧА СОЗДАНА] user_id={uid} на {h:02d}:{m:02d}")
        except Exception as e:
            logger.error(f"[ОШИБКА ПЛАНИРОВКИ] uid={uid}: {e}")

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
