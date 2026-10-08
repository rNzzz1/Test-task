# Сервис полнотекстового поиска по текстам документов

Сервис для поиска и управления документами с хранением данных в реляционной базе данных (PostgreSQL / SQLite) и полнотекстовым индексом в Elasticsearch. Разработан на асинхронном стеке **FastAPI** в рамках тестового задания.

---

## 🚀 Возможности и особенности

- **Полнотекстовый поиск**: Поиск по полю `text` в индексе Elasticsearch (с русским стеммингом `russian analyzer`), получение соответствующих документов из БД, упорядоченных по дате создания (`created_date`), с лимитом в первые 20 документов.
- **Синхронизированное удаление**: Удаление документа по `id` одновременно из базы данных и поискового индекса Elasticsearch.
- **Полная асинхронность**: Неблокирующий ввод-вывод на всех уровнях:
  - `FastAPI` (async endpoint handlers)
  - `SQLAlchemy 2.0` (async engine с `asyncpg` для PostgreSQL и `aiosqlite` для тестов/SQLite)
  - `AsyncElasticsearch` (официальный асинхронный клиент)
- **Автоматическая загрузка данных**: При первом старте сервиса автоматически проверяется наличие данных и выполняется первичная загрузка 1500 документов из `posts.csv` в базу данных и Elasticsearch.
- **OpenAPI / Swagger**: Актуальная документация `docs.json` в корне репозитория и интерактивный Swagger UI по адресу `http://localhost:8000/docs`.
- **Docker Compose**: Полная оркестрация сервисов (FastAPI + PostgreSQL + Elasticsearch) одной командой.
- **Функциональные тесты**: Набор тестов на базе `pytest` и `pytest-asyncio` для проверки поиска, удаления, валидации и граничных случаев.

---

## 🗄 Структура данных

### База данных (таблица `posts`)
| Поле | Тип | Описание |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Уникальный идентификатор документа |
| `rubrics` | `JSON` | Массив рубрик (например, `['VK-1603736028819866', ...]`) |
| `text` | `TEXT` | Текст документа |
| `created_date` | `DATETIME` | Дата и время создания документа (с индексом) |

### Поисковый индекс Elasticsearch (`posts`)
| Поле | Тип | Анализатор | Описание |
|---|---|---|---|
| `id` | `integer` | — | Идентификатор из базы данных |
| `text` | `text` | `russian` | Текст документа для полнотекстового поиска |

---

## 🛠 Быстрый запуск в Docker (рекомендуемый способ)

Для запуска сервиса со всеми зависимостями (FastAPI, PostgreSQL 16, Elasticsearch 8) потребуется только установленный **Docker** и **Docker Compose**:

```bash
# Клонируйте репозиторий и перейдите в папку проекта:
cd Test-task

# Запустите проект:
docker compose up --build
```

Сервисы поднимутся в следующем порядке:
1. `docsearch_db` (PostgreSQL 16) — инициализирует базу данных;
2. `docsearch_elasticsearch` (Elasticsearch 8.13.4) — запускает кластер в режиме `single-node`;
3. `docsearch_app` (FastAPI) — дожидается готовности БД и ES по healthcheck, создает таблицы, автоматически загружает `posts.csv` и запускает web-сервер на порту **8000**.

Проверка доступности:
```bash
curl http://localhost:8000/health
```

---

## 💻 Локальный запуск (без Docker)

### 1. Подготовка виртуального окружения
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Настройка переменных окружения
Скопируйте пример конфигурации:
```bash
cp .env.example .env
```

По умолчанию в `.env` указано:
```env
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=False

# Для PostgreSQL:
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/docsearch

# Или для локального SQLite без отдельного сервера БД:
# DATABASE_URL=sqlite+aiosqlite:///./docsearch.db

ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=posts
AUTO_SEED_ON_STARTUP=True
CSV_DATA_PATH=posts.csv
```

### 3. Ручной импорт данных (опционально)
Если отключен `AUTO_SEED_ON_STARTUP`, данные из CSV можно загрузить отдельным CLI-скриптом:
```bash
python scripts/load_csv.py --csv posts.csv
```

### 4. Запуск сервера
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📖 Документация API

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON в репозитории**: файл [`docs.json`](./docs.json)

### Основные методы

#### 1. Поиск документов по тексту
`GET /search` (или `GET /api/v1/search`)

Параметры запроса:
- `query` (строка, обязательно) — текст для поиска;
- `limit` (целое число, по умолчанию 20) — количество документов;
- `order` (`desc` или `asc`, по умолчанию `desc`) — сортировка по дате создания.

Пример запроса:
```bash
curl "http://localhost:8000/search?query=%D0%BF%D0%B0%D1%81%D1%81%D0%B8%D0%B2%D0%BA%D0%B8"
```

Пример ответа (200 OK):
```json
[
  {
    "id": 1,
    "rubrics": [
      "VK-1603736028819866",
      "VK-11879320040",
      "VK-63192684938"
    ],
    "text": "Слив информации на пассивки:\n\n• Булл (Блокировка боли)\n• Джесси (Массовый шок)...",
    "created_date": "2019-07-25T12:42:13"
  }
]
```

#### 2. Удаление документа
`DELETE /posts/{id}` (или `DELETE /api/v1/posts/{id}`)

Удаляет документ из базы данных и из индекса Elasticsearch.

Пример запроса:
```bash
curl -X DELETE "http://localhost:8000/posts/1"
```

Ответы:
- `204 No Content` — документ успешно удален.
- `404 Not Found` — документ с указанным `id` не найден.

#### 3. Получение документа по ID
`GET /posts/{id}`

Пример запроса:
```bash
curl "http://localhost:8000/posts/1"
```

#### 4. Добавление документа
`POST /posts`

Пример запроса:
```bash
curl -X POST "http://localhost:8000/posts" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "Новый интересный пост про разработку",
       "rubrics": ["DEV", "PYTHON"],
       "created_date": "2024-01-01T12:00:00"
     }'
```

#### 5. Проверка состояния сервиса
`GET /health`

Пример ответа:
```json
{
  "status": "ok",
  "database": true,
  "elasticsearch": true
}
```

---

## 🧪 Запуск тестов

Функциональные тесты проверяют корректность поиска, сортировку по дате создания, ограничение в 20 записей, синхронное удаление из БД и индекса, валидацию и обработку ошибок.

Для запуска тестов:
```bash
pytest -v
```

Тесты выполняются изолированно с использованием in-memory базы данных SQLite и встроенного мока поиска, что обеспечивает мгновенное выполнение (менее 0.2 с) без необходимости поднимать внешние сервисы.

---

## 📄 Обновление спецификации `docs.json`

Для актуализации файла спецификации OpenAPI:
```bash
python scripts/dump_openapi.py
```
Файл `docs.json` будет сгенерирован автоматически из схемы FastAPI.
