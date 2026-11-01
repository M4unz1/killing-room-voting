import base64
import http.cookiejar
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Store, VotingServer, client_reply, server_reply
from patch_game import install, restore, digest, load_manifest


class ProtocolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name)/'state.sqlite3'
        self.store = Store(self.database, 'http://127.0.0.1:8765')
        self.server = VotingServer(('127.0.0.1', 0), self.store)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.browser = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.store.close()
        self.temp.cleanup()

    def game(self, action, fields, multipart=False):
        payload = '&'.join(key+'='+str(value) for key,value in fields.items())
        if multipart:
            boundary = 'KillingRoomTestBoundary'
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="data"\r\n\r\n'
                    + payload + f'\r\n--{boundary}--\r\n').encode()
            content_type = 'multipart/form-data; boundary='+boundary
        else:
            body = urlencode({'data': payload}).encode()
            content_type = 'application/x-www-form-urlencoded'
        req = Request(self.base+'/reqapi/killingroom/'+action, data=body, headers={'Content-Type':content_type})
        with self.browser.open(req) as response:
            self.assertEqual(response.status, 200)
            root = ET.fromstring(response.read())
        self.assertEqual(root.findtext('error'), '0')
        self.assertEqual(int(root.findtext('cr')), client_reply(int(fields['cr'])))
        return root

    def start(self, multipart=False, player='Lars + <Test>'):
        startup = self.game('startGame', {'cr':123456,'sr':0,'uid':'test-device','floor':0}, multipart)
        data = {'cr':654321,'uid':'test-device','sr':server_reply(int(startup.findtext('sr'))),
                'sid':startup.findtext('sid'),'name':base64.b64encode(player.encode()).decode(),
                'height':180,'weight':80,'steamName':'Steam & Player + Test'}
        response = self.game('startGame', data, multipart)
        token = response.findtext('url').rsplit('/',1)[1]
        return response.findtext('gid'), token, data

    def state(self, token, browser=None):
        with (browser or self.browser).open(self.base+'/api/v/'+token) as response:
            return json.load(response)

    def vote(self, token, round_id, item, browser=None):
        request = Request(self.base+'/api/v/'+token, data=json.dumps({'round_id':round_id,'item':item}).encode(),
                          headers={'Content-Type':'application/json'})
        with (browser or self.browser).open(request) as response:
            return json.load(response)

    def open_floor(self, gid, items='good1,good2,bad1,bad2', floor=0):
        return self.game('newFloor', {'cr':555,'uid':'test-device','gid':gid,'sr':0,'floor':floor,'items':items})

    def finish_floor(self, gid, floor=0):
        return self.game('endFloor', {'cr':556,'uid':'test-device','gid':gid,'sr':0,'floor':floor+1})

    def test_two_stage_start_and_retry_do_not_duplicate_game(self):
        gid, token, fields = self.start(player='Lars + <Test>')
        self.assertEqual(self.state(token)['player'], 'Lars + <Test>')
        retry = self.game('startGame', fields)
        self.assertEqual(retry.findtext('gid'), gid)
        self.assertEqual(retry.findtext('url').rsplit('/',1)[1], token)

    def test_reported_end_floor_counter_and_late_retry(self):
        # Actual user log: newFloor floor=0, then endFloor floor=1.
        gid, token, _ = self.start()
        self.open_floor(gid, floor=0)
        first_round = self.state(token)['round_id']
        self.vote(token, first_round, 'good1')
        first_request = {'cr':701,'uid':'test-device','gid':gid,'sr':0,'floor':1}
        first_result = self.game('endFloor', first_request)
        self.assertEqual(first_result.findtext('votesCount'), '1')
        self.assertEqual(first_result.find('votes/item[@name="good1"]').text, '1')
        self.assertFalse(self.state(token)['active'])
        self.open_floor(gid, items='good3,good4,bad3,bad4', floor=1)
        second_round = self.state(token)['round_id']
        self.vote(token, second_round, 'bad4')
        replay = self.game('endFloor', first_request)
        self.assertEqual(ET.tostring(replay), ET.tostring(first_result))
        self.assertTrue(self.state(token)['active'])
        second_result = self.game('endFloor', {'cr':702,'uid':'test-device','gid':gid,'sr':0,'floor':2})
        self.assertEqual(second_result.findtext('votesCount'), '1')
        self.assertEqual(second_result.find('votes/item[@name="bad4"]').text, '1')

    def test_final_floor_counter_can_stay_unchanged(self):
        # CalculateFinishLevel caps actualFloor at the configured final floor.
        gid, token, _ = self.start()
        self.open_floor(gid, floor=6)
        self.vote(token, self.state(token)['round_id'], 'good1')
        previous_request = {'cr':801,'uid':'test-device','gid':gid,'sr':0,'floor':7}
        previous_result = self.game('endFloor', previous_request)
        self.assertEqual(previous_result.findtext('votesCount'), '1')
        self.open_floor(gid, items='good3,good4,bad3,bad4', floor=7)
        self.vote(token, self.state(token)['round_id'], 'bad4')
        last_result = self.game('endFloor', {'cr':802,'uid':'test-device','gid':gid,'sr':0,'floor':7})
        self.assertEqual(last_result.findtext('votesCount'), '1')
        self.assertEqual(last_result.find('votes/item[@name="bad4"]').text, '1')
        replay = self.game('endFloor', previous_request)
        self.assertEqual(ET.tostring(replay), ET.tostring(previous_result))

    def test_update_keeps_existing_0_1_database_votes(self):
        gid, token, _ = self.start()
        self.open_floor(gid)
        self.vote(token, self.state(token)['round_id'], 'bad2')
        # Version 0.1 did not have this new request-to-round binding table.
        with self.store.lock, self.store.db:
            self.store.db.execute('DROP TABLE end_floor_replies')
        upgraded = Store(self.database, self.base)
        try:
            response = ET.fromstring(upgraded.game_request('endFloor',
                {'cr':'901','uid':'test-device','gid':gid,'sr':'0','floor':'1'}))
            self.assertEqual(response.findtext('votesCount'), '1')
            self.assertEqual(response.find('votes/item[@name="bad2"]').text, '1')
        finally:
            upgraded.close()

    def test_unmatched_floor_does_not_close_current_round(self):
        gid, token, _ = self.start()
        self.open_floor(gid)
        self.vote(token, self.state(token)['round_id'], 'good1')
        empty = self.game('endFloor', {'cr':911,'uid':'test-device','gid':gid,'sr':0,'floor':9})
        self.assertEqual(empty.findtext('votesCount'), '0')
        self.assertTrue(self.state(token)['active'])
        self.assertEqual(self.state(token)['votesCount'], 1)
        actual = self.game('endFloor', {'cr':912,'uid':'test-device','gid':gid,'sr':0,'floor':1})
        self.assertEqual(actual.findtext('votesCount'), '1')

    def test_multipart_works_and_raw_inner_base64_plus_is_preserved(self):
        # U+083E encodes to 4KC+ in Base64 and exercises the inner + handling.
        _, token, _ = self.start(multipart=True, player='\u083e')
        self.assertEqual(self.state(token)['player'], '\u083e')

    def test_voting_full_cycle_changes_are_single_votes_and_close_is_idempotent(self):
        gid, token, _ = self.start()
        self.open_floor(gid)
        initial = self.state(token)
        rid = initial['round_id']
        self.assertEqual([x['kind'] for x in initial['items']], ['good','good','bad','bad'])
        self.assertEqual(self.vote(token, rid, 'good1')['votesCount'], 1)
        self.assertEqual(self.vote(token, rid, 'bad2')['votesCount'], 1)
        other_browser = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.state(token, other_browser)
        self.vote(token, rid, 'good1', other_browser)
        self.open_floor(gid)  # retry must preserve round and votes
        self.assertEqual(self.state(token)['round_id'], rid)
        finished = self.finish_floor(gid)
        self.assertEqual(finished.findtext('votesCount'), '2')
        self.assertEqual({x.get('name'):int(x.text) for x in finished.findall('votes/item')},
                         {'good1':1,'good2':0,'bad1':0,'bad2':1})
        self.assertEqual(ET.tostring(self.finish_floor(gid)), ET.tostring(finished))
        with self.assertRaises(HTTPError) as error:
            self.vote(token, rid, 'good2')
        self.assertEqual(error.exception.code, 400)
        self.assertFalse(self.state(token)['active'])
        self.open_floor(gid, floor=1)
        next_state = self.state(token)
        self.assertTrue(next_state['active'])
        self.assertEqual(next_state['votesCount'], 0)
        self.assertNotEqual(next_state['round_id'], rid)

    def test_persistence_and_xml_attribute_escaping(self):
        gid, token, _ = self.start()
        self.open_floor(gid, items='good&"1,good2,bad1,bad2'.replace('&', '_'))
        current = self.state(token)
        item = current['items'][0]['id']
        self.vote(token, current['round_id'], item)
        root = self.finish_floor(gid)
        self.assertEqual(root.find('votes/item').get('name'), item)
        second_store = Store(self.database, self.base)
        try:
            self.assertEqual(second_store.view(token, 'different-viewer')['votesCount'], 1)
        finally:
            second_store.close()

    def test_game_isolation_boss_deduplication_and_game_end(self):
        gid, token, _ = self.start()
        self.open_floor(gid)
        rid = self.state(token)['round_id']
        self.vote(token, rid, 'good1')
        other_gid, other_token, _ = self.start(player='Anderer Spieler')
        self.open_floor(other_gid)
        self.assertEqual(self.state(other_token)['votesCount'], 0)
        self.assertEqual(self.state(token)['votesCount'], 1)
        for _ in range(2):
            self.game('saveBossStat', {'cr':300,'uid':'test-device','gid':gid,'sr':0,'boss':1,'bossState':'kill'})
        stats = self.game('getBossStat', {'cr':301,'uid':'test-device','gid':gid,'sr':0,'boss':1})
        self.assertEqual(stats.findtext('bossKill'), '1')
        self.assertEqual(stats.findtext('bossKilled'), '0')
        self.game('endGame', {'cr':302,'uid':'test-device','gid':gid,'sr':0})
        self.assertTrue(self.state(token)['ended'])
        self.assertTrue(self.state(other_token)['active'])
        with self.assertRaises(HTTPError):
            self.vote(token, rid, 'good1')

    def test_stale_votes_and_cross_site_requests_rejected(self):
        gid, token, _ = self.start()
        self.open_floor(gid)
        rid = self.state(token)['round_id']
        self.open_floor(gid, items='good3,good4,bad3,bad4', floor=1)
        with self.assertRaises(HTTPError):
            self.vote(token, rid, 'good1')
        self.assertEqual(self.state(token)['votesCount'], 0)
        request = Request(self.base+'/api/v/'+token, data=b'{}',
                          headers={'Content-Type':'application/json','Origin':'https://unrelated.example'})
        with self.assertRaises(HTTPError) as error:
            self.browser.open(request)
        self.assertEqual(error.exception.code, 403)

    def test_health_assets_and_wrong_original_payload(self):
        for path in ('/', '/app.js', '/style.css', '/api/health'):
            with self.browser.open(self.base+path) as response:
                self.assertEqual(response.status, 200)
        with self.browser.open(self.base+'/favicon.ico') as response:
            self.assertEqual(response.status, 204)
        request = Request(self.base+'/reqapi/killingroom/startGame', data=urlencode({'data':'ENCRYPTED_BASE64=='}).encode(),
                          headers={'Content-Type':'application/x-www-form-urlencoded'})
        with self.assertRaises(HTTPError) as error:
            self.browser.open(request)
        self.assertEqual(error.exception.code, 400)


class PatchSafetyTests(unittest.TestCase):
    def test_wrong_binary_cannot_be_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'Assembly-CSharp.dll'
            path.write_bytes(b'not the supported game')
            with self.assertRaises(ValueError):
                install(path)
            self.assertEqual(path.read_bytes(), b'not the supported game')
            self.assertEqual(len(list(Path(temp).iterdir())), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
