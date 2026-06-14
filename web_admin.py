#!/usr/bin/env python3
"""
Web admin panel for YouTube Shorts Pipeline
"""

import os
import sys
import json
import sqlite3
import glob
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string, send_file

_pipeline_lock = threading.Lock()

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "shorts.db"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR = BASE_DIR / "data" / "raw"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shorts (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            video_id TEXT,
            video_title TEXT,
            part INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            comment TEXT DEFAULT '',
            youtube_url TEXT,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            uploaded_at TEXT,
            youtube_title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            tags TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT,
            videos_found INTEGER DEFAULT 0,
            shorts_created INTEGER DEFAULT 0,
            shorts_uploaded INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        )
    """)

    for col in ['youtube_title', 'description', 'tags', 'comments']:
        try:
            conn.execute(f"ALTER TABLE shorts ADD COLUMN {col} TEXT DEFAULT ''")
        except:
            pass
    conn.commit()
    conn.close()


def scan_and_sync():
    conn = get_db()
    existing = {row['id'] for row in conn.execute("SELECT id FROM shorts").fetchall()}
    new_count = 0

    for f in sorted(glob.glob(str(PROCESSED_DIR / "short_*.mp4"))):
        fpath = Path(f)
        sid = fpath.stem
        if sid not in existing:
            # filename: short_{safe}_{11ch_video_id}_{part}.mp4
            stem = sid.replace('short_', '', 1)
            last_underscore = stem.rfind('_')
            vid = ''
            part = 1
            if last_underscore >= 0:
                part = int(stem[last_underscore + 1:])
                before_part = stem[:last_underscore]
                vid_start = max(0, len(before_part) - 11)
                vid = before_part[vid_start:]
            # Try to find video title from raw files
            topic = ''
            for rf in sorted(RAW_DIR.iterdir()):
                if rf.suffix == '.webm' and rf.stem.startswith(vid + '_'):
                    topic = rf.stem[len(vid)+1:]
                    break
            if not topic:
                topic = "Amazing Facts"
            topic = topic.replace('_', ' ').strip()[:35]
            yt_title, yt_desc, yt_tags = generate_metadata(
                {'video_title': topic, 'part': part}
            )
            conn.execute(
                "INSERT OR IGNORE INTO shorts (id, filename, filepath, video_id, part, video_title, youtube_title, description, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, fpath.name, str(fpath), vid, part, topic, yt_title, yt_desc, yt_tags)
            )
            new_count += 1

    conn.commit()
    conn.close()
    return new_count


def generate_metadata(row):
    topic = (row['video_title'] or '').strip() if row['video_title'] else ''
    part = row['part'] or 1
    if topic:
        title_templates = [
            f"{topic} 😱",
            f"You Won't Believe This Fact About {topic.lower()}",
            f"🤯 {topic} — This Will Shock You",
            f"Why {topic.lower()}? The Answer Will Surprise You",
            f"😲 This Fact About {topic.lower()} Will Blow Your Mind",
        ]
        title = title_templates[(part - 1) % len(title_templates)]
    else:
        title = f"Amazing Short #{part}"

    desc = f"""🔥 Amazing historical facts you didn't know!

📌 Part {part}

Subscribe for more incredible facts! 🔔

#history #facts #shorts #historicalfacts #educational #interesting #historyfacts #didyouknow
"""
    tags = "history, facts, shorts, historical facts, educational, interesting history, did you know, history shorts"
    return title, desc, tags


def short_download_zip(sid):
    conn = get_db()
    row = conn.execute("SELECT * FROM shorts WHERE id=?", (sid,)).fetchone()
    conn.close()
    if not row:
        return None, 'Not found'
    video_path = row['filepath']
    if not os.path.exists(video_path):
        return None, 'File not found'

    title = (row['youtube_title'] or '').strip()
    desc = (row['description'] or '').strip()
    tags = (row['tags'] or '').strip()
    if not title:
        title, desc, tags = generate_metadata(row)

    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '.')).strip()[:60]
    safe_title = safe_title.rstrip('.')
    video_name = f"{safe_title}.mp4" if safe_title else row['filename']

    hashtags = ' '.join('#' + t.strip().replace(' ', '') for t in tags.split(',') if t.strip())

    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(video_path, video_name)
        meta = f"""Title: {title}

Description:
{desc}

Tags: {tags}

