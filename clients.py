"""Server-side per-player API keys and Discord destinations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import re

ROOT=Path(__file__).resolve().parent


class ClientRegistry:
    def __init__(self,path=None,legacy_token='',default_minimum=1):
        self.path=Path(path or ROOT/'clients.json')
        self.legacy_token=legacy_token
        self.default_minimum=default_minimum
        self.lock=threading.RLock()

    def records(self):
        with self.lock:
            data=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'clients':[]}
            records=data.get('clients',[])
            if not isinstance(records,list):raise ValueError('clients.json: clients muss eine Liste sein.')
            seen=set()
            for row in records:
                if not isinstance(row,dict) or not isinstance(row.get('id'),str) or row['id'] in seen:
                    raise ValueError('clients.json: Spieler-ID fehlt oder ist doppelt.')
                seen.add(row['id'])
                if row['id']=='legacy' or not re.fullmatch('[0-9a-f]{64}',row.get('api_token_sha256','')):
                    raise ValueError('clients.json: ungueltige Spieler-ID oder Schluessel-Pruefsumme.')
                n=row.get('minimum_votes',self.default_minimum)
                if type(n) is not int or not 1<=n<=127:raise ValueError('Spieler-Mindeststimmen: 1 bis 127.')
            return records

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
