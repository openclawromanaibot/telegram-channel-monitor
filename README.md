# telegram-channel-monitor

Лёгкий скрипт для мониторинга **публичных** Telegram-каналов по ключевым словам через превью `t.me/s/<channel>`.

Предназначен для **Hermes Agent** (script-only cron jobs):
- скрипт печатает совпадения в stdout → Hermes доставляет в Telegram;
- пустой stdout → тишина (никаких уведомлений).

Не требует Telegram API / бота / логина. Работает только с публичными каналами, у которых открыт web-preview.

## Ограничения

- `t.me/s/` отдаёт только последние ~20 сообщений.
- Для полной истории нужен Telethon/userbot или бот с доступом.
- Если постов больше, чем вмещается в окно между запусками — можно пропустить.

Для 5–15 минутного интервала обычно хватает.

## Быстрый старт (Hermes)

1. Склонируй или скачай `monitor.py` в `~/.hermes/scripts/`:

```bash
mkdir -p ~/.hermes/scripts
curl -sL https://raw.githubusercontent.com/openclawromanaibot/telegram-channel-monitor/main/monitor.py \
  -o ~/.hermes/scripts/tg-monitor.py
chmod +x ~/.hermes/scripts/tg-monitor.py
```

2. Создай cron-задачу (пример):

```bash
hermes cron create "every 10m" \
  --no-agent \
  --script tg-monitor.py \
  --deliver telegram:765151409 \
  --name "tg-keyword-monitor"
```

Или через переменные окружения в обёртке:

```bash
#!/bin/bash
# ~/.hermes/scripts/tg-monitor-wrapper.sh
export CHANNELS="nyachang_uslugi,another_channel"
export KEYWORDS="ищу|нужен|требуется|работа|услуг"
export STATE_FILE="$HOME/.hermes/scripts/tg-monitor-state.json"
exec python3 "$HOME/.hermes/scripts/tg-monitor.py"
```

3. Проверь один раз:

```bash
hermes cron run <job_id>
```

## Параметры

| Аргумент / ENV | Описание |
|----------------|----------|
| `--channels` / `CHANNELS` | Каналы через запятую (без @) |
| `--keywords` / `KEYWORDS` | Ключевые слова через `,` или `\|` |
| `--state` / `STATE_FILE` | Файл состояния (запоминает уже виденные post id) |
| `--max-posts` | Сколько последних постов смотреть (по умолчанию 20) |
| `--dry-run` | Не обновлять state |

## Пример вывода (то, что уйдёт в Telegram)

```
🔔 nyachang_uslugi · 2026-11-18T04:12:00+00:00
Keywords: ищу
Ищу человека на ...
https://t.me/nyachang_uslugi/12345
---
```

## Рекомендации по расписанию

- 5–15 минут — нормально для большинства каналов.
- Не ставь чаще 1–2 минут: Telegram может начать резать.
- State-файл обязателен, иначе при каждом запуске будут дубли старых постов из окна.

## Альтернативы

Если нужно реальное время / полная история / приватные каналы — используй Telethon (user session) или готовые сервисы (Apify и т.п.).

## License

MIT
