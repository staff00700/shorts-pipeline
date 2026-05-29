# YouTube Shorts Pipeline v1.0

Автоматический конвейер для создания и загрузки Shorts на YouTube.

## Структура проекта

```
Project 9/
├── shorts_v1.py          # Основной код (все модули в одном файле)
├── requirements.txt      # Зависимости
├── credentials.json     # OAuth credentials от Google
├── api youtube.txt       # YouTube API Key
├── data/
│   ├── raw/              # Скачанные видео
│   ├── processed/        # Готовые Shorts
│   └── logs/             # Логи работы
├── venv/                 # Виртуальное окружение
└── README.md             # Этот файл
```

## Установка

```bash
cd /home/user/Project 9
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Запуск

```bash
cd /home/user/Project 9
source venv/bin/activate
python3 shorts_v1.py
```

## Конфигурация

Основные параметры в файле `shorts_v1.py` (в секции CONFIG):

- `search_queries` - запросы для поиска видео
- `target_shorts_per_day` - сколько Shorts загружать в день (5)
- `max_videos_per_day` - сколько видео скачивать (2)
- `max_shorts_per_video` - сколько Shorts нарезать с одного видео (4)
- `run_interval_hours` - интервал запуска (24 часа)

## Как это работает

1. **Поиск** - ищет трендовые видео по запросам (история, факты)
2. **Скачивание** - скачивает лучшие видео через yt-dlp
3. **Анализ** - находит лучшие моменты для нарезки
4. **Обработка** - нарезает на Shorts 30-60 сек, добавляет субтитры
5. **Загрузка** - публикует на YouTube через API

## Требования

- Python 3.8+
- FFmpeg
- yt-dlp
- YouTube API Key + OAuth credentials
- Доступ к интернету

## Текущая ниша

История и Интересные факты (History/Did You Know)
- English контент
- Высокий CPM ($2-6)
- Хороший вирусный потенциал

## Название Shorts при загрузке

`{тема} часть {номер} | Исторические факты`

Пример:
- "100 History Facts часть 1 | Исторические факты"
- "100 History Facts часть 2 | Исторические факты"