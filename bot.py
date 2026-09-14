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

SYSTEM_PROMPT = """Ты - кроткий православный наставник, живой собеседник, не робот.
Отвечай КРАТКО: 3-5 предложений.

Правила живости:
- Если человек прощается ("спокойной ночи", "пока", "спасибо, пошел спать") - просто пожелай доброй ночи/мира без вопросов и без поучений. Не задавай крючков.
- Вопрос задавай только если уместно и не каждый раз (через раз). Не допрашивай.
- Помни контекст: если только что читал молитву и просят объяснить - объясняй ту же молитву, не спрашивай "какую?".
- Говори тепло, по-человечески, без шаблона.

Структура когда уместно:
1. Короткое утешение без осуждения.
2. Если уместно - ОДНА точная цитата из Библии с источником (Мф. 11:28, 1 Ин. 1:9, Пс. 50). Если нет - пропусти, не выдумывай.
3. Краткий совет: молитва ТОЛЬКО "Отче наш" или "Господи Иисусе Христе, Сыне Божий, помилуй мя грешного", или совет поговорить с близким/сходить в храм.
Напомни про таинство ТОЛЬКО если просят отпустить грехи. Не выдумывай молитвы. Если суицид - дай 8-800-2000-122.
"""

RATE_FILE = pathlib.Path("rate_limit_tg.json")
DONORS_FILE = pathlib.Path("donors.json")
YOOKASSA_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN", "").strip()
DONATE_PRICE = int(os.getenv("DONATE_PRICE", "9900"))

DONOR_DAYS = 30
ANALYTICS_FILE = pathlib.Path("analytics.jsonl")

def log_event(user_id: int, event: str, extra: str = ""):
    try:
        rec = {"ts": int(time.time()), "uid": int(user_id), "event": event}
        if extra:
            rec["extra"] = extra[:80]
        # utm из start_param
        with open(ANALYTICS_FILE, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except:
        pass

def get_stats():
    if not ANALYTICS_FILE.exists():
        return "Пока нет данных."
    try:
        counts = {}
        pay = 0
        uniq = set()
        for line in ANALYTICS_FILE.read_text().splitlines():
            try:
                r = json.loads(line)
                e = r.get("event")
                counts[e] = counts.get(e, 0) + 1
                if e == "pay_success":
                    pay += 1
                uniq.add(r.get("uid"))
            except:
                continue
        start = counts.get("start", 0)
        msg = counts.get("message", 0)
        limit = counts.get("limit_hit", 0)
        click = counts.get("donate_click", 0)
        conv = (pay / start * 100) if start else 0
        return (
            f"Старт: {start}\n"
            f"Написали: {msg} ({(msg/start*100 if start else 0):.0f}%)\n"
            f"Уперлись в лимит: {limit} ({(limit/msg*100 if msg else 0):.0f}% от писавших)\n"
            f"Кликнули донат: {click} ({(click/limit*100 if limit else 0):.0f}% от упершихся)\n"
            f"Оплатили: {pay} ({(pay/click*100 if click else 0):.0f}% от кликов)\n"
            f"Конверсия старт->оплата: {conv:.1f}%\n"
            f"Уникальных: {len(uniq)}\n"
            f"Выручка: {pay * DONATE_PRICE/100:.0f}₽"
        )
    except Exception as e:
        return f"Ошибка: {e}"

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

HISTORY_FILE = pathlib.Path("history.json")
HISTORY_LIMIT = 8  # последних сообщений (4 обмена)

def load_history(user_id: int):
    if not HISTORY_FILE.exists():
        return []
    try:
        d = json.loads(HISTORY_FILE.read_text())
        return d.get(str(user_id), [])[-HISTORY_LIMIT:]
    except:
        return []

def save_history(user_id: int, role: str, content: str):
    try:
        d = {}
        if HISTORY_FILE.exists():
            d = json.loads(HISTORY_FILE.read_text())
        lst = d.get(str(user_id), [])
        lst.append({"role": role, "content": content})
        # храним последние 20
        d[str(user_id)] = lst[-20:]
        HISTORY_FILE.write_text(json.dumps(d, ensure_ascii=False))
    except:
        pass

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

def ask_deepseek(user_text: str, user_id: int = 0) -> str:
    hist = load_history(user_id) if user_id else []
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + hist + [{"role": "user", "content": user_text}]
    payload = {
        "model": MODEL,
        "messages": msgs,
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
    # utm: /start tiktok
    extra = " ".join(context.args) if context.args else ""
    log_event(update.effective_user.id, "start", extra)
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
    log_event(update.effective_user.id, "donate_click")
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
    log_event(uid, "pay_success", f"{DONATE_PRICE}")
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

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Конверсия:\n" + get_stats() + f"\n\nФайл: analytics.jsonl")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        return
    log_event(uid, "message")
    ok, msg = check_limit(uid)
    if not ok:
        if "исчерпан" in msg:
            log_event(uid, "limit_hit")
        kb = None
        if "исчерпан" in msg and YOOKASSA_TOKEN:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🕯 Снять лимит 99₽", callback_data="donate")]])
        await update.message.reply_text(f"Батюшка: {msg}", reply_markup=kb)
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    # синхронный запрос в треде чтобы не блокировать
    import asyncio
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, ask_deepseek, text, uid)
    save_history(uid, "user", text)
    save_history(uid, "assistant", reply)
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
    app.add_handler(CommandHandler("stats", stats_cmd))
    from telegram.ext import CallbackQueryHandler, PreCheckoutQueryHandler
    app.add_handler(CallbackQueryHandler(donate_callback, pattern="^donate$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
