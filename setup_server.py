"""Create a server-side secret file locally; never uploads or prints the key."""
import argparse
import os
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description='Server-Konfiguration und API-Schluessel anlegen.')
    p.add_argument('hostname',help='DNS-Name, z.B. vote.example.de')
    args=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?',args.hostname) or '.' not in args.hostname:
        p.error('Einen DNS-Namen ohne https:// und ohne Pfad angeben.')
    file=ROOT/'settings.env'
    if file.exists():
        p.exit(1,'settings.env existiert bereits und bleibt unveraendert.\n')
    for name in ('settings','clients'):
        target=ROOT/(name+'.json')
        if not target.exists():
            target.write_bytes((ROOT/(name+'.example.json')).read_bytes())
    fd=os.open(file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:
        f.write(f'SERVER_HOST={args.hostname}\nKR_GAME_API_TOKEN={secrets.token_urlsafe(48)}\nDISCORD_BOT_TOKEN=\n')
    (ROOT/'seed').mkdir(exist_ok=True)
    print('settings.env und seed/ sind vorbereitet. Schluessel nur lokal in die Client-Konfiguration uebertragen.')


if __name__=='__main__':
    main()
