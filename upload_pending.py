#!/usr/bin/env python3
import sqlite3, os, sys, time, logging
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "data" / "shorts.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(BASE / "data" / "logs" / "upload_pending.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(BASE))
os.chdir(str(BASE))

from shorts_v1 import YouTubeUploader, generate_title_and_description

uploader = YouTubeUploader("credentials.json")
if not uploader.youtube:
    logger.error("YouTube client init failed")
    sys.exit(1)

done = 0
while True:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM shorts WHERE status IN ('pending','error') AND filepath LIKE ? ORDER BY created_at ASC LIMIT 1",
        (f"{BASE}/data/processed/%",)
    ).fetchone()
    conn.close()

    if not row:
        logger.info("All pending shorts uploaded!")
        break

    row = dict(row)
    path = row['filepath']
    if not os.path.exists(path):
        logger.warning(f"File not found: {path}")
        conn = sqlite3.connect(str(DB))
        conn.execute("UPDATE shorts SET status='error' WHERE id=?", (row['id'],))
        conn.commit()
        conn.close()
        continue

    title = (row.get('youtube_title') or '').strip()
    desc = (row.get('description') or '').strip()
    tags_str = (row.get('tags') or '').strip()
    if not title:
        topic = row.get('video_title') or "Amazing Facts"
        part = row['part'] or 1
        title, desc, tag_list = generate_title_and_description(topic, part, 20)
        tags_str = ', '.join(tag_list)
    else:
        tag_list = [t.strip() for t in tags_str.split(',') if t.strip()] or ['history', 'facts', 'shorts']

    # Проверка квоты перед загрузкой
    today_uploaded = sqlite3.connect(str(DB)).execute(
        "SELECT COUNT(*) FROM shorts WHERE status='uploaded' AND date(uploaded_at) = date('now')"
    ).fetchone()[0]
    if today_uploaded >= 10:
        tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=6, minute=0, second=0)
        wait = (tomorrow - datetime.now()).total_seconds()
        logger.warning(f"Лимит YT: {today_uploaded}/10. Жду до завтра ({wait/3600:.1f}ч)...")
        time.sleep(wait + 60)
        continue

    logger.info(f"[{done+1}] Uploading: {title}")
    import subprocess, os
    subprocess.run(['renice', '-n', '19', '-p', str(os.getpid())], capture_output=True)
    ok = uploader.upload_video(path, title, desc, tag_list)

    conn = sqlite3.connect(str(DB))
    if ok:
        vid = getattr(uploader, 'last_uploaded_id', '')
        yt_url = f"https://www.youtube.com/shorts/{vid}" if vid else ''
        conn.execute(
            "UPDATE shorts SET status='uploaded', youtube_url=?, uploaded_at=datetime('now'), youtube_title=?, description=?, tags=? WHERE id=?",
            (yt_url, title, desc, tags_str, row['id'])
        )
        logger.info(f"  OK -> {yt_url}")
        # Cleanup: удаляем загруженный файл
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"  Удалён: {path}")
        for ext in ['.srt', '_subbed.srt']:
            sub_path = path.replace('.mp4', ext)
            if os.path.exists(sub_path):
                os.remove(sub_path)
                logger.info(f"  Удалён: {sub_path}")
    else:
        conn.execute("UPDATE shorts SET status='error' WHERE id=?", (row['id'],))
        logger.error(f"  FAILED")
    conn.commit()
    conn.close()
    done += 1
    if done % 3 == 0:
        logger.info(f"Progress: {done} uploaded, sleeping 5min to avoid quota")
        time.sleep(300)
    else:
        time.sleep(185)

# Cleanup raw видео, от которых уже ничего не осталось
if done > 0:
    raw_dir = BASE / "data" / "raw"
    if raw_dir.exists():
        conn = sqlite3.connect(str(DB))
        imported = {r[0] for r in conn.execute("SELECT DISTINCT video_id FROM shorts WHERE video_id IS NOT NULL").fetchall()}
        conn.close()
        for f in raw_dir.iterdir():
            if f.suffix not in ('.webm', '.mp4', '.mkv', '.avi'):
                continue
            vid = f.stem.split('_')[0]
            if vid in imported:
                f.unlink()
                logger.info(f"Raw deleted: {f.name}")

logger.info(f"Done. Total uploaded this run: {done}")
