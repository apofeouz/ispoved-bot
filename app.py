import os
import requests
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "inclusionai/ling-3.0-flash-sante:free")

# приоритет DeepSeek если ключ заполнен
if DEEPSEEK_KEY:
    KEY = DEEPSEEK_KEY
    MODEL = DEEPSEEK_MODEL
    BASE_URL = f"{DEEPSEEK_BASE}/v1/chat/completions"
    PROVIDER = "deepseek"
else:
    KEY = OPENROUTER_KEY
    MODEL = OPENROUTER_MODEL
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    PROVIDER = "openrouter"

if not KEY:
    print("ОШИБКА: .env пустой. Вставь DEEPSEEK_API_KEY или OPENROUTER_API_KEY")
    exit(1)

# лимиты от спама
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT_PER_USER", "5"))
COOLDOWN = int(os.getenv("COOLDOWN_SEC", "10"))
import json as _json, time as _time, pathlib as _path
RATE_FILE = _path.Path("rate_limit.json")

def check_rate_limit(user_id="local"):
    now = _time.time()
    data = {}
    if RATE_FILE.exists():
        try:
            data = _json.loads(RATE_FILE.read_text())
        except:
            data = {}
    rec = data.get(user_id, {"day": "", "count": 0, "last": 0})
    today = _time.strftime("%Y-%m-%d")
    if rec["day"] != today:
        rec = {"day": today, "count": 0, "last": 0}
    if now - rec["last"] < COOLDOWN:
        return False, f"Подожди {int(COOLDOWN - (now - rec['last']))} сек."
    if rec["count"] >= DAILY_LIMIT:
        return False, f"Лимит {DAILY_LIMIT} в день исчерпан, приходи завтра."
    rec["count"] += 1
    rec["last"] = now
    data[user_id] = rec
    try:
        RATE_FILE.write_text(_json.dumps(data))
    except:
        pass
    return True, ""

SYSTEM_PROMPT = """Ты - кроткий православный наставник.
Отвечай КРАТКО: 4-6 предложений, без воды и без поучений на полстраницы.

Структура ответа:
1. Короткое утешение без осуждения (1-2 предложения).
2. Если уместно теме - ОДНА точная цитата из Библии/Псалтири по проблеме (с указанием источника, напр. Мф. 11:28, 1 Ин. 1:9, Пс. 50:12). Если нет точной подходящей - пропусти, не выдумывай.
3. Краткий совет: молитва (используй ТОЛЬКО "Отче наш" или "Господи Иисусе Христе, Сыне Божий, помилуй мя грешного"), разговор с близким, совет сходить в храм на беседу.
4. Напомни про таинство исповеди ТОЛЬКО если человек прямо просит отпустить грехи/исповедовать - тогда скажи: "Разрешение грехов дает только священник в храме". Не повторяй это в каждом ответе.
5. Задай ОДИН короткий вопрос для размышления.

Правила: не выдумывай имена/молитвы (никаких "сестра Рафаила"), не ставь епитимью, не осуждай, не ставь диагнозов. Если суицид - дай телефон 8-800-2000-122. Отвечай тепло и по-человечески, не как робот с дисклеймером.
"""

