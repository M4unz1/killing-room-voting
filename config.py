"""Shared settings for local play, central hosting and the Windows relay."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parent
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
DEFAULTS = {
    'minimum_votes': 1,
    'server': {'mode': 'local', 'bind': '127.0.0.1', 'port': 8765, 'public_url': ''},
    'client': {'server_url': '', 'player_name': '', 'game_dll': '', 'game_executable': ''},
    'connection_timeout_seconds': 120,
    'discord': {'enabled': False, 'channel_id': '', 'guild_id': ''},
    'stats': {'public': True},
    'registration': {'enabled': True, 'per_hour': 60, 'max_clients': 10000},
}


def merge(base, values):
    for key, value in values.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            merge(base[key], value)
        else:
            base[key] = value
    return base


def load_env(path=None):
    path = Path(path or ROOT/'settings.env')
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key.replace('_', '').isalnum():
            raise ValueError('Ungueltige Zeile in settings.env.')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def load_settings(path=None):
    path = Path(path or ROOT/'settings.json')
    settings = copy.deepcopy(DEFAULTS)
    if path.exists():
        values = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(values, dict):
            raise ValueError('settings.json muss ein JSON-Objekt enthalten.')
        merge(settings, values)
    minimum = settings.get('minimum_votes')
    if type(minimum) is not int or not 1 <= minimum <= 127:
        raise ValueError('minimum_votes muss eine ganze Zahl zwischen 1 und 127 sein.')
    timeout=settings['connection_timeout_seconds']
    if type(timeout) is not int or timeout!=0 and not 5<=timeout<=86400:
        raise ValueError('connection_timeout_seconds: 0 zum Deaktivieren oder 5 bis 86400 Sekunden.')
    for key in ('server', 'client', 'discord', 'stats', 'registration'):
        if not isinstance(settings.get(key), dict):
            raise ValueError(key + ' muss ein JSON-Objekt sein.')
    for env, key in [('KR_MODE','mode'),('KR_BIND','bind'),('KR_PUBLIC_URL','public_url')]:
        if os.environ.get(env):
            settings['server'][key] = os.environ[env]
    if os.environ.get('KR_PORT'):
        settings['server']['port'] = int(os.environ['KR_PORT'])
    if settings['server']['mode'] not in ('local', 'hub'):
        raise ValueError('server.mode muss local oder hub sein.')
    if type(settings['server']['port']) is not int or not 1 <= settings['server']['port'] <= 65535:
        raise ValueError('Ungueltiger Server-Port.')
    if type(settings['discord'].get('enabled')) is not bool or type(settings['stats'].get('public')) is not bool:
        raise ValueError('enabled/public muss true oder false sein.')
    if type(settings['registration'].get('enabled')) is not bool:
        raise ValueError('registration.enabled muss true oder false sein.')
    for key in ('per_hour','max_clients'):
        value=settings['registration'].get(key)
        if type(value) is not int or not 1<=value<=1000000:
            raise ValueError('registration.'+key+': ganze Zahl von 1 bis 1000000.')
    name=settings['client'].get('player_name','')
    if not isinstance(name,str) or len(name)>80 or any(ord(c)<32 for c in name):
        raise ValueError('client.player_name: maximal 80 Zeichen ohne Steuerzeichen.')
    return settings


def save_settings(settings, path=None):
    path = Path(path or ROOT/'settings.json')
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(settings, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    os.replace(temp, path)


def validate_url(value, allow_local_http=False):
    value = value.rstrip('/')
    parsed = urlsplit(value)
    local = parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if (not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path or parsed.scheme != 'https' and not (allow_local_http and local and parsed.scheme == 'http')):
        raise ValueError('Eine HTTPS-Basisadresse ohne Pfad verwenden, z.B. https://vote.example.de.')
    return value


def client_token(base):
    """Keep one automatically generated credential per server on this PC.

    Save before sending, so interrupted registrations can retry with the same
    key. Explicit keys in settings.env remain supported for private servers.
    """
    token=api_token()
    if token and not token.startswith('HIER_'):
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token):
            raise ValueError('Der vorhandene KR_GAME_API_TOKEN ist ungueltig.')
        return token,False
    folder=ROOT/'client_keys'
    folder.mkdir(mode=0o700,exist_ok=True)
    path=folder/('client-'+hashlib.sha256(base.encode()).hexdigest()+'.key')
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        # Another launcher may still be completing its first write.
        for attempt in range(20):
            token=path.read_text(encoding='ascii').strip()
            if token:break
            time.sleep(.05)
    else:
        token=secrets.token_urlsafe(48)
        with os.fdopen(fd,'w',encoding='ascii') as stream:
            stream.write(token+'\n')
            stream.flush()
            os.fsync(stream.fileno())
    if not re.fullmatch(r'[A-Za-z0-9_-]{64}',token):
        raise ValueError('Die lokale Schluesseldatei ist beschaedigt. Sicherung in client_keys/ pruefen.')
    return token,True


def remote_configuration(settings):
    base = validate_url(settings['client']['server_url'], allow_local_http=True)
    token,automatic=client_token(base)
    request = Request(base+'/api/config', headers={'User-Agent':'KillingRoomRelay/0.2','Authorization':'Bearer '+token})
    opener=build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            data = json.loads(response.read(8192))
    except HTTPError as exc:
        if exc.code!=401 or not automatic:
            raise ValueError('Serverzugang abgelehnt (HTTP '+str(exc.code)+'). Vorhandenen API-Schluessel pruefen.') from None
        registration=Request(base+'/api/register',data=json.dumps({'name':settings['client'].get('player_name','')}).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+token,'User-Agent':'KillingRoomRelay/0.2'})
        try:
            with opener.open(registration,timeout=10) as response:response.read(8192)
        except HTTPError as error:
            messages={403:'Dieser Server nimmt keine neuen Spieler an oder dein Schluessel wurde gesperrt.',
                      404:'Dieser Server unterstuetzt noch keine automatische Registrierung.',
                      429:'Registrierungslimit erreicht. Spaeter mit demselben Schluessel erneut versuchen.'}
            raise ValueError(messages.get(error.code,'Automatische Registrierung fehlgeschlagen (HTTP '+str(error.code)+').')) from None
        with opener.open(request,timeout=10) as response:
            data=json.loads(response.read(8192))
    if not isinstance(data,dict):
        raise ValueError('Der Server hat keine gueltige Konfiguration geliefert.')
    minimum = data.get('minimum_votes')
    if type(minimum) is not int or not 1 <= minimum <= 127:
        raise ValueError('Der Server hat eine ungueltige Mindeststimmenzahl geliefert.')
    timeout=data.get('connection_timeout_seconds',120)
    if type(timeout) is not int or timeout!=0 and not 5<=timeout<=86400:
        raise ValueError('Der Server hat eine ungueltige Timeout-Einstellung geliefert.')
    return dict(data,minimum_votes=minimum,connection_timeout_seconds=timeout)


def remote_minimum(settings):
    return remote_configuration(settings)['minimum_votes']


def ensure_patch(settings, minimum):
    path = settings['client'].get('game_dll', '')
    if path:
        from patch_game import install
        install(Path(path), minimum)
    elif minimum != 1:
        raise ValueError('Zuerst EINSTELLUNGEN_ANWENDEN.bat ausfuehren und die Spiel-DLL waehlen.')


def api_token():
    return os.environ.get('KR_GAME_API_TOKEN', '')
