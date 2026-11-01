"""Server-side per-player API keys and Discord destinations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import re
import time

ROOT=Path(__file__).resolve().parent


class RegistrationError(ValueError):
    def __init__(self, message, status=403):
        super().__init__(message)
        self.status = status


class ClientRegistry:
    def __init__(self,path=None,legacy_token='',default_minimum=1):
        self.path=Path(path or ROOT/'clients.json')
        self.legacy_token=legacy_token
        self.default_minimum=default_minimum
        self.lock=threading.RLock()
        self.store=None

    def attach_store(self, store):
        self.store=store
        with store.lock, store.db:
            store.db.execute('''CREATE TABLE IF NOT EXISTS registered_clients (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                api_token_sha256 TEXT NOT NULL UNIQUE, created_at REAL NOT NULL)''')
            store.db.execute('CREATE INDEX IF NOT EXISTS client_registration_time ON registered_clients(created_at)')

    def records(self):
        with self.lock:
            registered={}
            if self.store:
                with self.store.lock:
                    registered={r['id']:dict(r) for r in self.store.db.execute('SELECT * FROM registered_clients')}
            data=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'clients':[]}
            records=data.get('clients',[])
            if not isinstance(records,list):raise ValueError('clients.json: clients muss eine Liste sein.')
            seen=set()
            for row in records:
                if not isinstance(row,dict) or not isinstance(row.get('id'),str) or row['id'] in seen:
                    raise ValueError('clients.json: Spieler-ID fehlt oder ist doppelt.')
                seen.add(row['id'])
                value=row.get('api_token_sha256',registered.get(row['id'],{}).get('api_token_sha256',''))
                if row['id']=='legacy' or not re.fullmatch('[0-9a-f]{64}',value):
                    raise ValueError('clients.json: ungueltige Spieler-ID oder Schluessel-Pruefsumme.')
                if type(row.get('enabled',True)) is not bool:
                    raise ValueError('clients.json: enabled muss true oder false sein.')
                n=row.get('minimum_votes',self.default_minimum)
                if type(n) is not int or not 1<=n<=127:raise ValueError('Spieler-Mindeststimmen: 1 bis 127.')
                registered[row['id']]=dict(registered.get(row['id'],{}),**row)
            return list(registered.values())

    def register(self, token, name, limits):
        if not self.store:
            raise RegistrationError('Automatische Registrierung ist nicht verfuegbar.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43,128}',token):
            raise RegistrationError('Ungueltiger automatisch erzeugter Schluessel.',400)
        if not isinstance(name,str) or len(name)>80 or any(ord(c)<32 for c in name):
            raise RegistrationError('Spielername: maximal 80 Zeichen ohne Steuerzeichen.',400)
        digest=hashlib.sha256(token.encode()).hexdigest()
        # Hold both locks throughout the lookup, quota checks and insert. A retry
        # of the same locally saved key must never allocate another identity.
        with self.lock, self.store.lock, self.store.db:
            for row in self.records():
                if secrets.compare_digest(row['api_token_sha256'],digest):
                    if not row.get('enabled',True):
                        raise RegistrationError('Dieser Spielerschluessel wurde gesperrt.')
                    return dict(row,minimum_votes=row.get('minimum_votes',self.default_minimum)),False
            if not limits['enabled']:
                raise RegistrationError('Der Server nimmt derzeit keine neuen Spieler an.')
            now=time.time()
            total=self.store.db.execute('SELECT COUNT(*) FROM registered_clients').fetchone()[0]
            recent=self.store.db.execute('SELECT COUNT(*) FROM registered_clients WHERE created_at>?',(now-3600,)).fetchone()[0]
            if total>=limits['max_clients'] or recent>=limits['per_hour']:
                raise RegistrationError('Registrierungslimit erreicht. Bitte spaeter erneut versuchen.',429)
            client_id='auto_'+secrets.token_hex(8)
            name=name.strip() or 'Spieler '+client_id[-8:]
            self.store.db.execute('INSERT INTO registered_clients VALUES (?,?,?,?)',(client_id,name,digest,now))
            return {'id':client_id,'name':name,'minimum_votes':self.default_minimum},True

    def authenticate(self,authorization):
        if not authorization.startswith('Bearer '):return None
        token=authorization[7:]
        if len(token)<32:return None
        value=hashlib.sha256(token.encode()).hexdigest()
        for row in self.records():
            if row.get('enabled',True) and secrets.compare_digest(row.get('api_token_sha256',''),value):
                return dict(row,minimum_votes=row.get('minimum_votes',self.default_minimum))
        if self.legacy_token and secrets.compare_digest(token,self.legacy_token):
            return {'id':'legacy','name':'Standardspieler','minimum_votes':self.default_minimum}
        return None

    def get(self,client_id):
        return next((r for r in self.records() if r['id']==client_id and r.get('enabled',True)),None)


def main():
    p=argparse.ArgumentParser(description='Eigenen API-Schluessel pro Spieler erzeugen.')
    p.add_argument('name')
    p.add_argument('--minimum-votes',type=int,default=None)
    p.add_argument('--discord-channel',default='')
    p.add_argument('--discord-guild',default='')
    args=p.parse_args()
    if args.minimum_votes is not None and not 1<=args.minimum_votes<=127:p.error('Mindeststimmen: 1 bis 127.')
    for label,value in [('Kanal',args.discord_channel),('Server',args.discord_guild)]:
        if value and not value.isdigit():p.error('Discord-'+label+'-ID muss numerisch sein.')
    path=ROOT/'clients.json'
    data=json.loads(path.read_text()) if path.exists() else {'clients':[]}
    token=secrets.token_urlsafe(48);client_id=secrets.token_hex(8)
    record={'id':client_id,'name':args.name,'enabled':True,
        'api_token_sha256':hashlib.sha256(token.encode()).hexdigest(),
        'discord_channel_id':args.discord_channel,'discord_guild_id':args.discord_guild}
    if args.minimum_votes is not None:record['minimum_votes']=args.minimum_votes
    data['clients'].append(record)
    folder=ROOT/'client_keys';folder.mkdir(exist_ok=True,mode=0o700)
    keyfile=folder/(client_id+'.env')
    fd=os.open(keyfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write('KR_GAME_API_TOKEN='+token+'\n')
    temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');os.replace(temp,path)
    print(f'Spieler angelegt: {args.name} ({client_id}). Schluesseldatei: {keyfile}')
    print('Nur diesem Spieler als settings.env geben. Der API-Schluessel selbst wird nicht angezeigt.')


if __name__=='__main__':main()