Hashtags:
{hashtags}
"""
        zf.writestr(f"{safe_title}.txt" if safe_title else "metadata.txt", meta)

    buf.seek(0)
    return buf, video_name


init_db()
scan_and_sync()


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YouTube Shorts Pipeline</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f0f; color: #e0e0e0; display: flex; min-height: 100vh; }

.sidebar { width: 240px; background: #1a1a1a; padding: 20px 0; border-right: 1px solid #2a2a2a; flex-shrink: 0; }
.sidebar h1 { font-size: 16px; padding: 0 20px 20px; border-bottom: 1px solid #2a2a2a; margin-bottom: 10px; color: #fff; }
.sidebar a { display: block; padding: 10px 20px; color: #aaa; text-decoration: none; font-size: 14px; cursor: pointer; }
.sidebar a:hover, .sidebar a.active { background: #2a2a2a; color: #fff; }
.sidebar .badge { float: right; background: #ff4444; color: #fff; border-radius: 10px; padding: 1px 8px; font-size: 11px; }

.main { flex: 1; padding: 24px; overflow-y: auto; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header h2 { font-size: 20px; color: #fff; }
.header .stats { display: flex; gap: 20px; }
.header .stat { text-align: center; }
.header .stat-num { font-size: 24px; font-weight: bold; color: #fff; }
.header .stat-label { font-size: 12px; color: #888; }

.actions { display: flex; gap: 10px; margin-bottom: 20px; }
.btn { padding: 8px 16px; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; }
.btn-primary { background: #3ea6ff; color: #000; }
.btn-primary:hover { background: #65b8ff; }
.btn-secondary { background: #2a2a2a; color: #e0e0e0; }
.btn-secondary:hover { background: #3a3a3a; }
.btn-success { background: #2ba640; color: #fff; }
.btn-success:hover { background: #35c050; }
.btn-danger { background: #cc0000; color: #fff; }
.btn-sm { padding: 4px 10px; font-size: 12px; }

.filters { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.filters select, .filters input { padding: 6px 12px; border-radius: 6px; border: 1px solid #333; background: #1a1a1a; color: #e0e0e0; font-size: 13px; }

.shorts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.short-card { background: #1a1a1a; border-radius: 10px; border: 1px solid #2a2a2a; overflow: hidden; transition: border-color .2s; }
.short-card:hover { border-color: #3ea6ff; }
.short-card .preview { width: 100%; aspect-ratio: 9/16; background: #000; display: flex; align-items: center; justify-content: center; font-size: 48px; color: #555; cursor: pointer; overflow: hidden; position: relative; }

.short-card .info { padding: 12px; }
.short-card .info-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.short-card .filename { font-size: 13px; color: #fff; word-break: break-all; }
.short-card .filesize { font-size: 11px; color: #888; }

.status-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.status-pending { background: #332200; color: #ffaa00; }
.status-uploaded { background: #003311; color: #00cc44; }
.status-error { background: #330000; color: #ff4444; }

.short-card .stats-row { display: flex; gap: 12px; margin-top: 8px; font-size: 12px; color: #888; }
.short-card .comment { margin-top: 8px; padding: 6px 8px; background: #222; border-radius: 4px; font-size: 12px; color: #aaa; min-height: 20px; }
.short-card .comment-input { width: 100%; margin-top: 6px; padding: 6px 8px; background: #222; border: 1px solid #333; border-radius: 4px; color: #e0e0e0; font-size: 12px; }
.short-card .card-actions { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }

.toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 20px; background: #2ba640; color: #fff; border-radius: 8px; font-size: 13px; opacity: 0; transition: opacity .3s; z-index: 100; }
.toast.error { background: #cc0000; }
.toast.show { opacity: 1; }



.video-link { color: #3ea6ff; text-decoration: none; font-size: 12px; }
.video-link:hover { text-decoration: underline; }

.modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.7); z-index: 50; align-items: center; justify-content: center; }
.modal.show { display: flex; }
.modal-content { background: #1a1a1a; border-radius: 12px; padding: 24px; max-width: 500px; width: 90%; border: 1px solid #333; }
.modal-content h3 { margin-bottom: 12px; color: #fff; }
.modal-actions { display: flex; gap: 10px; margin-top: 16px; justify-content: flex-end; }

.loading { text-align: center; padding: 40px; color: #555; }
.loading::after { content: '...'; animation: dots 1.5s infinite; }
@keyframes dots { 0%,20% { content: '.'; } 40% { content: '..'; } 60%,100% { content: '...'; } }
</style>
</head>
<body>

<div class="sidebar">
<h1>🎬 Shorts Pipeline</h1>
<a class="active" onclick="switchTab('shorts')">Shorts</a>
<a onclick="switchTab('runs')">Запуски</a>
<a onclick="switchTab('logs')">Логи</a>
</div>

<div class="main">
<div class="header">
<h2 id="pageTitle">Все шортсы</h2>
<div class="stats" id="headerStats"></div>
</div>

<div class="actions">
<button class="btn btn-primary" onclick="scanNow()">🔄 Сканировать</button>
<button class="btn btn-primary" onclick="runPipeline()">▶ Запустить пайплайн</button>
<button class="btn btn-secondary" onclick="refreshStats()">📊 Обновить статистику</button>
</div>

<div class="filters">
<select id="statusFilter" onchange="render()">
<option value="all">Все статусы</option>
<option value="pending">Ожидают</option>
<option value="uploaded">Загружены</option>
<option value="error">Ошибки</option>
</select>
<input type="text" id="searchFilter" placeholder="Поиск..." oninput="render()">
</div>

<div id="tabContent">
<div id="shortsTab" class="shorts-grid"></div>
<div id="runsTab" style="display:none"></div>
<div id="logsTab" style="display:none"><pre id="logContent" style="background:#111;padding:16px;border-radius:8px;font-size:12px;max-height:80vh;overflow-y:auto;white-space:pre-wrap;color:#888;"></pre></div>
</div>
</div>

<div class="toast" id="toast"></div>

<div class="modal" id="statsModal">
<div class="modal-content">
<h3>Статистика YouTube</h3>
<div id="statsModalBody"></div>
<div class="modal-actions"><button class="btn btn-secondary" onclick="closeStats()">Закрыть</button></div>
</div>
</div>

<script>

function downloadZip(id) {
    window.location.href = '/api/shorts/' + encodeURIComponent(id) + '/download';
}

async function saveMetadata(id, field, value) {
    const data = {};
    const s = shorts.find(x => x.id === id);
    if (!s) return;
    data.youtube_title = s.youtube_title || '';
    data.description = s.description || '';
    data.tags = s.tags || '';
    data[field] = value;
    await api('POST', `/api/shorts/${id}/metadata`, data);
    s[field] = value;
}

let shorts = [];
let runs = [];
let statsCache = {};

async function api(method, path, body) {
    const opts = { method, headers: {'Content-Type':'application/json'} };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(path, opts);
    return r.json();
}

function toast(msg, err) { const t=document.getElementById('toast'); t.textContent=msg; t.className='toast'+(err?' error':'')+' show'; setTimeout(()=>t.className='toast',2500); }

async function scanNow() {
    const r = await api('POST','/api/scan');
    toast('Найдено новых: '+r.added);
    await loadData();
}

async function loadData() {
    const r = await api('GET','/api/shorts');
    shorts = r.shorts || [];
    const r2 = await api('GET','/api/runs');
    runs = r2.runs || [];
    render();
}

function render() {
    const statusFilter = document.getElementById('statusFilter').value;
    const searchFilter = document.getElementById('searchFilter').value.toLowerCase();

    let filtered = shorts;
    if (statusFilter !== 'all') filtered = filtered.filter(s => s.status === statusFilter);
    if (searchFilter) filtered = filtered.filter(s => s.filename.toLowerCase().includes(searchFilter) || (s.video_title||'').toLowerCase().includes(searchFilter));

    const total = shorts.length;
    const pending = shorts.filter(s=>s.status==='pending').length;
    const uploaded = shorts.filter(s=>s.status==='uploaded').length;

    document.getElementById('headerStats').innerHTML = `
        <div class="stat"><div class="stat-num">${total}</div><div class="stat-label">Всего</div></div>
        <div class="stat"><div class="stat-num">${pending}</div><div class="stat-label">Ожидают</div></div>
        <div class="stat"><div class="stat-num">${uploaded}</div><div class="stat-label">Загружено</div></div>
    `;

    const grid = document.getElementById('shortsTab');
    grid.innerHTML = filtered.length ? filtered.map(s => renderCard(s)).join('') : '<div style="grid-column:1/-1;text-align:center;padding:40px;color:#555;">Нет шортсов</div>';
}

function renderCard(s) {
    const statusClass = 'status-'+s.status;
    const statusLabel = {pending:'Ожидает',uploaded:'Загружено',error:'Ошибка'}[s.status]||s.status;
    const ytUrl = s.youtube_url || '';
    const size = s.filesize ? (s.filesize/1024/1024).toFixed(1)+'MB' : '';
    const title = s.youtube_title || s.video_title || s.filename.replace(/\.mp4$/, '');
    return `<div class="short-card" data-id="${s.id}">
        <div class="info">
            <div class="info-row">
                <span class="filename" title="${s.filename}">${title}</span>
                <span class="status-badge ${statusClass}">${statusLabel}</span>
            </div>
            <div class="info-row">
                ${ytUrl ? `<a class="video-link" href="${ytUrl}" target="_blank">▶ YouTube</a>` : ''}
                <span>📅 ${s.created_at||''}</span>
            </div>
            <div class="stats-row">
                <span>👁 ${s.views||0}</span>
                <span>👍 ${s.likes||0}</span>
                <span>💬 ${s.comments||0}</span>
            </div>
            <div class="comment">${s.comment||'<span style="color:#555">нет комментария</span>'}</div>
            <input class="comment-input" placeholder="Комментарий..." value="${(s.comment||'').replace(/"/g,'&quot;')}" onchange="saveComment('${s.id}',this.value)">
            ${s.youtube_url ? `<button class="btn btn-sm btn-secondary" style="margin:4px 0" onclick="toggleComments('${s.id}',this)">💬 Комментарии YouTube</button><div class="yt-comments" id="yt-comments-${s.id}" style="display:none"></div>` : ''}
            <div class="card-actions">
                ${s.status==='pending' ? `<button class="btn btn-success btn-sm" onclick="markUploaded('${s.id}')">✓ Загружено</button>` : ''}
                ${s.status==='pending' ? `<button class="btn btn-sm btn-secondary" onclick="markError('${s.id}')">✗ Ошибка</button>` : ''}
                ${s.status!=='pending' ? `<button class="btn btn-sm btn-secondary" onclick="markPending('${s.id}')">↺ Вернуть</button>` : ''}
                <button class="btn btn-sm btn-secondary" onclick="fetchYouTubeStats('${s.id}')">📊 Stats</button>
                <button class="btn btn-sm btn-secondary" onclick="downloadZip('${s.id}')">⬇ ZIP</button>
            </div>
        </div>
    </div>`;
}

async function toggleComments(id, btn) {
    const div = document.getElementById('yt-comments-'+id);
    if (div.style.display !== 'none') { div.style.display = 'none'; btn.textContent = '💬 Комментарии YouTube'; return; }
    div.style.display = 'block';
    btn.textContent = '⏳ Загрузка...';
    div.innerHTML = '<div style="color:#555;padding:8px">Загрузка...</div>';
    const r = await api('GET', `/api/shorts/${id}/comments`);
    if (r.error) { div.innerHTML = `<div style="color:#e55;padding:8px">Ошибка: ${r.error}</div>`; btn.textContent = '💬 Комментарии YouTube'; return; }
    if (!r.comments || !r.comments.length) { div.innerHTML = '<div style="color:#555;padding:8px">Нет комментариев</div>'; btn.textContent = '💬 Комментарии YouTube'; return; }
    btn.textContent = '💬 Комментарии YouTube';
    div.innerHTML = r.comments.map(c => renderComment(c, id)).join('');
}

function renderComment(c, shortId) {
    const date = c.publishedAt ? new Date(c.publishedAt).toLocaleDateString('ru-RU') : '';
    const replies = c.replies && c.replies.length
        ? '<div style="margin-left:24px;margin-top:6px;border-left:2px solid #333;padding-left:8px">'
            + c.replies.map(r => `<div style="margin-bottom:4px"><b style="color:#888;font-size:11px">${escHtml(r.author)}</b> <span style="font-size:12px">${escHtml(r.text)}</span></div>`).join('')
            + '</div>'
        : '';
    return `<div style="margin-bottom:8px;padding:6px 8px;background:#1a1a1a;border-radius:4px">
        <div style="display:flex;justify-content:space-between;margin-bottom:2px">
            <b style="font-size:12px;color:#aaa">${escHtml(c.author)}</b>
            <span style="font-size:10px;color:#666">${date} · 👍 ${c.likeCount}</span>
        </div>
        <div style="font-size:13px;margin-bottom:4px">${escHtml(c.text)}</div>
        ${replies}
        <div style="margin-top:4px">
            <input class="comment-input" style="width:calc(100% - 60px);display:inline" placeholder="Ответить..." id="reply-input-${c.id}">
            <button class="btn btn-sm btn-secondary" style="display:inline" onclick="replyComment('${shortId}','${c.id}')">➤</button>
        </div>
    </div>`;
}

function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function replyComment(shortId, commentId) {
    const input = document.getElementById('reply-input-'+commentId);
    const text = input.value.trim();
    if (!text) return;
    const r = await api('POST', `/api/shorts/${shortId}/comments/${commentId}/reply`, {text});
    if (r.error) { toast(r.error, true); return; }
    toast('Ответ отправлен!');
    input.value = '';
    // Refresh comments
    const btn = document.querySelector(`[onclick*="toggleComments('${shortId}'"]`);
    if (btn) { btn.textContent = '⏳ Обновление...'; }
    const div = document.getElementById('yt-comments-'+shortId);
    if (div) {
        const r2 = await api('GET', `/api/shorts/${shortId}/comments`);
        if (r2.comments) {
            div.innerHTML = r2.comments.map(c => renderComment(c, shortId)).join('');
        }
    }
    if (btn) { btn.textContent = '💬 Комментарии YouTube'; }
}

async function saveComment(id, val) {
    await api('POST', `/api/shorts/${id}/comment`, {comment: val});
    await loadData();
}

async function markUploaded(id) {
    const s = shorts.find(x=>x.id===id);
    const url = prompt('YouTube URL (если есть):', s?.youtube_url||'');
    await api('POST', `/api/shorts/${id}/uploaded`, {youtube_url: url||''});
    toast('Отмечено как загружено');
    await loadData();
}

async function markError(id) {
    await api('POST', `/api/shorts/${id}/error`);
    toast('Отмечено как ошибка');
    await loadData();
}

async function markPending(id) {
    await api('POST', `/api/shorts/${id}/pending`);
    toast('Возвращено в ожидание');
    await loadData();
}

async function fetchYouTubeStats(id) {
    const r = await api('GET', `/api/shorts/${id}/stats`);
    if (r.error) { toast(r.error, true); return; }
    document.getElementById('statsModalBody').innerHTML = `
        <div style="margin-bottom:12px"><strong>${r.title||''}</strong></div>
        <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:4px 0;color:#888">Просмотры</td><td style="text-align:right"><b>${r.views||0}</b></td></tr>
        <tr><td style="padding:4px 0;color:#888">Лайки</td><td style="text-align:right"><b>${r.likes||0}</b></td></tr>
        <tr><td style="padding:4px 0;color:#888">Комментарии</td><td style="text-align:right"><b>${r.comments||0}</b></td></tr>
        </table>
        ${r.youtube_url ? `<a class="video-link" href="${r.youtube_url}" target="_blank" style="display:block;margin-top:12px">▶ Открыть на YouTube</a>` : ''}
    `;
    document.getElementById('statsModal').classList.add('show');
}

function closeStats() { document.getElementById('statsModal').classList.remove('show'); }

async function refreshStats() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳ Обновление...';
    toast('Обновляю статистику ('+shorts.filter(s=>s.youtube_url).length+' видео)...');
    const r = await api('POST', '/api/refresh-stats');
    toast('Готово: обновлено '+r.updated+' видео');
    btn.disabled = false;
    btn.textContent = '📊 Обновить статистику';
    await loadData();
}

async function runPipeline() {
    const btn = document.querySelector('button[onclick="runPipeline()"]');
    btn.disabled = true;
    btn.textContent = '⏳ Запуск...';
    toast('Запуск пайплайна...');
    const r = await api('POST', '/api/run-pipeline');
    if (!r.ok) {
        btn.disabled = false;
        btn.textContent = '▶ Запустить пайплайн';
        toast(r.error, true);
        return;
    }
    btn.textContent = '⏳ Выполняется...';
    // Poll for completion
    const poll = setInterval(async () => {
        const rr = await api('GET', '/api/runs');
        const run = rr.runs ? rr.runs[0] : null;
        if (run && run.status !== 'running') {
            clearInterval(poll);
            btn.disabled = false;
            btn.textContent = '▶ Запустить пайплайн';
            if (run.status === 'success') {
                toast('Пайплайн завершён: +' + run.shorts_created + ' шортсов');
            } else {
                toast('Ошибка пайплайна', true);
            }
            await loadData();
        }
    }, 5000);
}

function switchTab(tab) {
    document.querySelectorAll('.sidebar a').forEach(a=>a.classList.remove('active'));
    event.target.classList.add('active');
    ['shortsTab','runsTab','logsTab'].forEach(id => document.getElementById(id).style.display='none');
    if (tab==='shorts') {
        document.getElementById('shortsTab').style.display='grid';
        document.getElementById('pageTitle').textContent='Все шортсы';
    } else if (tab==='runs') {
        document.getElementById('runsTab').style.display='block';
        document.getElementById('pageTitle').textContent='История запусков';
        loadRuns();
    } else if (tab==='logs') {
        document.getElementById('logsTab').style.display='block';
        document.getElementById('pageTitle').textContent='Логи';
        loadLogs();
    }
}

async function loadRuns() {
    const r = await api('GET','/api/runs');
    const tab = document.getElementById('runsTab');
    if (!r.runs||!r.runs.length) { tab.innerHTML='<div style="color:#555;padding:20px">Нет запусков</div>'; return; }
    tab.innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr style="border-bottom:1px solid #333;color:#888"><th style="padding:8px;text-align:left">Время</th><th style="padding:8px;text-align:left">Статус</th><th style="padding:8px;text-align:right">Видео</th><th style="padding:8px;text-align:right">Шортсы</th><th style="padding:8px;text-align:right">Загружено</th></tr>
        ${r.runs.map(rn => `<tr style="border-bottom:1px solid #222">
            <td style="padding:8px">${rn.started_at}</td>
            <td style="padding:8px"><span class="status-badge status-${rn.status==='success'?'uploaded':'pending'}">${rn.status}</span></td>
            <td style="padding:8px;text-align:right">${rn.videos_found||0}</td>
            <td style="padding:8px;text-align:right">${rn.shorts_created||0}</td>
            <td style="padding:8px;text-align:right">${rn.shorts_uploaded||0}</td>
        </tr>`).join('')}
    </table>`;
}

async function loadLogs() {
    const r = await api('GET','/api/logs');
    document.getElementById('logContent').textContent = r.log||'Лог не найден';
}

loadData();
</script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/shorts')
def api_shorts():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, 
            COALESCE((SELECT SUM(shorts_uploaded) FROM pipeline_runs WHERE status='success'), 0) as total_uploaded
        FROM shorts s ORDER BY s.created_at DESC
    """).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        fp = d.get('filepath', '')
        d['filesize'] = os.path.getsize(fp) if fp and os.path.exists(fp) else 0
        result.append(d)
    return jsonify({'shorts': result})


