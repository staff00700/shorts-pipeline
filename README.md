# YouTube Shorts Pipeline v1.0

Автоматический конвейер для создания и загрузки Shorts на YouTube.

## Возможности

- Поиск и скачивание трендовых видео через YouTube API + yt-dlp
- AI-анализ субтитров (OpenRouter) для выбора лучших моментов
- Нарезка Shorts 30-60 сек через FFmpeg
- Автоматические субтитры через faster-whisper
- Загрузка на YouTube через API
- Веб-админка для просмотра и управления шортсами
- Очистка обработанных файлов (не забивает диск)
- Защита от повторов — видео не скачиваются дважды

## Установка

```bash
git clone <repo-url> shorts-pipeline
cd shorts-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Зависимости системы:**
- FFmpeg (`sudo apt install ffmpeg`)
- yt-dlp (`sudo apt install yt-dlp` или `pip install yt-dlp`)

## Настройка

1. Получить API Key для YouTube Data API v3 в Google Cloud Console
2. Получить OAuth credentials (скачать `credentials.json`) для YouTube Upload API
3. (Опционально) Настроить OpenRouter в файле `OpenRouter.txt`:

```
@preset/for-youtube-shorts
sk-or-ваш_ключ
```

## Конфигурация

В файле `shorts_v1.py` в секции `CONFIG`:

| Параметр | Значение | Описание |
|---|---|---|
| `search_queries` | список | Запросы для поиска видео |
| `max_videos_per_day` | 1 | Сколько видео скачивать за запуск |
| `max_shorts_per_video` | 5 | Сколько Shorts нарезать с одного видео |
| `target_shorts_per_day` | 5 | Сколько Shorts загружать в день |
| `short_duration_min/max` | 30-60 | Длительность одного Short |
| `run_interval_hours` | 24 | Интервал между запусками |

## Запуск

**Одноразовый запуск:**
```bash
cd shorts-pipeline
source venv/bin/activate
python3 shorts_v1.py
```

**Веб-админка:**
```bash
cd shorts-pipeline
./start_web_admin.sh
# Открыть http://localhost:5050
```

**Автоматический запуск по крону (каждый день в 10:00):**
```bash
crontab -e
# Добавить строку:
0 10 * * * cd /path/to/shorts-pipeline && nice -n 19 ./venv/bin/python3 shorts_v1.py >> data/logs/cron.log 2>&1
```

## Как это работает

1. **Поиск** — ищет видео по историческим запросам через YouTube Data API
2. **Скачивание** — скачивает через yt-dlp (720p, без плейлистов)
3. **Анализ** — через OpenRouter AI или по ключевым словам находит лучшие моменты 30-60 сек
4. **Нарезка** — FFmpeg нарезает Shorts (1080×1920), накладывает текст-крючок
5. **Субтитры** — faster-whisper распознаёт речь и накладывает субтитры
6. **Загрузка** — публикует на YouTube (3 мин пауза между загрузками)
7. **Очистка** — удаляет загруженные файлы и обработанное сырьё

## Структура

```
shorts-pipeline/
├── shorts_v1.py          # Основной пайплайн
├── web_admin.py          # Веб-админка (Flask)
├── upload_pending.py     # Дозагрузка pending шортсов
├── get_token.py          # Получение OAuth токена
├── start_web_admin.sh    # Запуск веб-админки
├── requirements.txt
├── .gitignore
├── data/
│   ├── raw/              # Скачанные видео
│   ├── processed/        # Готовые Shorts
│   └── logs/             # Логи
└── venv/                 # Виртуальное окружение
```

## Требования

- Python 3.8+
- FFmpeg
- yt-dlp
- YouTube API Key + OAuth credentials (YouTube Data API v3)
