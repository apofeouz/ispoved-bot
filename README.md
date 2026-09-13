# Душа и свет — тихий собеседник

Телеграм-бот `t.me/dusha_i_svet_bot` — анонимная беседа без осуждения. Не священник, не замена таинству исповеди.

- Коротко: 4-6 предложений + одна цитата из Писания
- Молитвы только `Отче наш` / `Господи Иисусе Христе, помилуй мя грешного`
- Лимит 5/день, донат 99₽ → безлимит на 30 дней (ЮKassa)
- Провайдер DeepSeek Flash (`deepseek-chat`) — быстро и дешево

## Запуск локально

```bash
cp .env.example .env
# заполни TELEGRAM_TOKEN, DEEPSEEK_API_KEY
pip install -r requirements.txt
python3 bot.py  # телеграм
python3 app.py  # консоль
```

## .env

```
TELEGRAM_TOKEN=...
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
YOOKASSA_PROVIDER_TOKEN=... # из @BotFather Payments
DONATE_PRICE=9900
```

`.env` не коммитится.

## Деплой

```bash
scp -r ispoved-bot user@server:/opt/ispoved-bot
ssh user@server "cd /opt/ispoved-bot && pip install -r requirements.txt && systemctl restart ispoved"
```

PR welcome.
