import os
import time
import json
import pathlib
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "inclusionai/ling-3.0-flash-sante:free")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT_PER_USER", "5"))
COOLDOWN = int(os.getenv("COOLDOWN_SEC", "10"))

if DEEPSEEK_KEY:
    API_KEY = DEEPSEEK_KEY
    MODEL = DEEPSEEK_MODEL
    BASE_URL = f"{DEEPSEEK_BASE}/v1/chat/completions"
    PROVIDER = "deepseek"
else:
    API_KEY = OPENROUTER_KEY
    MODEL = OPENROUTER_MODEL
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    PROVIDER = "openrouter"

if not TELEGRAM_TOKEN:
    print("ОШИБКА: в .env добавь TELEGRAM_TOKEN=... от @BotFather")
    exit(1)
if not API_KEY:
    print("ОШИБКА: нет DEEPSEEK_API_KEY / OPENROUTER_API_KEY")
    exit(1)

SYSTEM_PROMPT = """Ты - кроткий православный наставник.
Отвечай КРАТКО: 4-6 предложений, без воды.

Структура:
1. Короткое утешение без осуждения (1-2 предложения).
2. Если уместно - ОДНА точная цитата из Библии с источником (Мф. 11:28, 1 Ин. 1:9, Пс. 50:12). Если нет - пропусти.
3. Краткий совет: молитва (ТОЛЬКО "Отче наш" или "Господи Иисусе Христе, Сыне Божий, помилуй мя грешного"), разговор с близким, совет сходить в храм.
4. Напомни про таинство ТОЛЬКО если просят отпустить грехи: "Разрешение грехов дает только священник в храме". Не повторяй каждый раз.
5. Один короткий вопрос для размышления.
Не выдумывай молитвы, не ставь епитимью. Если суицид - дай 8-800-2000-122.
"""

RATE_FILE = pathlib.Path("rate_limit_tg.json")
DONORS_FILE = pathlib.Path("donors.json")
YOOKASSA_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN", "").strip()
DONATE_PRICE = int(os.getenv("DONATE_PRICE", "9900"))

DONOR_DAYS = 30

def is_donor(user_id: int) -> bool:
    if not DONORS_FILE.exists():
        return False
    try:
        d = json.loads(DONORS_FILE.read_text())
        ts = d.get(str(user_id))
        if not ts:
            return False
        # 30 дней
        return (time.time() - int(ts)) < DONOR_DAYS * 24 * 3600
    except:
        return False

def add_donor(user_id: int):
    d = {}
    if DONORS_FILE.exists():
        try:
            d = json.loads(DONORS_FILE.read_text())
        except:
            d = {}
    d[str(user_id)] = int(time.time())
    try:
        DONORS_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    except:
        pass

