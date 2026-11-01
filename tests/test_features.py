import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.cookiejar
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import os
import shutil
import socket
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Store
from clients import ClientRegistry
from config import load_settings, remote_minimum
from bridge import RelayServer
import test_protocol as fixtures


class FeatureTests(unittest.TestCase):
    setUp=fixtures.ProtocolIntegrationTests.setUp
    tearDown=fixtures.ProtocolIntegrationTests.tearDown
    game=fixtures.ProtocolIntegrationTests.game
    start=fixtures.ProtocolIntegrationTests.start
    state=fixtures.ProtocolIntegrationTests.state
    vote=fixtures.ProtocolIntegrationTests.vote
    open_floor=fixtures.ProtocolIntegrationTests.open_floor
    finish_floor=fixtures.ProtocolIntegrationTests.finish_floor

    def enable_registry(self):
        self.keys={'one':'a'*64,'two':'b'*64}
        rows=[{'id':name,'name':name,'enabled':True,'minimum_votes':3 if name=='one' else 7,
               'api_token_sha256':hashlib.sha256(key.encode()).hexdigest(),
               'discord_channel_id':'101' if name=='one' else '102','discord_guild_id':'201'}
              for name,key in self.keys.items()]
        path=Path(self.temp.name)/'clients.json';path.write_text(json.dumps({'clients':rows}))
        self.server.registry=ClientRegistry(path)
        self.actor('one')

    def actor(self,which):
        self.browser.addheaders=[('Authorization','Bearer '+self.keys[which])]

    def test_auth_owner_isolation_and_per_player_minimum(self):
        self.enable_registry()
        gid_a,token_a,_=self.start(player='One')
        self.open_floor(gid_a)
        self.assertEqual(self.state(token_a)['minimum_votes'],3)
        self.actor('two')
        gid_b,token_b,_=self.start(player='Two')
        self.open_floor(gid_b)
        self.assertEqual(self.state(token_b)['minimum_votes'],7)
        with self.assertRaises(HTTPError):self.open_floor(gid_a)
        self.assertTrue(self.state(token_a)['active'])
        with patch.dict('os.environ',{'KR_GAME_API_TOKEN':self.keys['two']}):
            self.assertEqual(remote_minimum({'client':{'server_url':self.base}}),7)
        request=Request(self.base+'/reqapi/killingroom/startGame',data=urlencode({'data':'cr=1&uid=test'}).encode(),
                        headers={'Content-Type':'application/x-www-form-urlencoded'})
        with self.assertRaises(HTTPError) as error:build_opener().open(request)
        self.assertEqual(error.exception.code,401)

    def test_concurrent_players_votes_do_not_mix(self):
        self.enable_registry();a,ta,_=self.start();self.open_floor(a)
        ra=self.state(ta)['round_id']
        self.actor('two');b,tb,_=self.start();self.open_floor(b)
        rb=self.state(tb)['round_id']
        def visitor(args):
            token,rid,item=args
            browser=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
            self.state(token,browser)
            return self.vote(token,rid,item,browser)
        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(visitor,[(ta,ra,'good1')]*8+[(tb,rb,'bad2')]*8))
        self.assertEqual(self.state(ta)['votesCount'],8)
        self.assertEqual(self.state(tb)['votesCount'],8)
        end_b=self.finish_floor(b)
        self.assertEqual(end_b.find('votes/item[@name="bad2"]').text,'8')
        self.assertEqual(end_b.find('votes/item[@name="good1"]').text,'0')
        self.actor('one');end_a=self.finish_floor(a)
        self.assertEqual(end_a.find('votes/item[@name="good1"]').text,'8')

    def test_community_boss_rates_and_public_data_scope(self):
        self.enable_registry();a,ta,_=self.start();self.open_floor(a)
        for _ in range(2):self.game('saveBossStat',{'cr':11,'uid':'test-device','gid':a,'sr':0,'boss':1,'bossState':'kill'})
        self.actor('two');b,tb,_=self.start();self.open_floor(b)
        self.game('saveBossStat',{'cr':12,'uid':'test-device','gid':b,'sr':0,'boss':1,'bossState':'killed'})
        original=self.game('getBossStat',{'cr':13,'uid':'test-device','gid':b,'sr':0,'boss':1})
        self.assertEqual(original.findtext('bossKill'),'1');self.assertEqual(original.findtext('bossKilled'),'1')
        with self.browser.open(self.base+'/api/stats') as response:stats=json.load(response)
        self.assertEqual(stats['bosses'][0]['win_percentage'],50.0)
        self.assertEqual(stats['bosses'][0]['outcomes'],2)
        encoded=json.dumps(stats)
        for private in [a,b,ta,tb,'test-device',*self.keys.values()]:self.assertNotIn(private,encoded)
        self.server.store.public_stats=False
        with self.assertRaises(HTTPError):self.browser.open(self.base+'/api/stats')

    def test_relay_forwards_authenticated_game_protocol(self):
        self.enable_registry()
        hub=self.base
        relay=RelayServer(('127.0.0.1',0),hub,self.keys['one'])
        thread=threading.Thread(target=relay.serve_forever,daemon=True);thread.start()
        try:
            self.browser.addheaders=[]
            self.base='http://127.0.0.1:'+str(relay.server_port)
            gid,token,_=self.start(multipart=True)
            self.open_floor(gid)
            self.base=hub
            view=self.state(token)
            self.assertEqual(view['minimum_votes'],3)
            self.vote(token,view['round_id'],'good1')
            self.base='http://127.0.0.1:'+str(relay.server_port)
            end=self.finish_floor(gid)
            self.assertEqual(end.findtext('votesCount'),'1')
        finally:
            self.base=hub;relay.shutdown();thread.join();relay.server_close()

    def test_discord_persistence_rows_are_separate_per_player(self):
        self.enable_registry();a,ta,_=self.start();self.open_floor(a)
        self.actor('two');b,tb,_=self.start();self.open_floor(b)
        snapshots=self.store.discord_snapshots()
        self.assertEqual({s['client_id'] for s in snapshots},{'one','two'})
        for snap in snapshots:self.store.record_discord_message(snap['round_id'],'101','987'+str(snap['round_id']),'stamp',False)
        self.assertEqual(len([s for s in self.store.discord_snapshots() if s['message_id']]),2)

    def test_timeout_expires_one_player_and_preserves_statistics(self):
        self.enable_registry();a,ta,_=self.start();self.open_floor(a)
        ra=self.state(ta)['round_id'];self.vote(ta,ra,'good1')
        self.game('saveBossStat',{'cr':14,'uid':'test-device','gid':a,'sr':0,'boss':1,'bossState':'kill'})
        self.actor('two');b,tb,_=self.start();self.open_floor(b)
        now=time.time()
        with self.store.lock,self.store.db:
            self.store.db.execute('UPDATE games SET last_seen=? WHERE gid=?',(now-121,a))
            self.store.db.execute('UPDATE games SET last_seen=? WHERE gid=?',(now,b))
        self.assertEqual(self.store.expire_sessions(120,now),1)
        self.assertTrue(self.state(ta)['ended']);self.assertEqual(self.state(ta)['end_reason'],'timeout')
        self.assertFalse(self.state(tb)['ended'])
        self.assertEqual(self.store.statistics()['boss_wins'],1)
        self.assertEqual(self.store.statistics()['votes'],1)
        with self.assertRaises(HTTPError):self.vote(ta,ra,'good2')

    def test_heartbeat_is_owner_scoped(self):
        self.enable_registry();gid,token,_=self.start();self.open_floor(gid)
        def heartbeat(browser=None):
            request=Request(self.base+'/api/heartbeat',data=json.dumps({'gid':gid,'uid':'test-device'}).encode(),headers={'Content-Type':'application/json'})
            with (browser or self.browser).open(request) as response:return json.load(response)
        with self.assertRaises(HTTPError):heartbeat(build_opener())
        self.actor('two')
        with self.assertRaises(HTTPError):heartbeat()
        self.actor('one')
        with self.store.lock,self.store.db:self.store.db.execute('UPDATE games SET last_seen=1 WHERE gid=?',(gid,))
        self.assertTrue(heartbeat()['ok'])
        self.assertEqual(self.store.expire_sessions(120),0)

    def test_relay_stops_heartbeats_when_game_exits(self):
        self.enable_registry();gid,token,_=self.start();self.open_floor(gid)
        relay=RelayServer(('127.0.0.1',0),self.base,self.keys['one'])
        try:
            relay.sessions[gid]='test-device'
            with patch('bridge.game_running',return_value=True):self.assertEqual(relay.heartbeat_cycle('game.exe'),1)
            with patch('bridge.game_running',return_value=False):self.assertEqual(relay.heartbeat_cycle('game.exe'),0)
            self.assertEqual(relay.sessions,{})
            self.assertEqual(self.store.expire_sessions(0,now=time.time()+10000),0)
        finally:relay.server_close()


