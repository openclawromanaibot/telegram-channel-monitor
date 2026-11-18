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

1. Скачай скрипт:

```bash
mkdir -p ~/.hermes/scripts
curl -sL https://raw.githubusercontent.com/openclawromanaibot/telegram-channel-monitor/main/monitor.py \
  -o ~/.hermes/scripts/tg-monitor.py
chmod +x ~/.hermes/scripts/tg-monitor.py
```

2. Создай обёртку с нужными каналами и словами:

```bash
cat > ~/.hermes/scripts/tg-monitor-wrapper.sh << 'EOF'
#!/bin/bash
export CHANNELS="nyachang_uslugi"
export KEYWORDS="ищу|нужен|требуется|работа|услуг|помогите"
export STATE_FILE="$HOME/.hermes/scripts/tg-monitor-state.json"
exec python3 "$HOME/.hermes/scripts/tg-monitor.py"
EOF
chmod +x ~/.hermes/scripts/tg-monitor-wrapper.sh
```

3. Создай cron-задачу:

```bash
hermes cron create "every 10m" \
  --no-agent \
  --script tg-monitor-wrapper.sh \
  --deliver telegram:765151409 \
  --name "tg-keyword-monitor"
```

4. Проверь один раз:

```bash
hermes cron run <job_id>
```

## Параметры

| Аргумент / ENV       | Описание                                              |
|----------------------|-------------------------------------------------------|
| `--channels` / `CHANNELS` | Каналы через запятую (без @)                      |
| `--keywords` / `KEYWORDS` | Ключевые слова через `,` или `\|`                 |
| `--state` / `STATE_FILE`  | Файл состояния (запоминает уже виденные post id)  |
| `--max-posts`        | Сколько последних постов смотреть (по умолчанию 20)   |
| `--dry-run`          | Не обновлять state                                    |

## Пример уведомления (новый формат)

```
🔔 *Новое совпадение*
📢 `nyachang_uslugi`  ·  🕒 18.11 11:42
🔑 ищу, нужен

*Ищу* человека на подработку, *нужен* опыт...

→ https://t.me/nyachang_uslugi/12345
```

Ключевые слова подсвечиваются жирным (`*слово*`).

## Готовый промпт для Hermes

Скопируй и отправь своему агенту:

```
Нужно настроить мониторинг публичных Telegram-каналов по ключевым словам.

Репозиторий со скриптом:
https://github.com/openclawromanaibot/telegram-channel-monitor

Сделай следующее:

1. Скачай monitor.py в ~/.hermes/scripts/tg-monitor.py
2. Создай обёртку ~/.hermes/scripts/tg-monitor-wrapper.sh с такими настройками:

CHANNELS="nyachang_uslugi"
KEYWORDS="ищу|нужен|требуется|работа|услуг|помогите"
STATE_FILE="$HOME/.hermes/scripts/tg-monitor-state.json"

3. Сделай оба файла исполняемыми.
4. Создай script-only cron job:
   - расписание: every 10m
   - script: tg-monitor-wrapper.sh
   - no_agent: true
   - deliver: telegram:765151409
   - name: tg-keyword-monitor

5. Запусти задачу один раз для проверки (hermes cron run ...).

Если что-то непонятно по репозиторию — сначала прочитай README:
https://github.com/openclawromanaibot/telegram-channel-monitor/blob/main/README.md
```

(Замени `CHANNELS`, `KEYWORDS` и `telegram:ID` на свои.)

## Рекомендации по расписанию

- 5–15 минут — нормально для большинства каналов.
- Не ставь чаще 1–2 минут: Telegram может начать резать.
- State-файл обязателен, иначе при каждом запуске будут дубли.

## Альтернативы

Если нужно реальное время / полная история / приватные каналы — используй Telethon (user session) или готовые сервисы (Apify и т.п.).

## License

MIT
