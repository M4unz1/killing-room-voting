"""Local replacement for the protocol inspected in the user's Killing Room DLL."""
import argparse
import base64
import hashlib
from email import policy
from email.parser import BytesParser
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
import re
import secrets
import os
import sqlite3
import threading
import time
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
API_PREFIX = '/reqapi/killingroom/'
MAX_BODY = 65536
LOG = logging.getLogger('kr_voting')
VERSION = '0.2'


class ProtocolError(ValueError):
    pass


def client_reply(value):
    """Exact positive-integer arithmetic from HTTP.ModificatedClientRandom."""
    return ((value // 31 + 1) * (value % 17 + 3) * 7) + 71


def server_reply(value):
    return ((value // 53 + 3) * (value % 29 + 1) * 11) + 79


def integer(data, key, default=None, minimum=0, maximum=1000000000):
    raw = data.get(key, default)
    try:
        number = float(raw)
    except (ValueError, TypeError, OverflowError):
        raise ProtocolError('Ungueltiges Zahlenfeld: ' + key) from None
    if not math.isfinite(number) or not number.is_integer() or not minimum <= number <= maximum:
        raise ProtocolError('Ungueltiges Zahlenfeld: ' + key)
    return int(number)


def xml_response(**fields):
    root = ET.Element('response')
    for key, value in fields.items():
        node = ET.SubElement(root, key)
        if isinstance(value, dict):
            for item, count in value.items():
                ET.SubElement(node, 'item', {'name': item}).text = str(count)
        else:
            node.text = str(value)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def parse_game_form(body, content_type):
    if content_type.lower().startswith('application/x-www-form-urlencoded'):
        try:
            fields = parse_qs(body.decode('utf-8'), keep_blank_values=True, max_num_fields=32)
        except (UnicodeDecodeError, ValueError):
            raise ProtocolError('Ungueltiges Formular.') from None
        data_values = fields.get('data', [])
    elif content_type.lower().startswith('multipart/form-data'):
        message = BytesParser(policy=policy.default).parsebytes(
            b'Content-Type: ' + content_type.encode('ascii') + b'\r\nMIME-Version: 1.0\r\n\r\n' + body)
        data_values = []
        if message.is_multipart():
            for part in message.iter_parts():
                if part.get_param('name', header='content-disposition') == 'data':
                    try:
                        data_values.append(part.get_payload(decode=True).decode('utf-8'))
                    except (UnicodeDecodeError, AttributeError):
                        raise ProtocolError('Ungueltiges data-Feld.') from None
    else:
        raise ProtocolError('Erwartet WWWForm als URL-Formular oder Multipart-Formular.')
    if len(data_values) != 1 or not data_values[0].startswith('cr='):
        raise ProtocolError('Klartext-data fehlt. Ist die gepatchte DLL installiert?')
    # The inner game string is NOT URL-encoded. In particular, preserve + in Base64 names.
    raw, separator, steam_name = data_values[0].partition('&steamName=')
    result = {}
    for part in raw.split('&'):
        key, equals, value = part.partition('=')
        if equals and key:
            if key in result:
                raise ProtocolError('Doppeltes Datenfeld: ' + key)
            result[key] = value
    if separator:
        result['steamName'] = steam_name
    return result


def decode_player(data):
    if data.get('name'):
        try:
            name = base64.b64decode(data['name'], validate=True).decode('utf-8')
            return name[:120]
        except (ValueError, UnicodeDecodeError):
            pass
    return data.get('steamName', 'Spieler')[:120] or 'Spieler'


class Store:
    def __init__(self, database, public_url, item_metadata=None, minimum_votes=1, public_stats=True):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(database), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.public_url = public_url.rstrip('/')
        self.item_metadata = item_metadata or {}
        self.minimum_votes = minimum_votes
        self.public_stats = public_stats
        with self.db:
            self.db.executescript('''
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS handshakes (
                    sid TEXT PRIMARY KEY, uid TEXT NOT NULL, sr INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS games (
                    gid TEXT PRIMARY KEY, sid TEXT UNIQUE NOT NULL,
                    uid TEXT NOT NULL, viewer_token TEXT UNIQUE NOT NULL,
                    player TEXT NOT NULL, sr INTEGER NOT NULL,
                    current_round INTEGER, ended INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, gid TEXT NOT NULL,
                    floor INTEGER NOT NULL, items TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(gid) REFERENCES games(gid));
                CREATE TABLE IF NOT EXISTS votes (
                    round_id INTEGER NOT NULL, voter TEXT NOT NULL, item TEXT NOT NULL,
                    PRIMARY KEY(round_id, voter), FOREIGN KEY(round_id) REFERENCES rounds(id));
                CREATE TABLE IF NOT EXISTS boss_events (
                    gid TEXT NOT NULL, boss INTEGER NOT NULL, state TEXT NOT NULL,
                    PRIMARY KEY(gid, boss, state), FOREIGN KEY(gid) REFERENCES games(gid));
                CREATE TABLE IF NOT EXISTS end_floor_replies (
                    gid TEXT NOT NULL, request_key TEXT NOT NULL, round_id INTEGER NOT NULL,
                    PRIMARY KEY(gid, request_key),
                    FOREIGN KEY(gid) REFERENCES games(gid), FOREIGN KEY(round_id) REFERENCES rounds(id));
                CREATE TABLE IF NOT EXISTS discord_messages (
                    round_id INTEGER PRIMARY KEY, channel_id TEXT NOT NULL, message_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL, closed_synced INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(round_id) REFERENCES rounds(id));
            ''')
            for table, column, declaration in [('games','client_id',"TEXT NOT NULL DEFAULT 'legacy'"),
                    ('handshakes','client_id',"TEXT NOT NULL DEFAULT 'legacy'"),
                    ('games','minimum_votes','INTEGER NOT NULL DEFAULT 1'),
                    ('games','last_seen','REAL NOT NULL DEFAULT 0'),('games','end_reason',"TEXT NOT NULL DEFAULT ''")]:
                present={r[1] for r in self.db.execute('PRAGMA table_info('+table+')')}
                if column not in present:self.db.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' '+declaration)
            self.db.execute('UPDATE games SET last_seen=? WHERE last_seen=0 AND ended=0',(time.time(),))
            self.db.execute('CREATE INDEX IF NOT EXISTS active_session_expiry ON games(ended,last_seen)')

    def close(self):
        self.db.close()

    def heartbeat(self,data,client_id='legacy'):
        with self.lock,self.db:
            game=self._game(data,client_id)
            if game['ended']:raise ProtocolError('Sitzung beendet. Bitte eine neue Spielrunde starten.')
            self.db.execute('UPDATE games SET last_seen=? WHERE gid=?',(time.time(),game['gid']))
        return {'ok':True}

    def refresh_local_sessions(self):
        with self.lock,self.db:
            self.db.execute("UPDATE games SET last_seen=? WHERE rowid IN (SELECT MAX(rowid) FROM games WHERE client_id='legacy' AND ended=0 GROUP BY uid)",(time.time(),))

    def expire_sessions(self,timeout,now=None):
        if not timeout:return 0
        cutoff=(time.time() if now is None else now)-timeout
        with self.lock,self.db:
            expired=self.db.execute('SELECT gid FROM games WHERE ended=0 AND last_seen<?',(cutoff,)).fetchall()
            for row in expired:
                self.db.execute("UPDATE games SET ended=1,end_reason='timeout' WHERE gid=?",(row['gid'],))
                self.db.execute('UPDATE rounds SET closed=1 WHERE gid=?',(row['gid'],))
                LOG.info('Spiel %s: Sitzung nach %s Sekunden ohne Lebenszeichen beendet.',row['gid'][:8],timeout)
            return len(expired)

    def statistics(self):
        with self.lock:
            wins = deaths = 0
            bosses = []
            for row in self.db.execute('''SELECT boss,
                    SUM(CASE WHEN state='kill' THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN state='killed' THEN 1 ELSE 0 END) AS deaths
                    FROM boss_events GROUP BY boss ORDER BY boss'''):
                total = row['wins']+row['deaths']
                wins += row['wins']; deaths += row['deaths']
                bosses.append({'boss':row['boss'], 'wins':row['wins'], 'deaths':row['deaths'],
                               'outcomes':total, 'win_percentage':round(100*row['wins']/total,1) if total else None})
            runs = self.db.execute('SELECT COUNT(DISTINCT gid) FROM rounds').fetchone()[0]
            votes = self.db.execute('SELECT COUNT(*) FROM votes').fetchone()[0]
            rounds = self.db.execute('SELECT COUNT(*) FROM rounds').fetchone()[0]
            popular = [{'id':r['item'],'votes':r['n']} for r in self.db.execute(
                'SELECT item,COUNT(*) AS n FROM votes GROUP BY item ORDER BY n DESC,item LIMIT 10')]
            return {'runs':runs,'rounds':rounds,'votes':votes,'boss_wins':wins,'boss_deaths':deaths,
                    'bosses':bosses,'popular_items':popular,'minimum_votes':self.minimum_votes,
                    'scope':'Auf diesem Server erfasste Bossausgaenge; keine historische globale Statistik.'}

    def discord_snapshots(self):
        with self.lock:
            rows = self.db.execute('''SELECT r.*,g.player,g.viewer_token,g.ended,g.current_round,g.client_id,g.minimum_votes,
                    m.channel_id,m.message_id,m.payload_hash,m.closed_synced
                    FROM rounds r JOIN games g ON g.gid=r.gid
                    LEFT JOIN discord_messages m ON m.round_id=r.id
                    WHERE (r.id=g.current_round AND g.ended=0 AND r.closed=0)
                       OR (m.message_id IS NOT NULL AND m.closed_synced=0)
                    ORDER BY r.id''').fetchall()
            snapshots = []
            for row in rows:
                candidates = json.loads(row['items'])
                counts = self._counts(row['id'], candidates)
                active = not bool(row['closed'] or row['ended']) and row['current_round']==row['id']
                items = []
                for index,item in enumerate(dict.fromkeys(candidates)):
                    metadata = self.item_metadata.get(item,{})
                    if isinstance(metadata,str): metadata={'name':metadata}
                    items.append({'id':item,'label':metadata.get('name',item), 'votes':counts[item],
                                  'kind':'good' if candidates.index(item)<2 else 'bad'})
                snapshots.append({'round_id':row['id'],'player':row['player'],'floor':row['floor']+1,
                    'active':active,'items':items,'votesCount':sum(counts.values()),
                    'minimum_votes':row['minimum_votes'],'token':row['viewer_token'],'client_id':row['client_id'],
                    'url':self.public_url+'/v/'+row['viewer_token'],
                    'message_id':row['message_id'],'channel_id':row['channel_id'],
                    'payload_hash':row['payload_hash']})
            return snapshots

    def record_discord_message(self, round_id, channel_id, message_id, payload_hash, closed):
        with self.lock, self.db:
            self.db.execute('''INSERT INTO discord_messages VALUES (?,?,?,?,?)
                ON CONFLICT(round_id) DO UPDATE SET channel_id=excluded.channel_id,
                message_id=excluded.message_id,payload_hash=excluded.payload_hash,closed_synced=excluded.closed_synced''',
                (round_id,str(channel_id),str(message_id),payload_hash,int(closed)))

    def _game(self, data, client_id='legacy'):
        game = self.db.execute('SELECT * FROM games WHERE gid=?', (data.get('gid', ''),)).fetchone()
        if game is None or game['client_id']!=client_id or not secrets.compare_digest(game['uid'], data.get('uid', '')):
            raise ProtocolError('Spielkennung ungueltig. Bitte eine neue Spielrunde starten.')
        return game

    def game_request(self, action, data, client_id='legacy', minimum_votes=None):
        challenge = integer(data, 'cr', minimum=1, maximum=999999)
        uid = data.get('uid', '')
        if not uid or len(uid) > 1024:
            raise ProtocolError('Geraetekennung fehlt.')
        reply = {'cr': client_reply(challenge), 'error': 0}
        with self.lock, self.db:
            if action == 'startGame':
                if not data.get('sid'):
                    sid, sr = secrets.token_hex(16), secrets.randbelow(900000) + 10000
                    self.db.execute('INSERT INTO handshakes(sid,uid,sr,client_id) VALUES (?,?,?,?)', (sid, uid, sr,client_id))
                    return xml_response(**reply, sid=sid, sr=sr)
                startup = self.db.execute('SELECT * FROM handshakes WHERE sid=?', (data['sid'],)).fetchone()
                if startup is None or startup['client_id']!=client_id or not secrets.compare_digest(startup['uid'], uid):
                    raise ProtocolError('Startup-Sitzung ungueltig. Spiel neu starten.')
                game = self.db.execute('SELECT * FROM games WHERE sid=?', (startup['sid'],)).fetchone()
                if game is None:
                    gid, viewer_token = secrets.token_hex(16), secrets.token_urlsafe(24)
                    self.db.execute('INSERT INTO games(gid,sid,uid,viewer_token,player,sr,client_id,minimum_votes,last_seen) VALUES (?,?,?,?,?,?,?,?,?)',
                                    (gid, startup['sid'], uid, viewer_token, decode_player(data), startup['sr'],client_id,
                                     minimum_votes if minimum_votes is not None else self.minimum_votes,time.time()))
                    game = self.db.execute('SELECT * FROM games WHERE gid=?', (gid,)).fetchone()
                    LOG.info('Neue Spielrunde %s; Zuschauerlink: %s/v/%s', gid[:8], self.public_url, viewer_token)
                return xml_response(**reply, sr=game['sr'], gid=game['gid'],
                                    url=self.public_url + '/v/' + game['viewer_token'])

            game = self._game(data,client_id)
            if game['end_reason']=='timeout':
                raise ProtocolError('Verbindung abgelaufen. Bitte eine neue Spielrunde starten.')
            if not game['ended']:
                self.db.execute('UPDATE games SET last_seen=? WHERE gid=?',(time.time(),game['gid']))
            reply['sr'] = game['sr']
            if action == 'newFloor':
                if game['ended']:
                    raise ProtocolError('Diese Spielrunde ist bereits beendet.')
                floor = integer(data, 'floor', maximum=100)
                candidates = data.get('items', '').split(',')
                if not 1 <= len(candidates) <= 4 or any(not x or len(x) > 256 for x in candidates):
                    raise ProtocolError('Ein bis vier gueltige Item-Kennungen erwartet.')
                encoded = json.dumps(candidates, ensure_ascii=False)
                current = self.db.execute('SELECT * FROM rounds WHERE id=?', (game['current_round'],)).fetchone()
                if current is not None and current['floor'] > floor:
                    raise ProtocolError('Veraltete Level-Anfrage.')
                if current is None or current['floor'] != floor or current['items'] != encoded:
                    if current is not None:
                        self.db.execute('UPDATE rounds SET closed=1 WHERE id=?', (current['id'],))
                    cursor = self.db.execute('INSERT INTO rounds(gid,floor,items) VALUES (?,?,?)',
                                             (game['gid'], floor, encoded))
                    self.db.execute('UPDATE games SET current_round=? WHERE gid=?', (cursor.lastrowid, game['gid']))
                    LOG.info('Spiel %s: Level %s, %s Kandidaten, Abstimmung offen.', game['gid'][:8], floor+1, len(candidates))
                return xml_response(**reply)

            if action == 'endFloor':
                floor = integer(data, 'floor', maximum=100)
                # CalculateFinishLevel advances actualFloor BEFORE the voting UI.
                # Its final-floor clamp can also leave the value unchanged.
                # Resolve against the current candidate round, not an exact floor
                # lookup; bind each request so a late retry cannot close a newer round.
                identity = json.dumps({'cr':challenge, 'floor':floor, 'sr':data.get('sr','')},
                                      sort_keys=True, separators=(',', ':'))
                request_key = hashlib.sha256(identity.encode('utf-8')).hexdigest()
                bound = self.db.execute('SELECT round_id FROM end_floor_replies WHERE gid=? AND request_key=?',
                                        (game['gid'], request_key)).fetchone()
                round_id = bound['round_id'] if bound is not None else game['current_round']
                current = self.db.execute('SELECT * FROM rounds WHERE gid=? AND id=?',
                                          (game['gid'], round_id)).fetchone()
                if bound is None and current is not None and floor not in (current['floor'], current['floor']+1):
                    current = None
                counts = {}
                if current is not None:
                    self.db.execute('UPDATE rounds SET closed=1 WHERE id=?', (current['id'],))
                    self.db.execute('INSERT OR IGNORE INTO end_floor_replies VALUES (?,?,?)',
                                    (game['gid'], request_key, current['id']))
                    counts = self._counts(current['id'], json.loads(current['items']))
                    LOG.info('Spiel %s: Level %s ausgewertet, %s Stimmen (endFloor=%s, Abstimmung=%s).',
                             game['gid'][:8], current['floor']+1, sum(counts.values()), floor, current['id'])
                else:
                    LOG.warning('Spiel %s: Auswertung ohne passende Abstimmung (endFloor=%s).',
                                game['gid'][:8], floor)
                total = sum(counts.values())
                return xml_response(**reply, votesCount=total, votes=counts)

            if action == 'saveBossStat':
                boss = integer(data, 'boss', maximum=100)
                state = data.get('bossState')
                if state not in ('kill', 'killed'):
                    raise ProtocolError('Ungueltiger Boss-Status.')
                self.db.execute('INSERT OR IGNORE INTO boss_events VALUES (?,?,?)', (game['gid'], boss, state))
                return xml_response(**reply)

            if action == 'getBossStat':
                boss = integer(data, 'boss', maximum=100)
                rows = self.db.execute('SELECT state,COUNT(*) AS n FROM boss_events WHERE boss=? GROUP BY state', (boss,))
                counts = {row['state']: row['n'] for row in rows}
                return xml_response(**reply, bossKill=counts.get('kill', 0), bossKilled=counts.get('killed', 0))

            if action == 'endGame':
                self.db.execute('UPDATE games SET ended=1 WHERE gid=?', (game['gid'],))
                self.db.execute('UPDATE rounds SET closed=1 WHERE gid=?', (game['gid'],))
                return xml_response(**reply, votesCount=0, votes={})
            raise ProtocolError('Unbekannter Spiel-Endpunkt.')

    def _counts(self, round_id, items):
        counts = dict.fromkeys(items, 0)
        for row in self.db.execute('SELECT item,COUNT(*) AS n FROM votes WHERE round_id=? GROUP BY item', (round_id,)):
            if row['item'] in counts:
                counts[row['item']] = row['n']
        return counts

    def view(self, token, voter):
        with self.lock:
            game = self.db.execute('SELECT * FROM games WHERE viewer_token=?', (token,)).fetchone()
            if game is None:
                raise ProtocolError('Zuschauerlink nicht gefunden.')
            current = self.db.execute('SELECT * FROM rounds WHERE id=?', (game['current_round'],)).fetchone()
            result = {'player': game['player'], 'ended': bool(game['ended']), 'end_reason':game['end_reason'],'round_id': None,
                      'floor': None, 'active': False, 'items': [], 'votesCount': 0, 'choice': None,
                      'minimum_votes':game['minimum_votes']}
            if current is not None:
                candidates = json.loads(current['items'])
                counts = self._counts(current['id'], candidates)
                result.update(round_id=current['id'], floor=current['floor']+1,
                              active=not bool(current['closed'] or game['ended']), votesCount=sum(counts.values()))
                seen = set()
                for index, item in enumerate(candidates):
                    if item in seen:
                        continue
                    seen.add(item)
                    metadata = self.item_metadata.get(item, {})
                    if isinstance(metadata, str):
                        metadata = {'name': metadata}
                    result['items'].append({'id': item, 'label': metadata.get('name', item),
                                            'description': metadata.get('description', ''),
                                            'kind': 'good' if index < 2 else 'bad', 'votes': counts[item]})
                vote = self.db.execute('SELECT item FROM votes WHERE round_id=? AND voter=?', (current['id'], voter)).fetchone()
                result['choice'] = vote['item'] if vote else None
            return result

    def vote(self, token, voter, round_id, item):
        with self.lock, self.db:
            game = self.db.execute('SELECT * FROM games WHERE viewer_token=?', (token,)).fetchone()
            if game is None or game['ended'] or game['current_round'] != round_id:
                raise ProtocolError('Diese Abstimmung ist nicht mehr aktuell.')
            current = self.db.execute('SELECT * FROM rounds WHERE id=?', (round_id,)).fetchone()
            if current is None or current['closed'] or item not in json.loads(current['items']):
                raise ProtocolError('Diese Auswahl ist nicht mehr verfuegbar.')
            self.db.execute('INSERT INTO votes VALUES (?,?,?) ON CONFLICT(round_id,voter) DO UPDATE SET item=excluded.item',
                            (round_id, voter, item))
            result = self.view(token, voter)
            LOG.info('Spiel %s: Stimme gespeichert, Level %s, insgesamt %s Stimmen (Abstimmung=%s).',
                     game['gid'][:8], current['floor']+1, result['votesCount'], round_id)
            return result


class VotingServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store, game_api_token='', registry=None, connection_timeout=120):
        self.store = store
        self.game_api_token = game_api_token
        self.registry = registry
        self.connection_timeout=connection_timeout
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = 'KillingRoomVoting/0.2'

    def log_message(self, fmt, *args):
        # Log useful protocol events in Store; do not record raw device IDs or request bodies.
        if len(args) > 1 and str(args[1]).startswith(('4', '5')):
            LOG.warning('HTTP %s fuer %s', args[1], urlsplit(self.path).path[:180])

    def _send(self, status, body, content_type, cookie=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        if status != 204:
            self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status, obj, cookie=None):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8', cookie)

    def _body(self):
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            raise ProtocolError('Content-Length fehlt.') from None
        if not 0 <= length <= MAX_BODY or self.headers.get('Transfer-Encoding'):
            raise ProtocolError('Anfrage zu gross oder ungueltig.')
        self.connection.settimeout(10)
        return self.rfile.read(length)

    def _voter(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
        except cookies.CookieError:
            jar = cookies.SimpleCookie()
        value = jar['kr_viewer'].value if 'kr_viewer' in jar else ''
        if re.fullmatch('[0-9a-f]{32}', value):
            return value, None
        value = secrets.token_hex(16)
        cookie = f'kr_viewer={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000'
        if self.server.store.public_url.startswith('https://'):
            cookie += '; Secure'
        return value, cookie

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ('/', '/index.html') or re.fullmatch('/v/[A-Za-z0-9_-]{20,64}', path):
            self._send(200, (ROOT/'web/index.html').read_bytes(), 'text/html; charset=utf-8')
        elif path == '/stats':
            if not self.server.store.public_stats:
                return self._json(404, {'error':'Statistiken sind privat.'})
            self._send(200, (ROOT/'web/stats.html').read_bytes(), 'text/html; charset=utf-8')
        elif path in ('/app.js', '/style.css', '/stats.js'):
            mime = 'text/javascript' if path.endswith('.js') else 'text/css'
            self._send(200, (ROOT/'web'/path[1:]).read_bytes(), mime+'; charset=utf-8')
        elif path == '/api/health':
            self._json(200, {'ok': True, 'version': VERSION})
        elif path == '/api/config':
            actor=self.server.registry.authenticate(self.headers.get('Authorization','')) if self.server.registry else None
            if self.headers.get('Authorization') and self.server.registry and actor is None:
                return self._json(401, {'error':'Ungueltiger API-Schluessel.'})
            minimum=actor['minimum_votes'] if actor else self.server.store.minimum_votes
            self._json(200, {'version':VERSION,'minimum_votes':minimum,'connection_timeout_seconds':self.server.connection_timeout})
        elif path == '/api/stats':
            if not self.server.store.public_stats:
                return self._json(404, {'error':'Statistiken sind privat.'})
            self._json(200, self.server.store.statistics())
        elif path == '/favicon.ico':
            self._send(204, b'', 'image/x-icon')
        elif re.fullmatch('/api/v/[A-Za-z0-9_-]{20,64}', path):
            voter, cookie = self._voter()
            try:
                self._json(200, self.server.store.view(path.rsplit('/', 1)[1], voter), cookie)
            except ProtocolError as exc:
                self._json(404, {'error': str(exc)}, cookie)
        else:
            self._json(404, {'error': 'Nicht gefunden.'})

    def do_POST(self):
        path = urlsplit(self.path).path.rstrip('/')
        try:
            if path=='/api/heartbeat':
                authorization=self.headers.get('Authorization','')
                actor=self.server.registry.authenticate(authorization) if self.server.registry else None
                if self.server.registry and actor is None or not self.server.registry and self.server.game_api_token and not secrets.compare_digest(authorization,'Bearer '+self.server.game_api_token):
                    return self._json(401,{'error':'Spiel-API-Schluessel erforderlich.'})
                data=json.loads(self._body())
                if not isinstance(data,dict) or not isinstance(data.get('gid'),str) or not isinstance(data.get('uid'),str):
                    raise ProtocolError('Ungueltiges Lebenszeichen.')
                return self._json(200,self.server.store.heartbeat(data,actor['id'] if actor else 'legacy'))
            if path.startswith(API_PREFIX):
                expected = self.server.game_api_token
                authorization = self.headers.get('Authorization','')
                actor=self.server.registry.authenticate(authorization) if self.server.registry else None
                if self.server.registry and actor is None or not self.server.registry and expected and not secrets.compare_digest(authorization, 'Bearer '+expected):
                    return self._json(401, {'error':'Spiel-API-Schluessel erforderlich.'})
                action = path[len(API_PREFIX):]
                if action not in {'startGame', 'endGame', 'newFloor', 'endFloor', 'saveBossStat', 'getBossStat'}:
                    return self._json(404, {'error': 'Unbekannter Spiel-Endpunkt.'})
                data = parse_game_form(self._body(), self.headers.get('Content-Type', ''))
                result = self.server.store.game_request(action,data,client_id=actor['id'] if actor else 'legacy',
                             minimum_votes=actor['minimum_votes'] if actor else None)
                return self._send(200, result, 'application/xml; charset=utf-8')
            if re.fullmatch('/api/v/[A-Za-z0-9_-]{20,64}', path):
                if self.headers.get('Content-Type', '').split(';',1)[0].strip().lower() != 'application/json':
                    raise ProtocolError('JSON erwartet.')
                origin = self.headers.get('Origin')
                allowed = {self.server.store.public_url, 'http://' + self.headers.get('Host', '')}
                if origin and origin not in allowed:
                    return self._json(403, {'error': 'Ungueltiger Ursprung.'})
                data = json.loads(self._body())
                if not isinstance(data, dict) or not isinstance(data.get('round_id'), int) or not isinstance(data.get('item'), str):
                    raise ProtocolError('Ungueltige Auswahl.')
                voter, cookie = self._voter()
                result = self.server.store.vote(path.rsplit('/', 1)[1], voter, data['round_id'], data['item'])
                return self._json(200, result, cookie)
            self._json(404, {'error': 'Nicht gefunden.'})
        except (ProtocolError, ValueError, UnicodeDecodeError) as exc:
            LOG.warning('Anfrage abgelehnt: %s', str(exc)[:200])
            self._json(400, {'error': str(exc)})
        except (TimeoutError, ConnectionError):
            LOG.warning('Anfrage abgebrochen oder Zeitlimit erreicht.')
        except sqlite3.Error:
            LOG.exception('Datenbankfehler')
            self._json(500, {'error': 'Interner Datenbankfehler. Siehe kr_voting.log.'})


def main():
    from config import load_env, load_settings, api_token, ensure_patch, validate_url
    load_env()
    settings = load_settings()
    parser = argparse.ArgumentParser(description='Killing Room Voting 0.2: lokal oder zentraler Server.')
    parser.add_argument('--bind', default=None)
    parser.add_argument('--port', type=int, default=None)
    parser.add_argument('--database', type=Path, default=None)
    parser.add_argument('--public-url', default=None)
    args = parser.parse_args()
    mode = settings['server']['mode']
    bind = args.bind or settings['server']['bind']
    port = args.port or settings['server']['port']
    public_url = args.public_url or settings['server']['public_url'] or f'http://127.0.0.1:{port}'
    public_url = validate_url(public_url, allow_local_http=mode=='local')
    token = api_token() if mode=='hub' else ''
    if token.startswith('HIER_') or len(token)<32:
        token=''
    from clients import ClientRegistry
    registry=ClientRegistry(legacy_token=token,default_minimum=settings['minimum_votes']) if mode=='hub' else None
    if mode=='hub' and not registry.records() and not token:
        parser.error('Im Hub-Modus mindestens einen Spielerschluessel mit clients.py anlegen.')
    if mode=='local':
        ensure_patch(settings,settings['minimum_votes'])
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', handlers=[
        logging.StreamHandler(), RotatingFileHandler(ROOT/'kr_voting.log', maxBytes=2000000, backupCount=2, encoding='utf-8')])
    metadata = json.loads((ROOT/'items.json').read_text(encoding='utf-8'))
    database = args.database or Path(os.environ.get('KR_DATABASE_PATH',str(ROOT/'kr_voting.sqlite3')))
    seed=Path(os.environ.get('KR_SEED_PATH','/nonexistent'))
    if not database.exists() and seed.is_file():
        source=sqlite3.connect('file:'+str(seed)+'?mode=ro',uri=True)
        target=sqlite3.connect(str(database))
        try:source.backup(target)
        finally:source.close();target.close()
    store = Store(database,public_url,metadata,settings['minimum_votes'],settings['stats']['public'])
    bot = None
    try:
        server = VotingServer((bind,port),store,game_api_token=token,registry=registry,
                              connection_timeout=settings['connection_timeout_seconds'])
        if settings['discord']['enabled']:
            from discord_bot import DiscordRunner
            bot = DiscordRunner(store,os.environ.get('DISCORD_BOT_TOKEN',''),
                                settings['discord']['channel_id'],settings['discord']['guild_id'],registry)
            bot.start()
    except (OSError,ValueError,ImportError) as exc:
        store.close()
        parser.exit(1,f'Serverstart fehlgeschlagen: {exc}\n')
    stop_cleanup=threading.Event()
    def cleanup():
        from presence import game_running
        timeout=settings['connection_timeout_seconds']
        executable=settings['client'].get('game_executable','')
        if not timeout:return
        while not stop_cleanup.wait(min(5,max(1,timeout/4))):
            if mode=='local':
                if not executable:continue
                if game_running(executable):store.refresh_local_sessions()
            store.expire_sessions(timeout)
    cleanup_thread=threading.Thread(target=cleanup,daemon=True,name='kr-cleanup')
    cleanup_thread.start()
    LOG.info('Killing Room Voting %s bereit: %s; Mindeststimmen: %s',VERSION,public_url,store.minimum_votes)
    LOG.info('Statistiken: %s/stats; Modus: %s',public_url,mode)
    import signal
    def stop(signum,frame):
        raise KeyboardInterrupt
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM,stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_cleanup.set()
        cleanup_thread.join(timeout=6)
        server.server_close()
        if bot:
            bot.stop()
        store.close()


if __name__ == '__main__':
    main()
