"""Install the optional content plugin without changing the game DLL or voting patch."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import tempfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parent
PLUGIN_RELATIVE = Path('BepInEx/plugins/KillingRoomCommunity/KillingRoomCommunity.Content.dll')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def architecture(exe):
    with exe.open('rb') as stream:
        header = stream.read(64)
        if len(header) < 64 or header[:2] != b'MZ':
            raise ValueError('Bitte die Killing-Room-EXE auswaehlen.')
        offset = struct.unpack_from('<I', header, 60)[0]
        if offset > 10_000_000:
            raise ValueError('Ungueltiger PE-Header.')
        stream.seek(offset)
        pe = stream.read(6)
    if len(pe) != 6 or pe[:4] != b'PE\0\0':
        raise ValueError('Keine gueltige Windows-EXE.')
    machine = struct.unpack_from('<H', pe, 4)[0]
    if machine == 0x14c:
        return 'x86'
    if machine == 0x8664:
        return 'x64'
    raise ValueError('Diese Prozessorarchitektur wird nicht unterstuetzt.')


def game_library(exe):
    paths = [exe.parent/(exe.stem+'_Data')/'Managed/Assembly-CSharp.dll']
    paths += sorted(exe.parent.glob('*_Data/Managed/Assembly-CSharp.dll'))
    for path in paths:
        if path.is_file():
            return path
    raise ValueError('Neben der EXE wurde kein Managed-Ordner gefunden.')


def refuse_running_game(exe):
    if os.name != 'nt':
        return
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq '+exe.name, '/FO', 'CSV', '/NH'],
                            capture_output=True, text=True, check=True)
    if '"'+exe.name.lower()+'"' in result.stdout.lower():
        raise ValueError('Killing Room zuerst vollstaendig beenden.')


def download(url):
    # The caller supplies a pinned official release URL and verifies its hash.
    with urlopen(url, timeout=45) as response:
        data = response.read(10_000_001)
    if len(data) > 10_000_000:
        raise ValueError('Unerwartet grosses BepInEx-Paket.')
    return data


def framework_files(data):
    result = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            raw = entry.filename.replace('\\', '/')
            path = PurePosixPath(raw)
            if path.is_absolute() or '..' in path.parts or ':' in raw:
                raise ValueError('Unsicherer Pfad im Runtime-Archiv.')
            if entry.is_dir():
                continue
            # Install only the actual loader files; no archive can replace a
            # game asset, game DLL, unrelated root document or user settings.
            if not (raw.startswith('BepInEx/core/') or raw in ('winhttp.dll', 'doorstop_config.ini', '.doorstop_version')):
                continue
            if entry.file_size > 10_000_000 or entry.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError('Ungueltiger Runtime-Eintrag.')
            result[Path(*path.parts)] = archive.read(entry)
    required = [Path('winhttp.dll'), Path('doorstop_config.ini'), Path('BepInEx/core/BepInEx.dll')]
    if any(path not in result for path in required):
        raise ValueError('Das Runtime-Paket ist unvollstaendig.')
    return result


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='krce_', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def install(exe, package_root=ROOT, downloader=download):
    exe = Path(exe).resolve()
    manifest = json.loads((package_root/'package.json').read_text(encoding='utf-8'))
    library = game_library(exe)
    if sha256(library.read_bytes()) not in manifest['supported_game_hashes']:
        raise ValueError('Unbekannte Spiel-DLL. Es wurde nichts installiert.')
    refuse_running_game(exe)
    arch = architecture(exe)
    plugin = (package_root/'plugin/KillingRoomCommunity.Content.dll').read_bytes()
    if sha256(plugin) != manifest['plugin_sha256']:
        raise ValueError('Die Erweiterungs-DLL hat eine falsche Pruefsumme.')
    runtime = manifest['bepinex'][arch]
    root = exe.parent
    core = root/'BepInEx/core/BepInEx.dll'
    writes = {}
    if core.exists():
        if sha256(core.read_bytes()) != runtime['core_sha256']:
            raise ValueError('Eine andere BepInEx-Version ist vorhanden. Sie bleibt unveraendert. Siehe README zur manuellen Installation.')
        if not (root/'winhttp.dll').is_file() or not (root/'doorstop_config.ini').is_file():
            raise ValueError('Die vorhandene BepInEx-Installation ist unvollstaendig. Loader zuerst reparieren; siehe README.')
    else:
        if (root/'winhttp.dll').exists() or (root/'doorstop_config.ini').exists():
            raise ValueError('Ein anderer Loader ist vorhanden. Er wird nicht ueberschrieben.')
        data = downloader(runtime['url'])
        if sha256(data) != runtime['sha256']:
            raise ValueError('Das heruntergeladene BepInEx-Paket hat eine falsche Pruefsumme.')
        writes = framework_files(data)
        for relative in writes:
            if (root/relative).exists():
                raise ValueError('Vorhandene Runtime-Datei bleibt unveraendert: '+str(relative))
    destination = root/PLUGIN_RELATIVE
    old_plugin = destination.read_bytes() if destination.exists() else None
    if old_plugin is not None and old_plugin != plugin:
        backup = destination.with_suffix('.dll.previous.bak')
        if not backup.exists():
            atomic_write(backup, old_plugin)
    created = []
    try:
        for relative, data in writes.items():
            path = root/relative
            atomic_write(path, data)
            created.append(path)
        atomic_write(destination, plugin)
    except BaseException:
        if old_plugin is not None:
            atomic_write(destination, old_plugin)
        elif destination.exists():
            destination.unlink()
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return destination


def choose_game():
    import tkinter as tk
    from tkinter import filedialog
    window = tk.Tk()
    window.withdraw()
    try:
        name = filedialog.askopenfilename(title='KillingRoom.exe aus dem Spielordner waehlen', filetypes=[('Windows-Spiel', '*.exe')])
    finally:
        window.destroy()
    if not name:
        raise ValueError('Abgebrochen. Es wurde nichts installiert.')
    return Path(name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game-exe', type=Path)
    args = p.parse_args()
    try:
        target = install(args.game_exe or choose_game())
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        p.exit(1, 'Installation abgebrochen: '+str(error)+'\n')
    print('Community Content alpha installiert:', target)
    print('Beim ersten Spielstart wird die Konfiguration unter BepInEx/config angelegt.')
    print('F6 im Hauptmenue: Challenge waehlen. F8: Erweiterungsanzeige ein/aus.')


if __name__ == '__main__':
    main()