@app.route('/api/shorts/<sid>/uploaded', methods=['POST'])
def mark_uploaded(sid):
    data = request.get_json() or {}
    youtube_url = data.get('youtube_url', '')
    conn = get_db()
    conn.execute(
        "UPDATE shorts SET status='uploaded', youtube_url=?, uploaded_at=datetime('now') WHERE id=?",
        (youtube_url, sid)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/shorts/<sid>/error', methods=['POST'])
def mark_error(sid):
    conn = get_db()
    conn.execute("UPDATE shorts SET status='error' WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/shorts/<sid>/pending', methods=['POST'])
def mark_pending(sid):
    conn = get_db()
    conn.execute("UPDATE shorts SET status='pending', youtube_url=NULL, uploaded_at=NULL WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/shorts/<sid>/comment', methods=['POST'])
def save_comment(sid):
    data = request.get_json() or {}
    comment = data.get('comment', '')
    conn = get_db()
    conn.execute("UPDATE shorts SET comment=? WHERE id=?", (comment, sid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/shorts/<sid>/comments')
def api_short_comments(sid):
    conn = get_db()
    row = conn.execute("SELECT youtube_url FROM shorts WHERE id=?", (sid,)).fetchone()
    conn.close()
    if not row or not row['youtube_url']:
        return jsonify({'comments': []})

    vid_id = None
    url = row['youtube_url']
    if '/shorts/' in url:
        vid_id = url.split('/shorts/')[1].split('?')[0].split('/')[0]
    elif 'watch?v=' in url:
        vid_id = url.split('watch?v=')[1].split('&')[0]

    if not vid_id:
        return jsonify({'comments': []})

    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        token_path = BASE_DIR / 'token.json'
        if not token_path.exists():
            return jsonify({'comments': []})
        creds = Credentials.from_authorized_user_info(
            json.loads(token_path.read_text()),
            ['https://www.googleapis.com/auth/youtube.force-ssl',
             'https://www.googleapis.com/auth/youtube.readonly']
        )
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        yt = build('youtube', 'v3', credentials=creds)
        resp = yt.commentThreads().list(
            part='snippet,replies',
            videoId=vid_id,
            maxResults=20,
            order='time'
        ).execute()

        comments = []
        for item in resp.get('items', []):
            top = item['snippet']['topLevelComment']['snippet']
            c = {
                'id': item['id'],
                'author': top.get('authorDisplayName', ''),
                'authorChannelUrl': top.get('authorChannelUrl', ''),
                'text': top.get('textOriginal', ''),
                'publishedAt': top.get('publishedAt', ''),
                'likeCount': top.get('likeCount', 0),
                'totalReplyCount': item['snippet'].get('totalReplyCount', 0),
                'replies': []
            }
            for reply in item.get('replies', {}).get('comments', []):
                rs = reply['snippet']
                c['replies'].append({
                    'id': reply['id'],
                    'author': rs.get('authorDisplayName', ''),
                    'text': rs.get('textOriginal', ''),
                    'publishedAt': rs.get('publishedAt', ''),
                    'likeCount': rs.get('likeCount', 0),
                })
            comments.append(c)
        return jsonify({'comments': comments})
    except Exception as e:
        logger.warning(f"Comments fetch failed: {e}")
        return jsonify({'error': str(e), 'comments': []})


@app.route('/api/shorts/<sid>/comments/<comment_id>/reply', methods=['POST'])
def api_reply_comment(sid, comment_id):
    data = request.get_json() or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'пустой текст'})

    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        token_path = BASE_DIR / 'token.json'
        if not token_path.exists():
            return jsonify({'error': 'токен не найден'})
        creds = Credentials.from_authorized_user_info(
            json.loads(token_path.read_text()),
            ['https://www.googleapis.com/auth/youtube.force-ssl']
        )
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        yt = build('youtube', 'v3', credentials=creds)
        reply = yt.comments().insert(
            part='snippet',
            body={
                'snippet': {
                    'parentId': comment_id,
                    'textOriginal': text
                }
            }
        ).execute()
        rs = reply['snippet']
        return jsonify({
            'ok': True,
            'reply': {
                'id': reply['id'],
                'author': rs.get('authorDisplayName', ''),
                'text': rs.get('textOriginal', ''),
                'publishedAt': rs.get('publishedAt', ''),
            }
        })
    except Exception as e:
        logger.warning(f"Reply failed: {e}")
        return jsonify({'error': str(e)})


@app.route('/api/shorts/<sid>/download')
def api_download_short(sid):
    buf, name = short_download_zip(sid)
    if buf is None:
        return jsonify({'error': name}), 404
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=f"{name}.zip")


@app.route('/api/shorts/<sid>/metadata', methods=['POST'])
def api_update_metadata(sid):
    data = request.get_json() or {}
    conn = get_db()
    conn.execute(
        "UPDATE shorts SET youtube_title=?, description=?, tags=? WHERE id=?",
        (data.get('youtube_title', ''), data.get('description', ''), data.get('tags', ''), sid)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/shorts/<sid>/stats')
def short_stats(sid):
    conn = get_db()
    row = conn.execute("SELECT * FROM shorts WHERE id=?", (sid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'не найден'})

    vid = row['video_id']
    youtube_url = row['youtube_url'] or ''

    if youtube_url:
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            token_path = BASE_DIR / 'token.json'
            if token_path.exists():
                creds = Credentials.from_authorized_user_info(
                    json.loads(token_path.read_text()),
                    ['https://www.googleapis.com/auth/youtube.readonly']
                )
                if creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                yt = build('youtube', 'v3', credentials=creds)
                vid_id = None
                if 'watch?v=' in youtube_url:
                    vid_id = youtube_url.split('watch?v=')[1].split('&')[0]
                elif '/shorts/' in youtube_url:
                    vid_id = youtube_url.split('/shorts/')[1].split('?')[0].split('/')[0]
                if vid_id:
                    resp = yt.videos().list(part='statistics,snippet', id=vid_id).execute()
                    if resp['items']:
                        st = resp['items'][0]['statistics']
                        sn = resp['items'][0]['snippet']
                        views = int(st.get('viewCount', 0))
                        likes = int(st.get('likeCount', 0))
                        comments = int(st.get('commentCount', 0))
                        conn2 = get_db()
                        conn2.execute("UPDATE shorts SET views=?, likes=?, comments=? WHERE id=?",
                            (views, likes, comments, sid))
                        conn2.commit()
                        conn2.close()
                        return jsonify({
                            'title': sn['title'],
                            'views': views,
                            'likes': likes,
                            'comments': comments,
                            'youtube_url': youtube_url
                        })
        except Exception as e:
            logger.warning(f"Stats fetch failed: {e}")

    return jsonify({'error': 'статистика недоступна', 'youtube_url': youtube_url})


@app.route('/api/refresh-stats', methods=['POST'])
def refresh_stats():
    conn = get_db()
    rows = conn.execute("SELECT id, youtube_url FROM shorts WHERE youtube_url IS NOT NULL AND youtube_url != ''").fetchall()
    conn.close()
    updated = 0
    for r in rows:
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            token_path = BASE_DIR / 'token.json'
            if token_path.exists():
                creds = Credentials.from_authorized_user_info(
                    json.loads(token_path.read_text()),
                    ['https://www.googleapis.com/auth/youtube.readonly']
                )
                if creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                yt = build('youtube', 'v3', credentials=creds)
                url = r['youtube_url']
                vid_id = None
                if 'watch?v=' in url:
                    vid_id = url.split('watch?v=')[1].split('&')[0]
                elif '/shorts/' in url:
                    vid_id = url.split('/shorts/')[1].split('?')[0].split('/')[0]
                if vid_id:
                    resp = yt.videos().list(part='statistics', id=vid_id).execute()
                    if resp['items']:
                        st = resp['items'][0]['statistics']
                        conn2 = get_db()
                        conn2.execute("UPDATE shorts SET views=?, likes=?, comments=? WHERE id=?",
                            (int(st.get('viewCount',0)), int(st.get('likeCount',0)), int(st.get('commentCount',0)), r['id']))
                        conn2.commit()
                        conn2.close()
                        updated += 1
        except:
            pass
    return jsonify({'updated': updated})


@app.route('/api/scan', methods=['POST'])
def scan():
    added = scan_and_sync()
    return jsonify({'added': added})


@app.route('/api/runs')
def api_runs():
    conn = get_db()
    rows = conn.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 20").fetchall()
    conn.close()
    return jsonify({'runs': [dict(r) for r in rows]})


@app.route('/api/run-pipeline', methods=['POST'])
def run_pipeline():
    if not _pipeline_lock.acquire(blocking=False):
        return jsonify({'ok': False, 'error': 'Пайплайн уже выполняется'}), 429

    conn = get_db()
    conn.execute("INSERT INTO pipeline_runs (status) VALUES ('running')")
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    def run():
        created_before = None
        try:
            conn3 = get_db()
            created_before = conn3.execute("SELECT COUNT(*) FROM shorts").fetchone()[0]
            conn3.close()

            import shorts_v1
            shorts_v1.CONFIG['data_dir'] = str(BASE_DIR / 'data')
            shorts_v1.CONFIG['raw_dir'] = str(BASE_DIR / 'data' / 'raw')
            shorts_v1.CONFIG['processed_dir'] = str(BASE_DIR / 'data' / 'processed')
            shorts_v1.CONFIG['logs_dir'] = str(BASE_DIR / 'data' / 'logs')

            import io
            from contextlib import redirect_stdout, redirect_stderr
            f = io.StringIO()
            with redirect_stdout(f), redirect_stderr(f):
                shorts_v1.main()

            scan_and_sync()

            conn2 = get_db()
            after = conn2.execute("SELECT COUNT(*) FROM shorts").fetchone()[0]
            new_shorts = after - (created_before or 0)
            conn2.execute(
                "UPDATE pipeline_runs SET status='success', finished_at=datetime('now'), shorts_created=? WHERE id=?",
                (new_shorts, run_id)
            )
            conn2.commit()
            conn2.close()
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            try:
                conn2 = get_db()
                conn2.execute("UPDATE pipeline_runs SET status='error', finished_at=datetime('now') WHERE id=?", (run_id,))
                conn2.commit()
                conn2.close()
            except:
                pass
        finally:
            _pipeline_lock.release()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({'ok': True, 'run_id': run_id})


@app.route('/api/logs')
def api_logs():
    today = datetime.now().strftime('%Y%m%d')
    log_path = BASE_DIR / 'data' / 'logs' / f'shorts_{today}.log'
    if log_path.exists():
        text = log_path.read_text(encoding='utf-8', errors='replace')
        return jsonify({'log': text[-10000:]})
    return jsonify({'log': 'Лог за сегодня не найден'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    logger.info(f"Запуск веб-админки на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
