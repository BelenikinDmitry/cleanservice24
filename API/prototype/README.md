# CleanService24 Ads Manager (прототип)

Внутренний инструмент рекламодателя: объявления из `yadirect/after_renovation/ads.md`, кампании и отчёты Яндекс Директа.
Только стандартная библиотека Python 3.10+, зависимостей нет.

## Запуск (демо-режим, без токена)

```bash
cd API/prototype
python3 app.py            # http://localhost:8000
```

Демо-режим использует тестовые данные и не обращается к API Директа.

## Режимы

| `DIRECT_MODE` | Что делает |
|---|---|
| `demo` (по умолчанию) | тестовые данные, без сети |
| `sandbox` | реальные запросы в `api-sandbox.direct.yandex.com` |
| `prod` | боевой API |

Для `sandbox`/`prod` задайте переменные окружения (секреты в репозиторий не коммитить):

```bash
export DIRECT_MODE=sandbox
export YANDEX_CLIENT_ID=...
export YANDEX_CLIENT_SECRET=...
export YANDEX_REDIRECT_URI=http://localhost:8000/callback   # должен совпадать с настройками приложения в Яндекс ID
python3 app.py
```

## Скриншоты

Приложение должно быть запущено. Нужен `playwright` с установленным chromium:

```bash
python3 make_screenshots.py http://localhost:8000 ../screenshots
```

Скриншоты скрипта — это страница без окна браузера. Если нужны кадры с адресной строкой, снимите их вручную в браузере, открыв `http://localhost:8000`.

## Файлы

- `app.py` — веб-сервер, страницы, OAuth
- `direct_client.py` — клиент API (Campaigns.get, Reports, Ads.add) и демо-бэкенд
- `ads_parser.py` — разбор `ads.md` и проверка лимитов
- `make_screenshots.py` — съёмка скриншотов
