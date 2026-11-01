"""Exercise automatic credentials over real HTTP and persistent SQLite storage."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clients import ClientRegistry
from config import client_token, load_env, load_settings, remote_configuration
from server import Store, VotingServer
import test_protocol as fixtures


class RegistrationTests(unittest.TestCase):
    setUp=fixtures.ProtocolIntegrationTests.setUp
    tearDown=fixtures.ProtocolIntegrationTests.tearDown
    game=fixtures.ProtocolIntegrationTests.game
    start=fixtures.ProtocolIntegrationTests.start
    open_floor=fixtures.ProtocolIntegrationTests.open_floor
    state=fixtures.ProtocolIntegrationTests.state

    def enable_registration(self):
        self.registry=ClientRegistry(Path(self.temp.name)/'clients.json',default_minimum=3)
        self.registry.attach_store(self.store)
        self.server.registry=self.registry
        self.server.registration={'enabled':True,'per_hour':60,'max_clients':10000}

    def register(self,token,name='Player',extra=None,origin=None):
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token}
        if origin:headers['Origin']=origin
        request=Request(self.base+'/api/register',data=json.dumps(extra if extra is not None else {'name':name}).encode(),headers=headers)
        with build_opener().open(request,timeout=5) as response:
            return response.status,json.load(response)

    def test_two_new_pcs_register_automatically_and_reuse_local_identity(self):
        self.enable_registration()
        env=dict(os.environ,KR_GAME_API_TOKEN='')
        with patch.dict(os.environ,env,clear=True):
            identities=[]
            for pc in ('one','two'):
                root=Path(self.temp.name)/pc;root.mkdir()
                with patch('config.ROOT',root):
                    settings={'client':{'server_url':self.base,'player_name':pc}}
                    first=remote_configuration(settings)
                    key,automatic=client_token(self.base)
                    again=remote_configuration(settings)
                    self.assertTrue(automatic)
                    self.assertEqual(first['client_id'],again['client_id'])
                    self.assertEqual(client_token(self.base)[0],key)
                    self.assertEqual(first['minimum_votes'],3)
                    identities.append((first['client_id'],key))
                    files=list((root/'client_keys').iterdir())
                    self.assertEqual(len(files),1)
                    if os.name!='nt':self.assertEqual(stat.S_IMODE(files[0].stat().st_mode),0o600)
            self.assertNotEqual(identities[0][0],identities[1][0])
            self.assertNotEqual(identities[0][1],identities[1][1])
        self.browser.addheaders=[('Authorization','Bearer '+identities[0][1])]
        gid,token,_=self.start();self.open_floor(gid)
        self.assertEqual(self.state(token)['minimum_votes'],3)
        self.browser.addheaders=[('Authorization','Bearer '+identities[1][1])]
        with self.assertRaises(HTTPError):self.open_floor(gid)
        self.assertEqual(len(self.registry.records()),2)

    def test_concurrent_retries_allocate_one_identity_and_one_quota_slot(self):
        self.enable_registration();self.server.registration['per_hour']=1
        key=secrets.token_urlsafe(48)
        with ThreadPoolExecutor(max_workers=8) as workers:
            results=list(workers.map(lambda _:self.register(key),range(8)))
        self.assertEqual(sum(status==201 for status,_ in results),1)
        self.assertEqual(len({row['client_id'] for _,row in results}),1)
        self.assertEqual(len(self.registry.records()),1)

    def test_hashes_survive_restart_and_raw_keys_are_not_stored(self):
        self.enable_registration();key=secrets.token_urlsafe(48)
        _,result=self.register(key)
        store=Store(self.database,self.base)
        registry=ClientRegistry(Path(self.temp.name)/'clients.json',default_minimum=3)
        try:
            registry.attach_store(store)
            actor=registry.authenticate('Bearer '+key)
            self.assertEqual(actor['id'],result['client_id'])
            with store.lock:dump='\n'.join(store.db.iterdump())
            self.assertNotIn(key,dump)
            self.assertIn(hashlib.sha256(key.encode()).hexdigest(),dump)
            self.assertNotIn(key,json.dumps(result))
        finally:store.close()

    def test_closed_registration_preserves_existing_players(self):
        self.enable_registration();key=secrets.token_urlsafe(48)
        _,first=self.register(key)
        self.server.registration['enabled']=False
        self.assertEqual(self.register(key)[1],first)
        with self.assertRaises(HTTPError) as error:self.register(secrets.token_urlsafe(48))
        self.assertEqual(error.exception.code,403)
        self.assertIsNotNone(self.registry.authenticate('Bearer '+key))

    def test_quota_limits_new_keys_but_never_blocks_retries(self):
        self.enable_registration();self.server.registration['per_hour']=1
        key=secrets.token_urlsafe(48);self.register(key)
        with self.assertRaises(HTTPError) as error:self.register(secrets.token_urlsafe(48))
        self.assertEqual(error.exception.code,429)
        self.assertEqual(self.register(key)[0],200)
        with self.store.lock,self.store.db:self.store.db.execute('UPDATE registered_clients SET created_at=?',(time.time()-3601,))
        self.register(secrets.token_urlsafe(48))
        self.server.registration['max_clients']=2
        with self.assertRaises(HTTPError) as error:self.register(secrets.token_urlsafe(48))
        self.assertEqual(error.exception.code,429)

    def test_operator_can_override_and_revoke_automatic_players(self):
        self.enable_registration();key=secrets.token_urlsafe(48)
        _,first=self.register(key)
        self.registry.path.write_text(json.dumps({'clients':[{'id':first['client_id'],'minimum_votes':7,'discord_channel_id':'123','discord_guild_id':'456'}]}))
        actor=self.registry.authenticate('Bearer '+key)
        self.assertEqual(actor['minimum_votes'],7)
        self.assertEqual(self.registry.get(actor['id'])['discord_channel_id'],'123')
        self.registry.path.write_text(json.dumps({'clients':[{'id':actor['id'],'enabled':False}]}))
        self.assertIsNone(self.registry.authenticate('Bearer '+key))
        with self.assertRaises(HTTPError) as error:self.register(key)
        self.assertEqual(error.exception.code,403)
        self.assertEqual(len(self.registry.records()),1)

    def test_registration_rejects_weak_keys_and_privilege_fields(self):
        self.enable_registration()
        for key,data in [('short',{}),(secrets.token_urlsafe(48),{'name':'x','minimum_votes':1}),
                         (secrets.token_urlsafe(48),{'name':'x','id':'another-player'}),
                         (secrets.token_urlsafe(48),{'name':'x','discord_channel_id':'123'}),
                         (secrets.token_urlsafe(48),{'name':'x'*81})]:
            with self.assertRaises(HTTPError) as error:self.register(key,extra=data)
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error:self.register(secrets.token_urlsafe(48),origin='https://attacker.invalid')
        self.assertEqual(error.exception.code,403)
        self.assertEqual(self.registry.records(),[])

    def test_local_server_does_not_offer_registration(self):
        with self.assertRaises(HTTPError) as error:self.register(secrets.token_urlsafe(48))
        self.assertEqual(error.exception.code,404)

    def test_offline_retry_preserves_key_and_credentials_are_per_server(self):
        self.enable_registration()
        with patch.dict(os.environ,{'KR_GAME_API_TOKEN':''}),patch('config.ROOT',Path(self.temp.name)):
            original=client_token(self.base)[0]
            self.assertNotEqual(original,client_token('https://other.invalid')[0])
            with patch('config.build_opener') as opener:
                opener.return_value.open.side_effect=URLError('offline')
                with self.assertRaises(URLError):remote_configuration({'client':{'server_url':self.base}})
            self.assertEqual(original,client_token(self.base)[0])
            result=remote_configuration({'client':{'server_url':self.base}})
            self.assertEqual(self.registry.authenticate('Bearer '+original)['id'],result['client_id'])

    def test_explicit_keys_still_work_without_allocating_auto_credentials(self):
        self.enable_registration();key=secrets.token_urlsafe(48)
        self.registry.path.write_text(json.dumps({'clients':[{'id':'manual','api_token_sha256':hashlib.sha256(key.encode()).hexdigest()}]}))
        with patch.dict(os.environ,{'KR_GAME_API_TOKEN':key}),patch('config.ROOT',Path(self.temp.name)):
            self.assertEqual(remote_configuration({'client':{'server_url':self.base}})['client_id'],'manual')
            self.assertFalse((Path(self.temp.name)/'client_keys').exists())
        with self.store.lock:self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM registered_clients').fetchone()[0],0)


class FreshServerTests(unittest.TestCase):
    def test_empty_hub_and_separate_client_processes_keep_identity_after_restart(self):
        source=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);hub=root/'hub';hub.mkdir();pc=root/'pc';pc.mkdir()
            for name in ['server.py','config.py','clients.py','presence.py','items.json','setup_server.py',
                         'settings.example.json','clients.example.json']:
                shutil.copyfile(source/name,hub/name)
            shutil.copyfile(source/'config.py',pc/'config.py')
            subprocess.run([sys.executable,str(hub/'setup_server.py'),'vote.example.com'],check=True,capture_output=True)
            self.assertIn('KR_GAME_API_TOKEN=\n',(hub/'settings.env').read_text())
            env=dict(os.environ,KR_MODE='hub',KR_BIND='127.0.0.1',KR_PUBLIC_URL='https://example.invalid',KR_GAME_API_TOKEN='')
            with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
            base='http://127.0.0.1:'+str(port)
            identities=[]
            for restart in range(2):
                process=subprocess.Popen([sys.executable,str(hub/'server.py'),'--port',str(port)],env=env,
                                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                try:
                    deadline=time.monotonic()+8
                    while True:
                        try:
                            with build_opener().open(base+'/api/health',timeout=1) as response:json.load(response)
                            break
                        except OSError:
                            if time.monotonic()>deadline:raise
                            time.sleep(.05)
                    code="import json; from config import load_env,remote_configuration; load_env(); print(json.dumps(remote_configuration({'client':{'server_url':"+repr(base)+"}})))"
                    for _ in range(2):
                        client=subprocess.run([sys.executable,'-c',code],cwd=pc,env=env,capture_output=True,check=True)
                        identities.append(json.loads(client.stdout)['client_id'])
                finally:
                    process.terminate()
                    try:output=process.communicate(timeout=8)[0]
                    except subprocess.TimeoutExpired:process.kill();output=process.communicate()[0]
                    self.assertEqual(process.returncode,0,output.decode(errors='replace'))
            self.assertEqual(len(set(identities)),1)
            self.assertEqual(json.loads((hub/'clients.json').read_text()),{'clients':[]})


if __name__=='__main__':unittest.main()
