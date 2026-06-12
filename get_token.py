#!/usr/bin/env python3
"""
Скрипт для получения OAuth токена YouTube
Запусти на своём компьютере с браузером, затем скопируй token.json на сервер
"""

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
CLIENT_SECRETS_FILE = 'credentials.json'

def main():
    import sys, json, time

    if len(sys.argv) == 2 and sys.argv[1] == '--gen-url':
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        auth_url, _ = flow.authorization_url(prompt='consent')

        state = {
            'code_verifier': flow.code_verifier,
            'client_id': flow.client_config['client_id'],
            'client_secret': flow.client_config.get('client_secret', ''),
            'token_uri': flow.client_config['token_uri'],
        }
        with open('.oauth_state.json', 'w') as f:
            json.dump(state, f)
        with open('auth_url.txt', 'w') as f:
            f.write(auth_url)

        print("=" * 60)
        print("ПЕРЕЙДИ ПО ССЫЛКЕ В БРАУЗЕРЕ И РАЗРЕШИ ДОСТУП:")
        print(auth_url)
        print("=" * 60)
        print()
        print("Ссылка сохранена в auth_url.txt")
        print()
        print("ПОСЛЕ ПОЛУЧЕНИЯ КОДА запусти:")
        print("  python get_token.py --save-token")
        return

    if len(sys.argv) == 2 and sys.argv[1] == '--save-token':
        code = input('Вставь код из браузера: ').strip()

        with open('.oauth_state.json', 'r') as f:
            state = json.load(f)

        client_config = {'installed': {
            'client_id': state['client_id'],
            'client_secret': state['client_secret'],
            'token_uri': state['token_uri'],
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs',
            'redirect_uris': ['http://localhost'],
            'project_id': 'shorts-pipeline-496607',
        }}
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        flow.code_verifier = state['code_verifier']

        flow.fetch_token(code=code)
        credentials = flow.credentials

        with open('token.json', 'w') as token:
            token.write(credentials.to_json())

        os.unlink('.oauth_state.json')

        print("✅ Токен получен и сохранён в token.json")

        youtube = build('youtube', 'v3', credentials=credentials)
        channels = youtube.channels().list(mine=True, part='snippet').execute()
        if channels['items']:
            print(f"Подключено к каналу: {channels['items'][0]['snippet']['title']}")
        return

    print("Использование:")
    print("  python get_token.py --gen-url       # получить ссылку для авторизации")
    print("  python get_token.py --save-token    # сохранить токен (после вставки кода)")

if __name__ == '__main__':
    main()