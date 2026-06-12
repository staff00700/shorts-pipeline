#!/usr/bin/env python3
"""
YouTube Shorts Pipeline v1.0
Автоматический конвейер для создания и загрузки Shorts
"""

import os
import sys
import json
import time
import logging
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

# === КОНФИГУРАЦИЯ ===
CONFIG = {
    "api_key": "AIzaSyCw-rct2v0wKTrnAMBpPjdt_AhIlsrg6Ag",
    "credentials_file": "credentials.json",
    "openrouter_config_file": "OpenRouter.txt",
    "openrouter_api_key": None,
    "openrouter_model": None,
    "data_dir": "data",
    "raw_dir": "data/raw",
    "processed_dir": "data/processed",
    "logs_dir": "data/logs",
    "search_queries": [
        "historical facts documentary",
        "ancient history interesting",
        "world history secrets",
        "historical mysteries revealed",
        "amazing history facts",
        "undiscovered history",
        "historical events surprising"
    ],
    "max_videos_per_day": 1,
    "max_shorts_per_video": 5,
    "target_shorts_per_day": 5,
    "short_duration_min": 30,
    "short_duration_max": 60,
    "target_language": "en",
    "run_interval_hours": 24,
}

for directory in [CONFIG["data_dir"], CONFIG["raw_dir"], CONFIG["processed_dir"], CONFIG["logs_dir"]]:
    Path(directory).mkdir(parents=True, exist_ok=True)

os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{CONFIG["logs_dir"]}/shorts_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

or_config_path = Path(CONFIG["openrouter_config_file"])
if or_config_path.exists():
    lines = or_config_path.read_text().strip().splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith('@preset/'):
            CONFIG["openrouter_model"] = line
        elif line.startswith('sk-or-'):
            CONFIG["openrouter_api_key"] = line
    if CONFIG["openrouter_model"] and CONFIG["openrouter_api_key"]:
        logger.info(f"OpenRouter: загружен пресет {CONFIG['openrouter_model']}")
    else:
        logger.warning(f"OpenRouter: файл {CONFIG['openrouter_config_file']} не содержит пресет и/или ключ")