def donor_info():
    if not DONORS_FILE.exists():
        return "Донатов пока нет."
    try:
        d = json.loads(DONORS_FILE.read_text())
        lines = []
        now = time.time()
        for uid, ts in d.items():
            left = DONOR_DAYS * 24 * 3600 - (now - int(ts))
            if left > 0:
                days = int(left // 86400)
                lines.append(f"{uid}: {days}д осталось")
            else:
                lines.append(f"{uid}: истек")
        return "\n".join(lines) if lines else "Донатов пока нет."
    except Exception as e:
        return f"Ошибка базы: {e}"

def check_limit(user_id: int):
    if is_donor(user_id):
        return True, ""
    now = time.time()
    data = {}
    if RATE_FILE.exists():
        try:
            data = json.loads(RATE_FILE.read_text())
        except:
            data = {}
    key = str(user_id)
    rec = data.get(key, {"day": "", "count": 0, "last": 0})
    today = time.strftime("%Y-%m-%d")
    if rec["day"] != today:
        rec = {"day": today, "count": 0, "last": 0}
    if now - rec["last"] < COOLDOWN:
        return False, f"Подожди {int(COOLDOWN - (now - rec['last']))} сек."
    if rec["count"] >= DAILY_LIMIT:
        return False, f"Лимит {DAILY_LIMIT} в день исчерпан. Приходи завтра, помолись."
    rec["count"] += 1
    rec["last"] = now
    data[key] = rec
    try:
        RATE_FILE.write_text(json.dumps(data))
    except:
        pass
    return True, ""

def ask_deepseek(user_text: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 700 if PROVIDER == "deepseek" else 2000,
        "stream": False,
    }
    if PROVIDER == "openrouter":
        payload["reasoning"] = {"exclude": True}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    if PROVIDER == "openrouter":
        headers["HTTP-Referer"] = "http://localhost"
        headers["X-Title"] = "ispoved-bot"
    try:
        r = requests.post(BASE_URL, headers=headers, json=payload, timeout=(10, 30))
    except Exception as e:
        return "Прости, временный сбой, напиши еще раз."
    if r.status_code != 200:
        if r.status_code in (429, 502, 503):
            return "Сейчас много обращений, помолись минуту и напиши снова — я рядом."
        return "Прости, временный сбой, напиши еще раз."
    try:
        j = r.json()
        msg = j["choices"][0]["message"]["content"]
        return msg.strip() if msg else "Прости, связь прервалась — напиши еще раз."
    except Exception:
        return "Прости, не смог ответить, попробуй еще раз."

# --- Telegram ---
from telegram import Update, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🕯 Снять лимит 99₽", callback_data="donate")]]) if YOOKASSA_TOKEN else None
    await update.message.reply_text(
        "Мир тебе. Я — собеседник-наставник, не священник.\n"
        "Можешь написать что на душе — выслушаю без осуждения, подскажу мыслью и молитвой.\n"
        "Таинство исповеди и разрешение грехов — только у священника в храме.\n\n"
        f"Бесплатно {DAILY_LIMIT} в день, донат — безлимит.\n"
        "Напиши что тревожит. /help — подсказка. /donate — снять лимит.",
        reply_markup=kb
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Просто напиши что на сердце.\n"
        f"Лимит {DAILY_LIMIT} сообщений в день, пауза {COOLDOWN} сек.\n"
        "Донат 99₽ снимает лимит навсегда. Команда /donate\n"
        "Если тяжело — 8-800-2000-122 (круглосуточно).\n"
        "Это не замена исповеди."
    )

async def donate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not YOOKASSA_TOKEN:
        await update.message.reply_text("Донаты пока не настроены.")
        return
    prices = [LabeledPrice("Снятие лимита", DONATE_PRICE)]
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="Снять лимит на исповедь",
        description="Безлимит на беседы на 30 дней. Поддержи проект.",
        payload="donate-99",
        provider_token=YOOKASSA_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="donate",
    )

async def donate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await donate_cmd(update, context)

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    add_donor(uid)
    await update.message.reply_text("Спасибо! Лимит снят — теперь безлимит на 30 дней. Пиши когда тяжело на душе.")

# для админа ручная выдача: /grant 123456 и просмотр базы /donors
async def grant_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /grant <user_id>")
        return
    try:
        uid = int(context.args[0])
        add_donor(uid)
        await update.message.reply_text(f"Выдал безлимит на {DONOR_DAYS} дней для {uid}")
    except:
        await update.message.reply_text("Ошибка id")

async def donors_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"База доноров ({DONOR_DAYS}д):\n" + donor_info() + f"\n\nФайл: donors.json")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        return
    ok, msg = check_limit(uid)
    if not ok:
        kb = None
        if "исчерпан" in msg and YOOKASSA_TOKEN:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🕯 Снять лимит 99₽", callback_data="donate")]])
        await update.message.reply_text(f"Батюшка: {msg}", reply_markup=kb)
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    # синхронный запрос в треде чтобы не блокировать
    import asyncio
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, ask_deepseek, text)
    # разбить если >4000 символов
    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i:i+4000])

def main():
    print(f"Запуск ТГ-бота. Провайдер: {PROVIDER}, модель: {MODEL}, лимит {DAILY_LIMIT}/день, донат {'вкл' if YOOKASSA_TOKEN else 'выкл'}")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("donate", donate_cmd))
    app.add_handler(CommandHandler("grant", grant_cmd))
    app.add_handler(CommandHandler("donors", donors_cmd))
    from telegram.ext import CallbackQueryHandler, PreCheckoutQueryHandler
    app.add_handler(CallbackQueryHandler(donate_callback, pattern="^donate$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
