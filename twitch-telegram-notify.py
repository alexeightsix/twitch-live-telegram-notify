import requests
import json
import urllib.parse
import time
import sys


class twitch_client():
    def __init__(self, client_id, client_secret, redirect_uri):
        self.api_endpoint = 'https://api.twitch.tv'
        self.auth_endpoint = 'https://id.twitch.tv/oauth2/token'
        self.redirect_uri = redirect_uri
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = requests
        self.token = {}

    def load_token(self):
        try:
            f = '.twitch_token.json'
            file = filehandle = open(f, mode='r', encoding='utf-8')
            token = json.loads(file.read())
            file.close()
            if type(token) is dict:
                return token
        except ValueError:
            return None

    @staticmethod
    def update_token(token):
        file = filehandle = open('.twitch_token.json',
                                 mode='w', encoding='utf-8')

        token['expires_at'] = time.time() + token['expires_in']
        file.write(json.dumps(token))
        file.close()


    def get_access_token(self, code):
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
            'code': code
        }

        r = self.http.post(url=self.auth_endpoint, data=params)

        if r.status_code != 200:
            raise BaseException(r.json())

        token = r.json()
        self.update_token(token)
        return token

    def prompt_for_code(self):
        url = 'https://id.twitch.tv/oauth2/authorize?' + urllib.parse.urlencode({
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': 'user:read:follows'
        })
        ins = 'Open the following URL in your browser and paste the code param below:'
        code = input(ins + '\n\n\n' + url + '\n')
        return code

    def handle_token(self):
        token = self.load_token()
        if token is None or len(token) == 0:
            code = self.prompt_for_code()
            self.token = self.get_access_token(code)
        else:
            self.token = token

    def http_get_headers(self):
        return {
            'Authorization': f"Bearer {self.token['access_token']}",
            'Client-Id': self.client_id
        }

    def refresh_token(self):
        r = self.http.post(url=self.auth_endpoint, data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': self.token['refresh_token']
        })

        if r.status_code != 200:
            raise BaseException(r.json())

        token = r.json()
        self.update_token(token)

    def call(self, endpoint, params={}, method='GET'):
        url = self.api_endpoint + '/' + endpoint
        retries = 0

        while retries < 2:
            self.handle_token()

            if method == 'GET':
                r = self.http.get(url, params=params,
                                  headers=self.http_get_headers())
            elif method == 'POST':
                r = self.http.post(url, params=params,
                                   headers=self.http_get_headers())

            if r.status_code == 200:
                return r.json()

            if r.status_code == 401:
                self.refresh_token()
                retries = retries + 1
                continue

            raise BaseException(r.json())


class twitch_api():
    def __init__(self, client_id, client_secret, redirect_uri):
        self.client = twitch_client(client_id, client_secret, redirect_uri)

    def get_user_followed_streams(self, user_id):
        return self.client.call('helix/streams/followed', {'user_id': user_id})

    def get_user(self, login):
        return self.client.call('helix/users', {'login': login})['data'][0]


def config():
    cfg = filehandle = open('config.json', mode="r", encoding="utf-8")
    data = json.loads(cfg.read())
    cfg.close()
    return data


cfg = config()
api = twitch_api(cfg['twitch_client_id'], cfg['twitch_client_secret'], cfg['twitch_redirect_uri'])
user = api.get_user(cfg['twitch_user_name'])
followed = api.get_user_followed_streams(user['id'])


def telegram_push(chat_id, u):
    text = u['user_name'] + 'is live! (' + u['title'] + ')\n'
    text += "https://twitch.tv/" + u['user_login']
    response = requests.post(
        url=f'https://api.telegram.org/bot{cfg["telegram_api_token"]}/sendMessage',
        data={'chat_id': chat_id, 'text': text}
    ).json()


def is_processed(u, posts):
    for p in posts:
        if p['started_at'] == u['started_at']:
            return True
    return False


def get_processed_posts():
    db = filehandle = open('.processed.json', mode="r", encoding="utf-8")
    processed = json.loads(db.read())['processed']
    db.close()
    return processed


def update_db(contents):
    data = json.dumps({"processed": contents})
    db = filehandle = open('.processed.json', mode="w", encoding="utf-8")
    db.write(data)
    db.close()


processed = get_processed_posts()

if len(followed['data']) < 1:
    sys.exit(0)

p = 0

for u in followed['data']:
    if u['type'] != 'live':
        continue
    if is_processed(u, processed) is False:
        item = {
            'user_name': u['user_login'],
            'started_at': u['started_at']
        }
        telegram_push(cfg['telegram_chat_id'], u)
        processed.append(item)
        p = p + 1

if p > 0:
    update_db(processed)