class YouTubeCollector:
    """Сборщик: поиск и скачивание видео с YouTube"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def search_videos(self, query, max_results=10):
        """Поиск видео по запросу через YouTube Data API"""
        logger.info(f"Поиск видео по запросу: {query}")

        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'videoDuration': 'medium',
            'order': 'relevance',
            'maxResults': max_results,
            'key': self.api_key
        }

        url = f"{self.base_url}/search"
        import requests
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            videos = []
            if 'items' in data:
                for item in data['items']:
                    videos.append({
                        'video_id': item['id']['videoId'],
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'channel_title': item['snippet']['channelTitle'],
                        'published_at': item['snippet']['publishedAt']
                    })

            logger.info(f"Найдено {len(videos)} видео")
            return videos
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []

    def get_video_details(self, video_id):
        """Получение детальной информации о видео"""
        params = {
            'part': 'contentDetails,statistics',
            'id': video_id,
            'key': self.api_key
        }

        url = f"{self.base_url}/videos"
        import requests
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if 'items' in data and len(data['items']) > 0:
                item = data['items'][0]
                return {
                    'duration': item['contentDetails'].get('duration', 'PT0M0S'),
                    'view_count': item['statistics'].get('viewCount', '0'),
                    'like_count': item['statistics'].get('likeCount', '0')
                }
        except Exception as e:
            logger.error(f"Ошибка получения деталей: {e}")

        return None

    def download_video(self, video_url, output_path):
        """Скачивание видео через yt-dlp"""
        logger.info(f"Скачивание: {video_url}")

        try:
            cmd = [
                'yt-dlp',
                '-f', 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                '--output', output_path,
                '--no-playlist',
                video_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                logger.info(f"Успешно скачано: {output_path}")
                return True
            else:
                logger.error(f"Ошибка скачивания: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Таймаут при скачивании")
            return False
        except Exception as e:
            logger.error(f"Исключение при скачивании: {e}")
            return False


class VideoAnalyzer:
    """AI анализатор: поиск лучших моментов в видео"""

    def __init__(self):
        self.model_loaded = False

    def load_model(self):
        """Загрузка модели для анализа (Ollama или альтернатива)"""
        logger.info("Проверка доступности AI модели...")

        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                self.model_loaded = True
                logger.info("Ollama доступна")
                return True
        except:
            pass

        logger.warning("AI модель недоступна - используем анализ по метаданным")
        return False

    def analyze_video(self, video_path, video_id=None, num_moments=3):
        """Анализ видео - ищем интересные моменты по маркерам"""
        logger.info(f"Анализ видео: {video_path}")

        if not os.path.exists(video_path):
            logger.error(f"Файл не найден: {video_path}")
            return []

        # Пробуем получить субтитры
        subtitles = None
        if video_id:
            subtitles = self._get_youtube_subtitles(video_id)

        if subtitles and len(subtitles) >= 10:
            logger.info(f"Анализируем {len(subtitles)} предложений из субтитров")
            moments = self._smart_moment_selection(subtitles, num_moments)
        else:
            logger.warning("Субтитры недоступны - используем базовый анализ")
            moments = self._basic_analysis(video_path, num_moments)

        logger.info(f"Выбрано {len(moments)} моментов для Shorts")
        return moments

    def _smart_moment_selection(self, subtitles, num_moments):
        """Умный выбор моментов - ищем интересные места по ключевым словам"""
        moments = []

        # Ключевые слова-маркеры интересных фактов
        interesting_markers = [
            'did you know', 'amazing', 'incredible', 'surprising', 'shocking',
            'fact', 'million', 'billion', 'percent', 'never', 'always',
            'first', 'largest', 'biggest', 'smallest', 'oldest', 'newest',
            'emperor', 'king', 'queen', 'war', 'discovery', 'invention',
            'secret', 'mystery', 'hidden', 'lost', 'ancient', 'historical'
        ]

        # Оцениваем каждое предложение
        scored = []
        for seg in subtitles:
            text_lower = seg['text'].lower()
            score = 0

            # Базовые очки за длину (более длинные предложения обычно содержат факты)
            score += min(len(seg['text']) / 50, 3)

            # Очки за маркеры
            for marker in interesting_markers:
                if marker in text_lower:
                    score += 2

            # Очки за числа (факты часто содержат числа)
            if any(c.isdigit() for c in seg['text'][:10]):
                score += 1

            # Очки за восклицания и вопросы
            if '!' in seg['text'] or '?' in seg['text']:
                score += 1

            scored.append({
                'index': len(scored),
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text'],
                'score': score
            })

        # Сортируем по score
        scored.sort(key=lambda x: x['score'], reverse=True)

        # Берём top моментов, распределённых по видео
        if len(scored) >= num_moments:
            # Выбираем лучшие моменты, но распределяем по времени
            selected = []
            used_ranges = []

            for item in scored[:num_moments * 3]:
                # Проверяем что не перекрывается с уже выбранными
                start = item['start']
                end = min(start + 45, item['end'])

                overlap = False
                for used_start, used_end in used_ranges:
                    if not (end <= used_start or start >= used_end):
                        overlap = True
                        break

                if not overlap and len(selected) < num_moments:
                    center_idx = item['index']
                    s_idx = max(0, center_idx - 3)
                    e_idx = min(len(subtitles) - 1, center_idx + 15)

                    start_time = subtitles[s_idx]['start']
                    end_time = subtitles[e_idx]['end']

                    # Расширяем пока не наберём 40+ секунд
                    while end_time - start_time < 40 and e_idx < len(subtitles) - 1:
                        e_idx += 5
                        end_time = subtitles[min(e_idx, len(subtitles)-1)]['end']

                    # Кап 58 секунд
                    if end_time - start_time > 58:
                        end_time = start_time + 55

                    # Текст превью из нескольких предложений
                    preview_parts = [s['text'][:60] for s in subtitles[s_idx:s_idx+3]]
                    text_preview = ' | '.join(preview_parts)[:100]

                    selected.append({
                        'start': int(start_time),
                        'end': int(end_time),
                        'duration': int(end_time - start_time),
                        'text_preview': text_preview
                    })
                    used_ranges.append((start_time, end_time))

            # Сортируем по времени
            selected.sort(key=lambda x: x['start'])
            moments = selected

        if not moments:
            # Fallback
            moments = self._basic_fallback(subtitles, num_moments)

        return moments

    def _basic_analysis(self, video_path, num_moments):
        """Базовый анализ по длительности видео"""
        try:
            ffprobe_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', video_path
            ]
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=30)
            total_duration = float(result.stdout.strip()) if result.stdout.strip() else 1800
        except:
            total_duration = 1800

        return self._basic_fallback_from_duration(total_duration, num_moments)

    def _basic_fallback_from_duration(self, total_duration, num_moments):
        """Fallback - равномерное деление"""
        moments = []
        block_size = total_duration / num_moments

        for i in range(num_moments):
            start = int((i + 0.3) * block_size)
            end = min(start + 40, int(total_duration))

            moments.append({
                'start': start,
                'end': end,
                'duration': end - start,
                'text_preview': 'Interesting historical moment'
            })

        return moments

    def _basic_fallback(self, subtitles, num_moments):
        """Fallback из субтитров без scoring"""
        if not subtitles:
            return self._basic_fallback_from_duration(1800, num_moments)

        total_duration = subtitles[-1]['end']
        return self._basic_fallback_from_duration(total_duration, num_moments)

    def _get_youtube_subtitles(self, video_id):
        """Получение субтитров с YouTube через yt-dlp"""
        logger.info(f"Скачиваю субтитры для {video_id}")

        try:
            cmd = [
                'yt-dlp',
                '--write-subs', '--write-auto-subs',
                '--sub-lang', 'en',
                '--skip-download',
                '--output', 'data/raw/%(id)s.%(ext)s',
                f'https://www.youtube.com/watch?v={video_id}'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Ищем скачанный файл субтитров
            import glob
            for ext in ['vtt', 'srt', 'json']:
                files = glob.glob(f'data/raw/*{video_id}*.{ext}')
                if files:
                    sub_file = files[0]
                    logger.info(f"Субтитры найдены: {sub_file}")
                    return self._parse_subtitles(sub_file)

        except Exception as e:
            logger.error(f"Ошибка получения субтитров: {e}")

        return None

    def _parse_subtitles(self, sub_file):
        """Парсинг субтитров в массив предложений"""
        segments = []
        lines_data = []

        try:
            with open(sub_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if sub_file.endswith('.vtt'):
                # Убираем HTML теги
                import re
                content = re.sub(r'<[^>]+>', '', content)

                # Разбиваем на строки
                all_lines = content.split('\n')

                current_start = None

                for line in all_lines:
                    line = line.strip()

                    # Пропускаем служебные строки
                    if not line or line.startswith('WEBVTT') or line.startswith('Kind') or line.startswith('Language'):
                        continue

                    # Ищем строку с временем
                    if '-->' in line:
                        parts = line.split('-->')
                        if len(parts) >= 2:
                            start_str = parts[0].strip().split()[0]
                            start_sec = self._time_to_seconds(start_str)
                            current_start = start_sec
                    # Это текстовая строка
                    elif line and current_start:
                        if line not in [' ', '']:
                            lines_data.append({
                                'time': current_start,
                                'text': line
                            })

                # Теперь объединяем строки в предложения
                current_sentence = []
                sentence_start = None

                for item in lines_data:
                    current_sentence.append(item['text'])

                    # Если строка заканчивается на . ? ! - это конец предложения
                    if any(item['text'].endswith(p) for p in '.?!') or len(current_sentence) >= 3:
                        full_text = ' '.join(current_sentence)

                        if len(full_text) > 15 and sentence_start:
                            segments.append({
                                'start': sentence_start,
                                'end': item['time'],
                                'text': full_text
                            })

                        current_sentence = []
                        sentence_start = None

                    if not sentence_start:
                        sentence_start = item['time']

        except Exception as e:
            logger.error(f"Ошибка парсинга субтитров: {e}")

        logger.info(f"Распознано {len(segments)} предложений из субтитров")
        return segments

    def _time_to_seconds(self, time_str):
        """Конвертация времени в секунды"""
        parts = time_str.replace(',', '.').split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return 0

class OpenRouterAnalyzer:
    """AI анализатор через OpenRouter API"""

    def __init__(self, config):
        self.api_key = config["openrouter_api_key"]
        self.model = config["openrouter_model"]
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def analyze(self, subtitles, video_title, video_duration, num_moments=4):
        if not self.api_key or not self.model:
            logger.warning("OpenRouter не настроен")
            return None

        if not subtitles or len(subtitles) < 5:
            logger.warning("Субтитров меньше 5 — OpenRouter не используется")
            return None

        subs_text = "\n".join(
            f"[{s['start']:.1f} - {s['end']:.1f}] {s['text']}"
            for s in subtitles[:200]
        )

        system_prompt = """Ты — эксперт по вирусным YouTube Shorts. Отвечаешь ТОЛЬКО JSON.

