# TikTok Developer App Review — Submission Guide

## Use Case Description (вставь в форму)

**App name:** Shorts Uploader  
**Category:** Content Publishing / Social Media Management  
**Description:**
> Shorts Uploader is an automated short-form video publishing tool that creates and distributes historical/educational short videos (30-60 seconds) to social media platforms. The app downloads public domain educational content, creates engaging short clips with subtitles, and publishes them to connected social media accounts on a daily schedule. Content focuses on historical facts, ancient civilizations, and educational topics designed to inform and entertain viewers.

**How app uses TikTok API:**
> The app uses the Content Posting API to upload pre-processed MP4 video files directly to the user's TikTok account. Videos are 9:16 aspect ratio, 30-60 seconds long, with embedded subtitles. The app posts up to 5 videos per day from a single source video, with unique titles and descriptions for each clip. All content is original or derived from public domain educational sources with proper attribution.

**Privacy Policy URL:** `https://staff00700.github.io/shorts-pipeline/privacy-policy`  
**Terms of Service URL:** `https://staff00700.github.io/shorts-pipeline/terms-of-service`

## Demo Video Instructions

TikTok asks how your app works. Сделай скриншоты/видео:

1. **Логин** — покажи OAuth страницу TikTok (как приложение запрашивает доступ)
2. **Интерфейс** — покажи веб-админку (http://192.168.13.68:5050) с логом загрузок
3. **Результат** — покажи загруженное видео в TikTok (можно сделать тестовый приватный пост)

Или просто запиши экран на телефоне:
- Открой админку → покажи логи → покажи что видео создаются и грузятся

## Что заполнить в TikTok Developers Portal

1. **App Name:** Shorts Uploader
2. **App Description:** Automated short-form video publishing for educational history content
3. **Category:** Content Publishing
4. **Privacy Policy URL:** `https://staff00700.github.io/shorts-pipeline/privacy-policy`
5. **Terms of Service URL:** `https://staff00700.github.io/shorts-pipeline/terms-of-service`
6. **Authorized Redirect URIs:** `https://staff00700.github.io/shorts-pipeline/callback`
7. **Scopes requested:** `video.publish`, `video.upload`
8. **Use Case:** Paste the description above
9. **Demo video/сcreenshot:** Attach 2-3 screenshots (see instructions above)

## После одобрения

Когда ревью пройдёт, нужно будет:
1. Получить Client Key и Client Secret из настроек приложения
2. Прописать их в скрипт для OAuth
3. Авторизовать TikTok аккаунт
4. Добавить код загрузки в пайплайн шортсов (я это сделаю)

## Ссылки

- TikTok Developers: https://developers.tiktok.com
- Твоё приложение: https://developers.tiktok.com/app/
