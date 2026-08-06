# pg-polygon-orchestr

Библиотека для автоматического развёртывания и управления Docker-контейнерами через Python.

## Требования

- Python 3.14+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — менеджер зависимостей и виртуальных окружений
- Docker Desktop или Docker Engine — должен быть **запущен** перед выполнением тестов

## Установка

Клонировать репозиторий и установить зависимости:

```bash
git clone <repo_url>
cd pg-polygon-orchestr/project
uv sync
```

## Запуск тестов

> **Важно:** интеграционные тесты запускают реальные Docker-контейнеры и требуют работающего Docker daemon.

Запуск всех интеграционных тестов:

```bash
uv run pytest -m integration -vv
```

Запуск конкретного теста:

```bash
uv run pytest -m integration -k <имя_теста>
```

Например:

```bash
uv run pytest -m integration -k test_1__two_nodes_deployed_started_named_and_destroyed
```

## Конфигурация

| Файл | Назначение |
|---|---|
| `pytest.ini` | Конфигурация pytest (маркеры, пути к тестам) |
| `pyproject.toml` | Метаинформация проекта и зависимости |

## Возможные проблемы

**После прерывания тестов остались мусорные контейнеры:**

Тесты могут оставить контейнеры, образы и сети если были прерваны принудительно (Ctrl+C)