class ConfigurationTests(unittest.TestCase):
    def test_minimum_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'settings.json'
            for n in [0,128,True,'3']:
                path.write_text(json.dumps({'minimum_votes':n}))
                with self.assertRaises(ValueError):load_settings(path)
            path.write_text(json.dumps({'minimum_votes':25}))
            self.assertEqual(load_settings(path)['minimum_votes'],25)
            for timeout in [True,-1,4,86401]:
                path.write_text(json.dumps({'connection_timeout_seconds':timeout}))
                with self.assertRaises(ValueError):load_settings(path)
            path.write_text(json.dumps({'connection_timeout_seconds':0}))
            self.assertEqual(load_settings(path)['connection_timeout_seconds'],0)

    def test_legacy_database_migrates_without_losing_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.sqlite3'
            db=sqlite3.connect(path)
            db.executescript('''
                CREATE TABLE handshakes(sid TEXT PRIMARY KEY,uid TEXT,sr INTEGER);
                CREATE TABLE games(gid TEXT PRIMARY KEY,sid TEXT,uid TEXT,viewer_token TEXT,player TEXT,sr INTEGER,current_round INTEGER,ended INTEGER);
                CREATE TABLE rounds(id INTEGER PRIMARY KEY,gid TEXT,floor INTEGER,items TEXT,closed INTEGER);
                CREATE TABLE votes(round_id INTEGER,voter TEXT,item TEXT,PRIMARY KEY(round_id,voter));
                CREATE TABLE boss_events(gid TEXT,boss INTEGER,state TEXT,PRIMARY KEY(gid,boss,state));
                INSERT INTO handshakes VALUES('sid','uid',100);
                INSERT INTO games VALUES('gid','sid','uid','viewer','Player',100,1,0);
                INSERT INTO rounds VALUES(1,'gid',0,'["good"]',0);
                INSERT INTO votes VALUES(1,'voter','good');
                INSERT INTO boss_events VALUES('gid',1,'kill');
            ''');db.close()
            store=Store(path,'http://127.0.0.1:8765')
            try:
                self.assertEqual(store.view('viewer','voter')['votesCount'],1)
                self.assertEqual(store.statistics()['bosses'][0]['wins'],1)
                self.assertEqual(store.discord_snapshots()[0]['client_id'],'legacy')
            finally:store.close()

    def test_hub_entrypoint_loads_clients_and_runs_timeout_cleanup(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)
            for file in ['server.py','config.py','clients.py','presence.py','items.json']:
                shutil.copyfile(root/file,target/file)
            key='c'*64
            (target/'clients.json').write_text(json.dumps({'clients':[{'id':'one','api_token_sha256':hashlib.sha256(key.encode()).hexdigest(),'minimum_votes':5}]}))
            (target/'settings.json').write_text(json.dumps({'connection_timeout_seconds':5}))
            with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
            env=dict(os.environ,KR_MODE='hub',KR_BIND='127.0.0.1',KR_PUBLIC_URL='https://example.invalid',KR_GAME_API_TOKEN='')
            proc=subprocess.Popen([sys.executable,str(target/'server.py'),'--port',str(port)],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            base='http://127.0.0.1:'+str(port)
            opener=build_opener();opener.addheaders=[('Authorization','Bearer '+key)]
            try:
                deadline=time.monotonic()+8
                while True:
                    try:
                        with opener.open(base+'/api/config',timeout=1) as response:cfg=json.load(response)
                        break
                    except OSError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.05)
                self.assertEqual(cfg['minimum_votes'],5)
                def send(data):
                    req=Request(base+'/reqapi/killingroom/startGame',data=urlencode({'data':data}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
                    with opener.open(req,timeout=2) as response:return ET.fromstring(response.read())
                first=send('cr=1&uid=test&sr=0')
                game=send('cr=2&uid=test&sid='+first.findtext('sid'))
                token=game.findtext('url').rsplit('/',1)[1]
                db=sqlite3.connect(target/'kr_voting.sqlite3')
                db.execute('UPDATE games SET last_seen=1');db.commit();db.close()
                deadline=time.monotonic()+5
                while True:
                    with opener.open(base+'/api/v/'+token,timeout=1) as response:state=json.load(response)
                    if state['ended']:break
                    if time.monotonic()>deadline:self.fail('Timeout-Worker beendet die Sitzung nicht.')
                    time.sleep(.1)
                self.assertEqual(state['end_reason'],'timeout')
            finally:
                proc.terminate()
                try:out=proc.communicate(timeout=8)[0]
                except subprocess.TimeoutExpired:proc.kill();out=proc.communicate()[0]
                self.assertEqual(proc.returncode,0,out.decode(errors='replace'))


@unittest.skipUnless(importlib.util.find_spec('discord'),'Discord-Abhaengigkeit optional')
class DiscordOfflineTests(unittest.TestCase):
    def test_publisher_reuses_messages_and_closes_buttons(self):
        from discord_bot import VotingBot
        async def check():
            store=Store(':memory:','https://example.invalid')
            try:
                first=ET.fromstring(store.game_request('startGame',{'cr':'1','uid':'u'}))
                game=ET.fromstring(store.game_request('startGame',{'cr':'2','uid':'u','sid':first.findtext('sid')}))
                gid=game.findtext('gid')
                store.game_request('newFloor',{'cr':'3','uid':'u','gid':gid,'floor':'0','items':'good1,good2,bad1,bad2'})
                message=SimpleNamespace(id=9001,edit=AsyncMock())
                channel=SimpleNamespace(guild=SimpleNamespace(id=201),send=AsyncMock(return_value=message),fetch_message=AsyncMock(return_value=message))
                bot=VotingBot(store,'101','201');bot.get_channel=lambda _id:channel
                snap=store.discord_snapshots()[0]
                await bot.publish_one(snap)
                await bot.publish_one(store.discord_snapshots()[0])
                self.assertEqual(channel.send.await_count,1)
                self.assertEqual(message.edit.await_count,0)
                store.vote(snap['token'],'discord:test',snap['round_id'],'good1')
                await bot.publish_one(store.discord_snapshots()[0])
                self.assertEqual(message.edit.await_count,1)
                store.game_request('endFloor',{'cr':'4','uid':'u','gid':gid,'floor':'1'})
                await bot.publish_one(store.discord_snapshots()[0])
                final_view=message.edit.call_args.kwargs['view']
                self.assertTrue(all(b.disabled for b in final_view.children if b.custom_id))
                self.assertEqual(store.discord_snapshots(),[])
                await bot.close()
            finally:store.close()
        asyncio.run(check())

    def test_persistent_buttons_change_one_account_vote_and_route_by_player(self):
        from discord_bot import VotingView, VotingBot
        async def check():
            store=Store(':memory:','https://example.invalid')
            try:
                start=ET.fromstring(store.game_request('startGame',{'cr':'1','uid':'u'}))
                game=ET.fromstring(store.game_request('startGame',{'cr':'2','uid':'u','sid':start.findtext('sid')}))
                gid=game.findtext('gid')
                store.game_request('newFloor',{'cr':'3','uid':'u','gid':gid,'floor':'0','items':'good1,good2,bad1,bad2'})
                snapshot=store.discord_snapshots()[0]
                view=VotingView(store,snapshot)
                self.assertTrue(view.is_persistent())
                fake=SimpleNamespace(user=SimpleNamespace(id=12345),response=SimpleNamespace(send_message=AsyncMock()))
                await view.children[0].callback(fake);await view.children[1].callback(fake)
                self.assertEqual(store.statistics()['votes'],1)
                fake.response.send_message.assert_awaited()
                bot=VotingBot(store,'101','201')
                self.assertEqual(bot.destination(snapshot),(101,201))
                await bot.close()
            finally:store.close()
        asyncio.run(check())


if __name__=='__main__':unittest.main(verbosity=2)