## Твоя задача
Выбрать моменты из видео, которые максимально зацепят зрителя в первые 3 секунды.

## Правило №1: Крючок (hook) решает всё
Первые 3 секунды клипа — это самая важная часть. Клип должен начинаться с:
- Неожиданного факта, который сложно поверить
- Шокирующей статистики
- Вопроса, вызывающего любопытство
- Противоречия или парадокса

НЕ начинай клип с:
- Скучного "The history of..." или "In this video..."
- Длинных предисловий и контекста

## Правила отбора моментов
1. Каждый клип должен быть самодостаточным и начинаться с крючка.
2. Длительность каждого клипа: от 25 до 40 секунд. Идеально — 30-35 секунд.
3. Клипы НЕ должны пересекаться — минимум 10 секунд между концом и началом следующего.
4. Клип должен начинаться с полного предложения, а не с середины фразы.
5. Клип должен заканчиваться логически завершённой мыслью.

## Формат ответа (СТРОГО JSON, БЕЗ ЛИШНЕГО ТЕКСТА)
..
  "clips": [
    ..
      "start": 123.0,
      "end": 155.0,
      "reason": "на русском, почему этот момент зацепит",
      "hook": "первая фраза, с которой начинается клип"
    ..
  ]
,.

## Важно!
- Не более MOMENTS_COUNT клипов на видео.
- Длительность клипа (end - start) должна быть от 25 до 40 секунд.
- Ответ должен быть ТОЛЬКО JSON. Никаких объяснений, комментариев или markdown.
- start/end строго в секундах""".replace('..', '{').replace(',.', '}')

        user_prompt = f"""Название видео: {video_title}
