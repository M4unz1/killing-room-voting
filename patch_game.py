"""Version-bound, reversible Killing Room network patch; Python standard library only."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'patch_manifest.json'
BACKUP_SUFFIX = '.kr-original.bak'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def build_patch(original, minimum_votes=1, manifest=None):
    manifest = manifest or load_manifest()
    if digest(original) != manifest['original_sha256']:
        raise ValueError('Diese DLL passt nicht zur untersuchten Spielversion. Es wurde nichts geaendert.')
    if type(minimum_votes) is not int or not 1 <= minimum_votes <= 127:
        raise ValueError('minimum_votes muss zwischen 1 und 127 liegen.')
    out = bytearray(original)
    changes = list(manifest['changes'])
    threshold = manifest['threshold']
    before = base64.b64decode(threshold['before'], validate=True)
    if minimum_votes <= 8:
        after = bytes([0x16+minimum_votes]) + before[1:]
    else:
        # Replace long bge with short bge, preserving all later instruction offsets.
        after = bytes([0x1f, minimum_votes, 0x2f, threshold['short_branch_distance'], 0, 0])
    changes.append({'name':'minimum_votes', 'offset':threshold['offset'],
                    'before':threshold['before'], 'after':base64.b64encode(after).decode()})
    used = set()
    for entry in changes:
        offset = entry['offset']
        before = base64.b64decode(entry['before'], validate=True)
        after = base64.b64decode(entry['after'], validate=True)
        if len(before) != len(after) or original[offset:offset+len(before)] != before:
            raise ValueError('Pruefung eines Patch-Bereichs fehlgeschlagen: ' + entry['name'])
        positions = set(range(offset, offset+len(before)))
        if positions & used:
            raise ValueError('Ueberlappende Patch-Bereiche.')
        used.update(positions)
        out[offset:offset+len(before)] = after
    result = bytes(out)
    if digest(result) != manifest['patched_sha256'][str(minimum_votes)]:
        raise ValueError('Die Pruefsumme der erstellten DLL stimmt nicht.')
    return result


def write_atomic(path, content):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='kr_patch_', suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def install(path, minimum_votes=1):
    path = Path(path)
    if path.name.lower() != 'assembly-csharp.dll':
        raise ValueError('Bitte die Assembly-CSharp.dll im Managed-Ordner des Spiels auswaehlen.')
    manifest = load_manifest()
    existing = path.read_bytes()
    current_hash = digest(existing)
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    known = set(manifest['patched_sha256'].values())
    if current_hash == manifest['original_sha256']:
        original = existing
        if backup.exists():
            if digest(backup.read_bytes()) != manifest['original_sha256']:
                raise ValueError('Vorhandene Sicherung hat eine andere Pruefsumme. Sie wird nicht ueberschrieben.')
        else:
            with backup.open('xb') as f:
                f.write(original)
                f.flush()
                os.fsync(f.fileno())
    elif current_hash in known:
        if not backup.exists():
            raise ValueError('Patch erkannt, aber die Original-Sicherung fehlt. Keine Aenderung.')
        original = backup.read_bytes()
    else:
        raise ValueError('Andere Spielversion oder bereits anders modifizierte DLL. Keine Aenderung.')
    patched = build_patch(original, minimum_votes, manifest)
    if path.read_bytes() != existing:
        raise ValueError('Die ausgewaehlte Datei wurde inzwischen veraendert. Bitte erneut versuchen.')
    if patched != existing:
        write_atomic(path, patched)
    print('Patch installiert: ' + str(path))
    print('Original gesichert: ' + str(backup))
    print('Benoetigte Stimmen pro Level: ' + str(minimum_votes))
    return path


def restore(path):
    path = Path(path)
    manifest = load_manifest()
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if not backup.exists():
        raise ValueError('Original-Sicherung nicht gefunden: ' + str(backup))
    original = backup.read_bytes()
    if digest(original) != manifest['original_sha256']:
        raise ValueError('Die Original-Sicherung passt nicht zur untersuchten Version.')
    existing = path.read_bytes()
    if digest(existing) not in {manifest['original_sha256'], *manifest['patched_sha256'].values()}:
        raise ValueError('Die aktuelle DLL wurde anderweitig veraendert. Sie wird nicht ueberschrieben.')
    if original != existing:
        write_atomic(path, original)
    print('Original wiederhergestellt: ' + str(path))


def choose_dll():
    try:
        import tkinter as tk
        from tkinter import filedialog
        window = tk.Tk()
        window.withdraw()
        window.attributes('-topmost', True)
        filename = filedialog.askopenfilename(
            title='Assembly-CSharp.dll im Managed-Ordner von Killing Room auswaehlen',
            filetypes=[('Assembly-CSharp.dll', 'Assembly-CSharp.dll'), ('DLL-Dateien', '*.dll')])
        window.destroy()
        if not filename:
            raise ValueError('Abgebrochen. Es wurde nichts geaendert.')
        return Path(filename)
    except ImportError:
        entered = input('Vollstaendiger Pfad zur Assembly-CSharp.dll: ').strip().strip('"')
        if not entered:
            raise ValueError('Abgebrochen.')
        return Path(entered)


def main():
    parser = argparse.ArgumentParser(description='Killing Room: lokalen Voting-Patch installieren oder entfernen.')
    parser.add_argument('source', nargs='?', type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--install', action='store_true')
    action.add_argument('--restore', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--minimum-votes', type=int, default=None)
    parser.add_argument('--settings', action='store_true', help='settings.json lesen und DLL-Pfad speichern')
    args = parser.parse_args()
    try:
        settings = None
        minimum = args.minimum_votes if args.minimum_votes is not None else 1
        if args.settings:
            from config import load_env, load_settings, remote_minimum, save_settings
            load_env()
            settings = load_settings()
            minimum = remote_minimum(settings) if settings['client']['server_url'] else settings['minimum_votes']
        stored_path = settings['client'].get('game_dll') if settings else None
        path = args.source or (Path(stored_path) if stored_path else choose_dll())
        if args.restore:
            restore(path)
        elif args.install:
            install(path, minimum)
            if settings is not None:
                settings['minimum_votes'] = minimum
                settings['client']['game_dll'] = str(path.resolve())
                if not settings['client'].get('game_executable'):
                    from presence import infer_executable
                    settings['client']['game_executable']=infer_executable(path)
                save_settings(settings)
        else:
            output = args.output or path.with_name('Assembly-CSharp.kr-patched.dll')
            if output.resolve() == path.resolve():
                raise ValueError('Fuer eine Installation mit Sicherung --install verwenden.')
            if output.exists():
                raise ValueError('Die Ausgabedatei existiert bereits: ' + str(output))
            write_atomic(output, build_patch(path.read_bytes(), minimum))
            print('Patch-Datei erstellt: ' + str(output))
    except (OSError, ValueError, KeyError) as exc:
        print('FEHLER: ' + str(exc), file=sys.stderr)
        print('Spiel und Steam-Dateipruefung vorher beenden; Original-Sicherung aufbewahren.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
