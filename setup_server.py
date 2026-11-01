"""Prepare the hostname and optional bot secret for the public server."""
import argparse
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description='Server-Konfiguration fuer automatische Spielerregistrierung anlegen.')
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
        f.write(f'SERVER_HOST={args.hostname}\nKR_GAME_API_TOKEN=\nDISCORD_BOT_TOKEN=\n')
    (ROOT/'seed').mkdir(exist_ok=True)
    print('Server vorbereitet. Spiel-PCs registrieren ihren eigenen API-Schluessel automatisch beim ersten Verbinden.')


if __name__=='__main__':
    main()