Общая длительность: {video_duration:.0f} секунд
Нужно клипов: {num_moments}

Субтитры:
{subs_text}"""

        logger.info(f"OpenRouter: отправляю субтитры ({len(subtitles)} предложений) в {self.model}")

        try:
            import requests
            response = requests.post(
                self.api_url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/ares-bot',
                    'X-Title': 'YouTube Shorts Pipeline'
                },
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt.replace('MOMENTS_COUNT', str(num_moments))},
                        {'role': 'user', 'content': user_prompt}
                    ]
                },
                timeout=120
            )

            if not response.ok:
                logger.error(f"OpenRouter: HTTP {response.status_code}: {response.text[:200]}")
                return None

            data = response.json()
            if not data.get('choices'):
                logger.error("OpenRouter: пустой ответ")
                return None

            content = data['choices'][0]['message']['content'].strip()
            logger.debug(f"OpenRouter сырой ответ: {content[:500]}")

            if content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content[3:]
                if content.endswith('```'):
                    content = content[:-3].strip()
                elif '```' in content:
                    content = content.rsplit('```', 1)[0].strip()
                content = content.strip()
                if content.startswith('json'):
                    content = content[4:].strip()

            result = json.loads(content)

            if 'error' in result:
                logger.warning(f"OpenRouter: {result['error']}")
                return None

            clips = result.get('clips', [])
            if not clips:
                logger.warning("OpenRouter: не нашёл клипов")
                return None

            moments = []
            for clip in clips[:num_moments]:
                start = int(clip['start'])
                end = int(clip['end'])
                duration = end - start
                if duration < 20:
                    end = start + 28
                    duration = 28
                if duration > 45:
                    end = start + 38
                    duration = 38
                moments.append({
                    'start': start,
                    'end': end,
                    'duration': duration,
                    'hook': clip.get('hook', '')[:100],
                    'text_preview': clip.get('reason', clip.get('hook', ''))[:100]
                })

            logger.info(f"OpenRouter: выбрано {len(moments)} моментов")
            return moments

        except requests.Timeout:
            logger.error("OpenRouter: таймаут")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"OpenRouter: ошибка парсинга JSON: {e}")
            raw_snippet = content if 'content' in dir() else 'N/A'
            logger.error(f"OpenRouter: контент: {raw_snippet[:300]}")
            return None
        except Exception as e:
            logger.error(f"OpenRouter: ошибка: {e}")
            return None


class ShortsProcessor:
    """Процессор: нарезка, субтитры, обработка звука"""

    def __init__(self, config):
        self.config = config

    def create_short(self, video_path, moment, output_path, topic):
        """Создание одного Short из момента"""
        start = moment['start']
        duration = moment['duration']
        hook = moment.get('hook', '').strip() or topic[:50]

        logger.info(f"Создание Short: {output_path} ({start}-{start+duration} сек)")

        try:
            hook_lines = []
            words = hook.split()
            line = ''
            for w in words:
                if len(line + ' ' + w) > 35:
                    hook_lines.append(line)
                    line = w
                else:
                    line = (line + ' ' + w).strip()
            if line:
                hook_lines.append(line)
            hook_text = '\\n'.join(hook_lines[:3])

            font = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
            if not os.path.exists(font):
                font = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
            if not os.path.exists(font):
                font = ''

            filter_parts = [
                'scale=1080:1920:force_original_aspect_ratio=decrease',
                'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black'
            ]

            if hook_text and font:
                import shlex
                escaped_hook = hook_text.replace("'", "'\\\\''").replace(':', '\\\\:')
                filter_parts.append(
                    f"drawtext=text='{escaped_hook}'"
                    f":fontfile={font}"
                    f":fontsize=48"
                    f":fontcolor=white"
                    f":box=1:boxcolor=black@0.65:boxborderw=20"
                    f":x=(w-text_w)/2:y=h*0.15"
                    f":enable='between(t,0,3)'"
                )

            if font and duration > 4:
                cta_start = duration - 4
                filter_parts.append(
                    f"drawtext=text='Like & Subscribe'"
                    f":fontfile={font}"
                    f":fontsize=56"
                    f":fontcolor=yellow"
                    f":box=1:boxcolor=black@0.7:boxborderw=24"
                    f":x=(w-text_w)/2:y=h*0.75"
                    f":enable='between(t,{cta_start},{duration})'"
                )
                filter_parts.append(
                    f"drawtext=text='Подпишись'"
                    f":fontfile={font}"
                    f":fontsize=42"
                    f":fontcolor=white"
                    f":box=1:boxcolor=black@0.5:boxborderw=16"
                    f":x=(w-text_w)/2:y=h*0.75+70"
                    f":enable='between(t,{cta_start},{duration})'"
                )

            filter_parts = [p for p in filter_parts if p.strip()]
            vf = ','.join(filter_parts)

            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-ss', str(start),
                '-t', str(duration),
                '-vf', vf,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '28',
                '-threads', '1',
                '-c:a', 'aac',
                '-b:a', '128k',
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Short создан: {output_path}")

                if self._has_audio(output_path):
                    logger.info("Звук присутствует - оставляем оригинальный")
                else:
                    logger.warning("Нет звука - нужно добавить TTS")

                return True
            else:
                logger.error(f"Ошибка создания Short (filter: {vf}): {result.stderr[:500]}")
                return False

        except Exception as e:
            logger.error(f"Исключение при создании Short: {e}")
            return False

    def _has_audio(self, video_path):
        """Проверка наличия звука в видео"""
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_type', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return 'audio' in result.stdout
        except:
            return False

    def add_subtitles(self, video_path, output_path, language='en'):
        """Добавление субтитров через faster-whisper"""
        logger.info(f"Генерация субтитров для: {video_path}")

        try:
            from faster_whisper import WhisperModel

            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(video_path, language=language, vad_filter=True)
            segments_list = list(segments)

            if not segments_list:
                logger.warning("Whisper не распознал речь")
                return False

            subtitles_path = output_path.replace('.mp4', '.srt')
            self._create_srt(segments_list, subtitles_path)

            cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-vf', f"subtitles={subtitles_path}",
                '-threads', '1',
                '-c:a', 'copy',
                output_path
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            logger.info("Субтитры добавлены")

            return True

        except Exception as e:
            logger.warning(f"Не удалось добавить субтитры: {e}")
            return False

    def _create_srt(self, segments, output_path):
        """Создание SRT файла из сегментов"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                if hasattr(segment, 'start'):
                    start = self._format_time(segment.start)
                    end = self._format_time(segment.end)
                    text = segment.text.strip()
                else:
                    start = self._format_time(segment['start'])
                    end = self._format_time(segment['end'])
                    text = segment['text'].strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

    def _format_time(self, seconds):
        """Форматирование времени для SRT"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class YouTubeUploader:
    """Загрузчик: публикация видео на YouTube"""

    def __init__(self, credentials_file):
        self.credentials_file = credentials_file
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Аутентификация через OAuth"""
        logger.info("Аутентификация YouTube API...")

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

            credentials = None

            # Сначала пробуем использовать сохранённый токен
            if os.path.exists('token.json'):
                logger.info("Использую сохранённый токен token.json")
                credentials = Credentials.from_authorized_user_info(
                    json.loads(open('token.json').read()), SCOPES)

            # Если токена нет или он истёк - используем credentials.json
            elif os.path.exists(self.credentials_file):
                logger.info("Получаю новый токен через credentials.json")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                credentials = flow.run_local_server(port=8080, prompt='consent')

                # Сохраняем токен для следующих запусков
                with open('token.json', 'w') as token:
                    token.write(credentials.to_json())
                logger.info("Токен сохранён в token.json")
            else:
                logger.error(f"Файл credentials не найден: {self.credentials_file}")
                self.youtube = None
                return

            # Проверяем валидность токена и рефрешим если надо
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    from google.auth.transport.requests import Request
                    credentials.refresh(Request())
                    logger.info("Токен обновлён")
                    with open('token.json', 'w') as token:
                        token.write(credentials.to_json())
                except Exception as e:
                    logger.error(f"Ошибка refresh токена: {e}")

            if credentials and credentials.valid:
                self.youtube = build('youtube', 'v3', credentials=credentials)
                self.MediaFileUpload = MediaFileUpload

                # Проверяем какой канал подключён
                try:
                    channels = self.youtube.channels().list(mine=True, part='snippet').execute()
                    if channels['items']:
                        channel_name = channels['items'][0]['snippet']['title']
                        logger.info(f"✅ Подключено к каналу: {channel_name}")
                except:
                    pass

                logger.info("Аутентификация успешна")
            else:
                logger.error("Токен недействителен")
                self.youtube = None

        except Exception as e:
            logger.error(f"Ошибка аутентификации: {e}")
            self.youtube = None

    def upload_video(self, video_path, title, description, tags=None):
        """Загрузка видео на YouTube"""
        if not self.youtube:
            logger.error("YouTube API не инициализирован")
            return False

        logger.info(f"Загрузка: {title}")

        try:
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': '24',  # Entertainment
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False,
                }
            }

            media = self.MediaFileUpload(video_path, chunksize=-1, resumable=True)

            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = request.execute()

            if response and 'id' in response:
                vid = response['id']
                logger.info(f"Загружено! Video ID: {vid}")
                self.last_uploaded_id = vid
                return True
            else:
                logger.error("Ошибка загрузки")
                return False

        except Exception as e:
            logger.error(f"Исключение при загрузке: {e}")
            return False


