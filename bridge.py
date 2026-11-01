"""Loopback-only relay from the patched game to an authenticated HTTPS hub."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import secrets
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from config import load_env, load_settings, validate_url, api_token, client_token, remote_configuration, ensure_patch
from presence import game_running
from server import parse_game_form

LOG = logging.getLogger('kr_bridge')
ACTIONS = {'startGame','endGame','newFloor','endFloor','saveBossStat','getBossStat'}
PREFIX = '/reqapi/killingroom/'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class RelayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, base_url, token):
        self.base_url = validate_url(base_url, allow_local_http=True)
        self.token = token
        self.sessions={}
        self.session_lock=threading.RLock()
        self.presence_stop=threading.Event()
        self.presence_thread=None
        super().__init__(address, RelayHandler)

    def heartbeat_cycle(self,executable):
        with self.session_lock:
            if not game_running(executable):
                if self.sessions:LOG.info('Spielprozess beendet; Lebenszeichen werden gestoppt.')
                self.sessions.clear()
                return 0
            sessions=list(self.sessions.items())
        sent=0
        for gid,uid in sessions:
            request=Request(self.base_url+'/api/heartbeat',data=json.dumps({'gid':gid,'uid':uid}).encode(),
                headers={'Content-Type':'application/json','Authorization':'Bearer '+self.token})
            try:
                with build_opener(NoRedirect()).open(request,timeout=8) as response:response.read(8192)
                sent+=1
            except HTTPError as exc:
                if exc.code in (400,401):
                    with self.session_lock:self.sessions.pop(gid,None)
                LOG.warning('Lebenszeichen abgelehnt: HTTP %s.',exc.code)
            except (URLError,OSError):LOG.warning('Lebenszeichen konnte nicht gesendet werden.')
        return sent

    def start_presence(self,executable,timeout):
        if not timeout:return
        def run():
            while not self.presence_stop.wait(min(15,max(1,timeout/3))):
                self.heartbeat_cycle(executable)
        self.presence_thread=threading.Thread(target=run,daemon=True,name='kr-heartbeat')
        self.presence_thread.start()

    def stop_presence(self):
        self.presence_stop.set()
        if self.presence_thread:self.presence_thread.join(timeout=10)


class RelayHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.send_bytes(200, b'Killing Room Relay 0.2 bereit.', 'text/plain; charset=utf-8')

    def do_POST(self):
        path = urlsplit(self.path).path
        if not path.startswith(PREFIX) or path[len(PREFIX):] not in ACTIONS:
            return self.send_bytes(404, b'Nicht gefunden.', 'text/plain')
        try:
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 <= length <= 65536 or self.headers.get('Transfer-Encoding'):
                raise ValueError('Ungueltige Anfragegroesse.')
            self.connection.settimeout(10)
            body = self.rfile.read(length)
            request = Request(self.server.base_url+path, data=body, headers={
                'Content-Type': self.headers.get('Content-Type','application/x-www-form-urlencoded'),
                'Authorization': 'Bearer '+self.server.token,
                'User-Agent': 'KillingRoomRelay/0.2'})
            with build_opener(NoRedirect()).open(request, timeout=10) as response:
                data = response.read(262144)
                fields=parse_game_form(body,self.headers.get('Content-Type',''))
                root=ET.fromstring(data)
                gid=root.findtext('gid') or fields.get('gid')
                if gid and fields.get('uid'):
                    with self.server.session_lock:
                        if path.endswith('/endGame'):
                            self.server.sessions.pop(gid,None)
                        else:
                            if root.findtext('gid'):
                                self.server.sessions={g:u for g,u in self.server.sessions.items() if u!=fields['uid']}
                            self.server.sessions[gid]=fields['uid']
                self.send_bytes(response.status, data, response.headers.get('Content-Type','application/xml'))
        except HTTPError as exc:
            LOG.error('Serverantwort HTTP %s. Bei 401 den API-Schluessel pruefen.', exc.code)
            self.send_bytes(exc.code, b'Fehler bei der Serververbindung.', 'text/plain')
        except (URLError, OSError, ValueError,ET.ParseError):
            LOG.error('Zentraler Server nicht erreichbar oder Konfiguration ungueltig.')
            self.send_bytes(502, b'Zentraler Server nicht erreichbar.', 'text/plain')


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        load_env()
        settings = load_settings()
        base = validate_url(settings['client']['server_url'], allow_local_http=True)
        remote=remote_configuration(settings)
        token,_=client_token(base)
        minimum=remote['minimum_votes']
        ensure_patch(settings, minimum)
        executable=settings['client'].get('game_executable','')
        if remote['connection_timeout_seconds'] and not executable:
            raise ValueError('EINSTELLUNGEN_ANWENDEN.bat ausfuehren oder client.game_executable in settings.json eintragen.')
        server = RelayServer(('127.0.0.1',8765), base, token)
        server.start_presence(executable,remote['connection_timeout_seconds'])
    except (OSError, ValueError, URLError) as exc:
        LOG.error('%s', str(exc).replace(api_token(), '[Schluessel]') if api_token() else str(exc))
        return 1
    LOG.info('Spiel-PC verbunden mit %s; Mindeststimmen: %s. Jetzt Killing Room starten.', base, minimum)
    LOG.info('Spieler-ID: %s. Der API-Schluessel wird lokal gespeichert und automatisch wiederverwendet.',remote.get('client_id','legacy'))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop_presence()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