def chat_stream(user_text: str):
    import json
    import sys
    import threading
    import time
    import itertools

    # анимация "думает..." пока ждем первый токен
    stop_anim = threading.Event()
    anim_done = threading.Event()

    def thinking_anim():
        for dots in itertools.cycle(["   ", ".  ", ".. ", "..."]):
            if stop_anim.is_set():
                break
            print(f"\rБатюшка думает{dots}", end="", flush=True)
            time.sleep(0.35)
        anim_done.set()

    t = threading.Thread(target=thinking_anim, daemon=True)
    t.start()

    # проверка лимитов
    ok, msg = check_rate_limit("local")
    if not ok:
        print(f"\nБатюшка: {msg}\n")
        return

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 700 if PROVIDER == "deepseek" else 2000,
        "stream": True,
    }
    if PROVIDER == "openrouter":
        payload["reasoning"] = {"exclude": True}
    headers = {
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }
    if PROVIDER == "openrouter":
        headers["HTTP-Referer"] = "http://localhost"
        headers["X-Title"] = "ispoved-bot"

    resp = None
    for attempt in range(2):
        try:
            resp = requests.post(
                BASE_URL,
                headers=headers,
                json=payload,
                stream=True,
                timeout=(10, 20),
            )
        except requests.exceptions.RequestException as e:
            if attempt == 0:
                time.sleep(1.5)
                continue
            stop_anim.set()
            t.join(timeout=1)
            print("\r" + " " * 30 + f"\rБатюшка: Прости, временный сбой, напиши еще раз.\n")
            return

        if resp.status_code == 429 and attempt == 0:
            # фри-лимит - ждем и ретрай
            retry_after = 1.5
            try:
                retry_after = float(resp.headers.get("Retry-After", 1.5))
            except:
                pass
            time.sleep(retry_after)
            continue
        break

    if resp is None or resp.status_code != 200:
        stop_anim.set()
        t.join(timeout=1)
        print("\r" + " " * 30 + "\r", end="")
        try:
            err = resp.json() if resp is not None else {}
            msg = err.get('error', {}).get('message', str(resp.text) if resp is not None else "no response")
            if resp is not None and resp.status_code in (429, 502, 503):
                print(f"Батюшка: Сейчас много людей обращается, помолись минуту и напиши снова - я выслушаю.\n")
            else:
                print(f"Батюшка: Прости, временный сбой, напиши еще раз.\n")
            with open("error.log", "a") as f:
                f.write(f"http {resp.status_code if resp else 'none'} {msg[:200]} for: {user_text[:80]}\n")
        except Exception:
            print(f"Батюшка: Прости, временный сбой, напиши еще раз.\n")
        return

    first_token = True
    buffer = ""
    start = time.time()
    try:
        for line in resp.iter_lines(chunk_size=1):
            # если 20 сек нет первого токена - считаем зависом
            if first_token and time.time() - start > 20:
                stop_anim.set()
                t.join(timeout=1)
                print("\r" + " " * 30 + "\rБатюшка: Прости, чадо, сейчас долго не отвечает - помолись кратко и напиши еще раз, я здесь.\n")
                resp.close()
                return
            if not line:
                # keep-alive от OpenRouter ": OPENROUTER PROCESSING" приходит как b': ...' - игнорируем но не считаем зависом
                if time.time() - start > 25 and first_token:
                    continue
                continue
            if line.startswith(b"data: "):
                data = line[6:]
                if data == b"[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        if first_token:
                            stop_anim.set()
                            t.join(timeout=1)
                            print("\r" + " " * 30 + "\rБатюшка: ", end="", flush=True)
                            first_token = False
                        buffer += text
                        if " " in buffer or "\n" in buffer or len(buffer) > 20:
                            print(buffer, end="", flush=True)
                            buffer = ""
                except Exception:
                    continue
            elif line.startswith(b":"):
                # OPENROUTER PROCESSING - просто ждем
                continue
    except requests.exceptions.ReadTimeout:
        stop_anim.set()
        t.join(timeout=1)
        print("\r" + " " * 30 + f"\rБатюшка: Прости, долго нет ответа - попробуй еще раз, я рядом.\n")
        return
    finally:
        if first_token:
            stop_anim.set()
            try:
                t.join(timeout=1)
            except:
                pass
            print("\r" + " " * 30 + "\r", end="")

    if buffer:
        print(buffer, end="", flush=True)
    if not first_token:
        print("\n")
    else:
        # тихий фолбэк без пугающего текста - пастырский ответ + авто-ретрай не нужен
        print("\r" + " " * 30 + "\rБатюшка: Прости, чадо, связь прервалась - напиши еще раз, я рядом и выслушаю. Господь видит твое сердце.\n")
        # логируем для отладки в файл
        try:
            with open("error.log", "a") as f:
                f.write(f"no_content for: {user_text[:80]}\n")
        except:
            pass


if __name__ == "__main__":
    print(f"Исповедь-бот запущен (стрим). Провайдер: {PROVIDER}, модель: {MODEL}, лимит {DAILY_LIMIT}/день, пауза {COOLDOWN}с")
    print("Напиши сообщение (пустая строка - выход):\n")
    while True:
        try:
            text = input("Ты: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        chat_stream(text)
