# Lotoshino

Чистый Django-проект с асинхронной главной страницей и запуском через ASGI/Uvicorn.
Python 3.14, язык `ru`, часовой пояс `Europe/Moscow`.
Локальная база — SQLite, серверная — PostgreSQL.

## Локальная разработка

Активируйте окружение `lotoshino`, созданное через `py`:

```bash
source ~/.python3/venvs/lotoshino/bin/activate
make install
make migrate
make run
```

Сайт: <http://127.0.0.1:8000/>, админка: <http://127.0.0.1:8000/admin/>.
Создание администратора:

```bash
poetry run python manage.py createsuperuser
```

`make run` запускает Uvicorn с перезапуском при изменении Python-файлов.
`make run-async` — его псевдоним. Статика админки обслуживается в режиме разработки.
Другой адрес или порт: `make run HOST=127.0.0.1 PORT=8001`.
Автоматическое обновление вкладки браузера не включено.

Зависимости описаны в `pyproject.toml`, точные версии — в `poetry.lock`.
Для обновления в пределах заданных диапазонов: `poetry update`.

## Проверки

```bash
make check       # Ruff, настройки Django и отсутствие пропущенных миграций
make test        # Тесты асинхронной главной страницы
make format     # Форматирование и автоматические исправления Ruff
```

## Настройки сервера

Перед запуском задайте переменные окружения:

- `DJANGO_SETTINGS_MODULE=lotoshino.settings.production`;
- `DJANGO_SECRET_KEY` — отдельный секретный ключ;
- `DJANGO_ALLOWED_HOSTS` — домены через запятую;
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`.

Файл `.env` автоматически не загружается. Настройки сервера отключают DEBUG,
используют PostgreSQL и требуют HTTPS. Постоянные подключения к БД отключены
(`CONN_MAX_AGE=0`) для ASGI.

```bash
poetry run python manage.py migrate
poetry run python manage.py collectstatic --noinput
poetry run python -m uvicorn lotoshino.asgi:application --host 127.0.0.1 --port 8000
```

Обслуживание `staticfiles/`, HTTPS и настройки доверенного reverse proxy
настраиваются при развёртывании под конкретный сервер.
