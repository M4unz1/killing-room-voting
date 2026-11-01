"""Package the compiled community plugin. Never include game assemblies."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '0.1.0-alpha'
CORE_SHA256 = '780f175821781c14fdc349bf214603b7bab594ac556aecb1f6679b80248133f0'
RUNTIME_SHA256 = {
    'x86': 'a4024dafaca5d3784097e34b3c2921415030c0b461e52f30053ed8914be9622d',
    'x64': '6c57a714a892efb4e9e1fef63d608a3391f30ec984031c465404e4ee381a0755',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package(output):
    plugin = (ROOT/'build/KillingRoomCommunity.Content.dll').read_bytes()
    voting = json.loads((ROOT.parent/'patch_manifest.json').read_text(encoding='utf-8'))
    hashes = sorted({voting['original_sha256'], *voting['patched_sha256'].values()})
    embedded = set(re.findall(r'"([0-9a-f]{64})"', (ROOT/'BuildInfo.cs').read_text()))
    if set(hashes) != embedded:
        raise ValueError('BuildInfo.cs and voting patch support differ. Rebuild after updating both.')
    manifest = {
        'version': VERSION,
        'plugin_sha256': digest(plugin),
        'supported_game_hashes': hashes,
        'bepinex': {
            arch: {
                'version': '5.4.23.6',
                'url': 'https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.6/BepInEx_win_'+arch+'_5.4.23.6.zip',
                'sha256': runtime_hash,
                'core_sha256': CORE_SHA256,
            } for arch, runtime_hash in RUNTIME_SHA256.items()
        },
    }
    entries = {'plugin/KillingRoomCommunity.Content.dll': plugin,
               'package.json': (json.dumps(manifest, indent=2)+'\n').encode('utf-8')}
    for name in ['INSTALLIEREN.bat', 'install_content.py', 'README.md', 'README.en.md',
                 'content-metadata.json', 'VERIFICATION.json']:
        entries[name] = (ROOT/name).read_bytes()
    entries['CHECKSUMS.sha256'] = ''.join(digest(data)+'  '+name+'\n'
                                        for name, data in sorted(entries.items())).encode('ascii')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo('KillingRoom_Community_Content/'+name, (2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return {'path': str(output), 'bytes': output.stat().st_size, 'sha256': digest(output.read_bytes()),
            'plugin_sha256': digest(plugin), 'supported_game_hashes': len(hashes)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.output.resolve()), indent=2))
