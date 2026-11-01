import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_content', ROOT/'install_content.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game = self.root/'game'; self.game.mkdir()
        self.package = self.root/'package'; (self.package/'plugin').mkdir(parents=True)
        self.exe = self.game/'KillingRoom.exe'
        data = bytearray(256); data[:2] = b'MZ'; struct.pack_into('<I', data, 60, 128)
        data[128:132] = b'PE\0\0'; struct.pack_into('<H', data, 132, 0x14c); self.exe.write_bytes(data)
        managed = self.game/'KillingRoom_Data/Managed'; managed.mkdir(parents=True)
        self.library = managed/'Assembly-CSharp.dll'; self.library.write_bytes(b'game-voting-patch')
        (self.package/'plugin/KillingRoomCommunity.Content.dll').write_bytes(b'content-plugin')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, payload in [('winhttp.dll', b'loader'), ('doorstop_config.ini', b'config'), ('BepInEx/core/BepInEx.dll', b'core')]:
                archive.writestr(name, payload)
        self.runtime = stream.getvalue()
        h = lambda data:hashlib.sha256(data).hexdigest()
        self.manifest = {'supported_game_hashes':[h(self.library.read_bytes())], 'plugin_sha256':h(b'content-plugin'),
                         'bepinex':{'x86':{'url':'https://example.invalid/pinned.zip','sha256':h(self.runtime),'core_sha256':h(b'core')}}}
        self.write_manifest()

    def tearDown(self): self.temp.cleanup()
    def write_manifest(self): (self.package/'package.json').write_text(json.dumps(self.manifest))
    def install(self, data=None): return installer.install(self.exe, self.package, lambda _:self.runtime if data is None else data)

    def test_install_preserves_original_voting_dll_and_is_repeatable(self):
        before = self.library.read_bytes()
        target = self.install()
        self.assertEqual(target.read_bytes(), b'content-plugin')
        self.assertEqual(self.library.read_bytes(), before)
        self.install()
        self.assertEqual(self.library.read_bytes(), before)

    def test_unsupported_game_is_untouched(self):
        self.library.write_bytes(b'unknown')
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.game/'winhttp.dll').exists())

    def test_other_proxy_loader_is_preserved(self):
        (self.game/'winhttp.dll').write_bytes(b'another-mod')
        with self.assertRaises(ValueError): self.install()
        self.assertEqual((self.game/'winhttp.dll').read_bytes(), b'another-mod')

    def test_other_framework_is_not_overwritten(self):
        core = self.game/'BepInEx/core/BepInEx.dll'; core.parent.mkdir(parents=True); core.write_bytes(b'other-framework')
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(core.read_bytes(), b'other-framework')

    def test_partial_existing_framework_requires_repair(self):
        core = self.game/'BepInEx/core/BepInEx.dll'; core.parent.mkdir(parents=True); core.write_bytes(b'core')
        with self.assertRaisesRegex(ValueError, 'unvollstaendig'): self.install()
        self.assertFalse((self.game/installer.PLUGIN_RELATIVE).exists())

    def test_runtime_hash_mismatch_cannot_write_files(self):
        with self.assertRaises(ValueError): self.install(b'corrupt-download')
        self.assertFalse((self.game/'winhttp.dll').exists())

    def test_partial_install_rolls_back_only_its_own_files(self):
        unrelated = self.game/'keep.txt'; unrelated.write_text('keep')
        real = installer.atomic_write
        def fail(path, data):
            if path.name == 'KillingRoomCommunity.Content.dll':raise OSError('simulated disk failure')
            return real(path, data)
        with patch.object(installer, 'atomic_write', side_effect=fail):
            with self.assertRaises(OSError):self.install()
        self.assertFalse((self.game/'winhttp.dll').exists())
        self.assertEqual(unrelated.read_text(), 'keep')

    def test_archive_path_traversal_is_rejected(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('../escape.dll',b'bad')
        with self.assertRaises(ValueError):installer.framework_files(stream.getvalue())

    def test_pe_architecture_is_detected_without_running_the_game(self):
        self.assertEqual(installer.architecture(self.exe),'x86')
        data=bytearray(self.exe.read_bytes());struct.pack_into('<H',data,132,0x8664);self.exe.write_bytes(data)
        self.assertEqual(installer.architecture(self.exe),'x64')


if __name__ == '__main__':unittest.main()