def generate_title_and_description(topic, part_number, total_parts):
    """Генерация цепляющего заголовка и описания для Short"""
    short_topic = topic[:35].strip().rstrip(',').rstrip('.')
    templates = [
        f"{short_topic} 😱",
        f"You Won't Believe This Fact About {short_topic.lower()}",
        f"🤯 {short_topic} — This Will Shock You",
        f"Why {short_topic.lower()}? The Answer Will Surprise You",
        f"😲 This Fact About {short_topic.lower()} Will Blow Your Mind",
    ]
    title = templates[(part_number - 1) % len(templates)]

    description = f"""🔥 Amazing historical facts you didn't know!

📌 Part {part_number} of {total_parts}

Subscribe for more incredible facts! 🔔

#history #facts #shorts #historicalfacts #educational #interesting #historyfacts #didyouknow
"""

    tags = ['history', 'facts', 'shorts', 'historical facts', 'educational', 'interesting history', 'did you know', 'history shorts']

    return title, description, tags


def main():
    """Основная функция - главный цикл конвейера"""
    logger.info("="*50)
    logger.info("Запуск YouTube Shorts Pipeline v1.0")
    logger.info("="*50)

    collector = YouTubeCollector(CONFIG['api_key'])
    or_analyzer = OpenRouterAnalyzer(CONFIG) if CONFIG["openrouter_api_key"] else None
    analyzer = VideoAnalyzer()
    processor = ShortsProcessor(CONFIG)

    uploader = YouTubeUploader(CONFIG['credentials_file'])

    logger.info("Этап 1: Поиск и скачивание видео")

    downloaded_videos = []
    seen_ids = set()

    prev_ids = set()
    db_path = Path(CONFIG.get('data_dir', 'data')) / 'shorts.db'
    if db_path.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            for row in conn.execute('SELECT DISTINCT video_id FROM shorts WHERE video_id IS NOT NULL'):
                prev_ids.add(row[0])
            for row in conn.execute('SELECT DISTINCT video_id FROM processed_videos WHERE video_id IS NOT NULL'):
                prev_ids.add(row[0])
            conn.close()
        except Exception:
            pass

    import random
    queries = list(CONFIG['search_queries'])
    random.shuffle(queries)

    for query in queries:
        if len(downloaded_videos) >= CONFIG['max_videos_per_day']:
            break

        videos = collector.search_videos(query, max_results=5)

        for video_data in videos:
            video_id = video_data['video_id']
            if video_id in seen_ids or video_id in prev_ids:
                continue

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            video_title = video_data['title']

            safe_title = "".join(c for c in video_title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]

            if collector.download_video(video_url, f"{CONFIG['raw_dir']}/{video_id}_{safe_title}"):
                import glob
                downloaded_file = glob.glob(f"{CONFIG['raw_dir']}/{video_id}_{safe_title}.*")[0] if glob.glob(f"{CONFIG['raw_dir']}/{video_id}_{safe_title}.*") else None
                if downloaded_file:
                    downloaded_videos.append({
                        'path': downloaded_file,
                        'title': video_title,
                        'id': video_id
                    })
                    seen_ids.add(video_id)
                    # Запоминаем video_id чтобы не скачать повторно
                    try:
                        conn2 = sqlite3.connect(str(db_path))
                        conn2.execute("INSERT OR IGNORE INTO processed_videos (video_id) VALUES (?)", (video_id,))
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass

            time.sleep(2)

    logger.info(f"Скачано {len(downloaded_videos)} видео")

    logger.info("Этап 2: Анализ и создание Shorts")

    all_shorts = []

    for video_data in downloaded_videos:
        video_path = video_data['path']
        video_title = video_data['title']
        video_id = video_data['id']

        if not os.path.exists(video_path):
            continue

        logger.info(f"Обработка видео: {video_title}")

        subtitles_for_ai = None
        if video_id:
            subtitles_for_ai = analyzer._get_youtube_subtitles(video_id)

        moments = None
        if or_analyzer and subtitles_for_ai and len(subtitles_for_ai) >= 5:
            video_duration = 0
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                    capture_output=True, text=True, timeout=30
                )
                video_duration = float(result.stdout.strip()) if result.stdout.strip() else 1800
            except Exception:
                video_duration = 1800
            moments = or_analyzer.analyze(
                subtitles_for_ai, video_title, video_duration, CONFIG['max_shorts_per_video']
            )

        if not moments:
            moments = analyzer.analyze_video(video_path, video_id, CONFIG['max_shorts_per_video'])

        topic = video_title[:40].strip()

        for i, moment in enumerate(moments):
            safe = "".join(c for c in video_title if c.isalnum() or c in (' ', '-')).strip()[:25]
            short_filename = f"short_{safe}_{video_data['id']}_{i+1}.mp4"
            short_path = os.path.join(CONFIG['processed_dir'], short_filename)

            if processor.create_short(video_path, moment, short_path, topic):
                subbed = short_path.replace('.mp4', '_subbed.mp4')
                if processor.add_subtitles(short_path, subbed):
                    os.replace(subbed, short_path)
                    logger.info(f"Субтитры наложены: {short_path}")
                part_num = len(all_shorts) + 1
                yt_title, yt_desc, yt_tags = generate_title_and_description(topic, part_num, CONFIG['max_shorts_per_video'])
                all_shorts.append({
                    'path': short_path,
                    'topic': topic,
                    'part': part_num,
                    'youtube_title': yt_title,
                    'description': yt_desc,
                    'tags': ', '.join(yt_tags)
                })

                logger.info(f"Пауза 30 сек перед следующим шортом...")
                time.sleep(30)

        logger.info(f"Пауза 60 сек перед следующим видео...")
        time.sleep(60)

    logger.info(f"Создано {len(all_shorts)} Shorts")

    import sqlite3
    db_path = Path(CONFIG.get('data_dir', 'data')) / 'shorts.db'

    for short in all_shorts:
        sid = Path(short['path']).stem
        # filename: short_{safe}_{11ch_video_id}_{part}.mp4
        # YouTube video_id всегда 11 символов, берём перед последним разделителем
        stem = sid.replace('short_', '', 1)
        last_underscore = stem.rfind('_')
        if last_underscore >= 0:
            part = int(stem[last_underscore + 1:])
            before_part = stem[:last_underscore]
            vid_start = max(0, len(before_part) - 11)
            video_id = before_part[vid_start:]
        else:
            video_id = ''
            part = 1
        try:
            db = sqlite3.connect(str(db_path))
            db.execute("""INSERT OR IGNORE INTO shorts
                (id, filename, filepath, video_id, part, video_title, youtube_title, description, tags, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (sid, Path(short['path']).name, short['path'], video_id, part,
                 short.get('topic', ''), short.get('youtube_title', ''),
                 short.get('description', ''), short.get('tags', '')))
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Ошибка сохранения в БД: {e}")

    logger.info("Этап 3: Загрузка на YouTube")

    shorts_to_upload = all_shorts[:CONFIG['target_shorts_per_day']]

    uploaded_count = 0

    for short in shorts_to_upload:
        title = short.get('youtube_title', '')
        description = short.get('description', '')
        tags = short.get('tags', '')
        tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []

        if uploader.upload_video(short['path'], title, description, tag_list):
            logger.info(f"Загружен: {title}")
            uploaded_count += 1
            try:
                sid = Path(short['path']).stem
                vid = getattr(uploader, 'last_uploaded_id', '')
                yt_url = f"https://www.youtube.com/shorts/{vid}" if vid else ''
                db = sqlite3.connect(str(db_path))
                db.execute("UPDATE shorts SET status='uploaded', youtube_url=?, uploaded_at=datetime('now') WHERE id=?", (yt_url, sid))
                db.commit()
                db.close()

                # Cleanup: удаляем загруженный шорт и его субтитры
                short_path = short['path']
                if os.path.exists(short_path):
                    os.remove(short_path)
                    logger.info(f"Удалён: {short_path}")
                for ext in ['.srt', '_subbed.srt']:
                    sub_path = short_path.replace('.mp4', ext)
                    if os.path.exists(sub_path):
                        os.remove(sub_path)
                        logger.info(f"Удалён: {sub_path}")
            except Exception as e:
                logger.error(f"Ошибка обновления БД для {short['path']}: {e}")
        else:
            logger.error(f"Не удалось загрузить: {short['path']}")

        time.sleep(180)  # 3 мин между загрузками — естественнее для алгоритма

    logger.info("Этап 4: Очистка сырых видео")

    raw_dir = Path(CONFIG['raw_dir'])
    if raw_dir.exists():
        imported_video_ids = set()
        db_for_cleanup = sqlite3.connect(str(db_path))
        for row in db_for_cleanup.execute("SELECT DISTINCT video_id FROM shorts WHERE video_id IS NOT NULL"):
            imported_video_ids.add(row[0])
        db_for_cleanup.close()

        for rf in sorted(raw_dir.iterdir()):
            if rf.suffix not in ('.webm', '.mp4', '.mkv', '.avi'):
                continue
            vid = rf.stem.split('_')[0]
            if vid in imported_video_ids:
                rf.unlink()
                logger.info(f"Удалён raw: {rf.name}")
            elif rf.stat().st_mtime < time.time() - 86400:
                rf.unlink()
                logger.info(f"Удалён старый raw: {rf.name}")

    logger.info("="*50)
    logger.info(f"Цикл завершен. Успешно загружено {uploaded_count}/{len(shorts_to_upload)} Shorts")
    logger.info(f"Следующий запуск через {CONFIG['run_interval_hours']} часов")
    logger.info("="*50)


if __name__ == "__main__":
    main()