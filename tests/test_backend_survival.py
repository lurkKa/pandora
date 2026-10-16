import concurrent.futures
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

import backend_survival as api
from survival_campaign import LEVELS, VARIANTS, SCHEMA, UNIT, Process, grade, initial_files
from survival_runtime import PythonLab, LabCodeError, LabDatabase

spec = importlib.util.spec_from_file_location('survival_reference', Path(__file__).with_name('survival_reference.py'))
reference_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference_module)
reference = reference_module.reference


class RuntimeTests(unittest.TestCase):
    def run_code(self, body, *, budget=1000):
        files = initial_files('inventory')
        files['app.py'] = 'def handle(request,state,env,db):\n' + ''.join('    '+line+'\n' for line in body.splitlines())
        process = Process(files, budget=budget)
        try:
            result = process.request({'method': 'GET', 'path': '/health', 'body': '', 'headers': {}, 'time': 1, 'client': 'a'})
            return result, process.alive
        finally:
            process.close()

    def test_forbidden_capabilities(self):
        for expression in ['import os', 'import subprocess', 'x = request.__class__', 'import pathlib', 'from sqlite3 import connect']:
            with self.subTest(expression=expression), self.assertRaises(LabCodeError):
                PythonLab(expression+'\ndef handle(request,state,env,db): return {}')
        for expression in ['open("/etc/passwd")', 'eval("1")', 'globals()', 'str(handle)']:
            with self.subTest(expression=expression):
                result, alive = self.run_code(expression)
                self.assertFalse(alive)
                self.assertEqual(result['status'], 0)

    def test_resource_limits_cannot_be_caught(self):
        for body in ['try:\n    while True: pass\nexcept: pass\nreturn {"status":200,"body":{}}', 'x = b"a" * 1000000000000', 'x = "%9999999999999s" % "a"', 'x=[]\nx.append(x)', 'x="a"*32000\nx=str([x]*1000)']:
            with self.subTest(body=body):
                result, alive = self.run_code(body)
                self.assertFalse(alive)
                self.assertEqual(result['status'], 0)

    def test_sql_is_confined_and_rollback_is_real(self):
        db = LabDatabase()
        try:
            for sql in ["ATTACH DATABASE '/tmp/escape.db' AS x", 'SELECT * FROM sqlite_master', 'SELECT randomblob(999999999)', 'SELECT 1; SELECT 2', "INSERT INTO records VALUES ('x','not integer')"]:
                with self.subTest(sql=sql), self.assertRaises((ValueError, sqlite3.DatabaseError)):
                    db.execute(sql)
            self.assertEqual(db.rows(), [])
            db.execute('INSERT INTO records VALUES (?,?)', ["a' OR 1=1", 12])
            self.assertEqual(db.execute('SELECT amount FROM records WHERE id=?', ["a' OR 1=1"]).one(), {'amount': 12})
        finally:
            db.close()


class CampaignTests(unittest.TestCase):
    def test_all_contracts_are_solvable(self):
        self.assertEqual(min(x[1] for x in LEVELS), 10000)
        self.assertEqual(max(x[1] for x in LEVELS), 150000)
        for variant in VARIANTS:
            for level in range(1, len(LEVELS)+1):
                with self.subTest(variant=variant, level=level):
                    files = initial_files(variant)
                    files['app.py'] = reference(variant, database=level >= 6)
                    result = grade(files, variant, level, seed=19)
                    self.assertTrue(result['passed'], [x for x in result['checks'] if not x['passed']][:4])

    def test_hidden_values_change_and_final_code_can_repeat_early_stages(self):
        files = initial_files('inventory')
        files['app.py'] = reference('inventory')
        for seed in (0, 1, 42, 82362):
            result = grade(files, 'inventory', 11, seed=seed)
            self.assertTrue(result['passed'], [x for x in result['checks'] if not x['passed']][:3])
        self.assertTrue(grade(files, 'inventory', 2, migrated=True)['passed'])

    def test_fake_success_hardcoded_auth_and_no_database_rejected(self):
        files = initial_files('inventory')
        self.assertFalse(grade(files, 'inventory', 1)['passed'])
        files['app.py'] = reference('inventory', database=False)
        self.assertFalse(grade(files, 'inventory', 6)['passed'])
        files['app.py'] = reference('inventory').replace("env['API_TOKEN']", "'lab-token-change-me'")
        self.assertFalse(grade(files, 'inventory', 5)['passed'])
        files['.env'] = 'PORT=no'
        self.assertFalse(grade(files, 'inventory', 1)['passed'])

    def test_secret_cannot_be_hidden_by_filling_the_log_buffer(self):
        files = initial_files('inventory')
        files['app.py'] = reference('inventory', database=False).replace("state['requests'] =", "print(env['API_TOKEN'])\n    for i in range(101):\n        print('noise')\n    state['requests'] =", 1)
        result = grade(files, 'inventory', 5, seed=47)
        self.assertFalse(result['passed'])
        self.assertTrue(any(x['name'] == 'Токен не попал в логи' and not x['passed'] for x in result['checks']))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.db')
        @contextmanager
        def db():
            conn = sqlite3.connect(self.path, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
        self.db = db
        with db() as conn:
            conn.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1); CREATE TABLE xp_log(id INTEGER PRIMARY KEY,user_id INTEGER,xp_change INTEGER,reason TEXT,task_id TEXT); INSERT INTO users(id) VALUES (1),(2);')
            api.ensure_schema(conn.cursor())
            conn.commit()
        def award(cur, uid, amount, reason, task_id):
            cur.execute('UPDATE users SET xp=xp+? WHERE id=?', (amount,uid))
            cur.execute('INSERT INTO xp_log(user_id,xp_change,reason,task_id) VALUES (?,?,?,?)', (uid,amount,reason,task_id))
        self.service = api.SurvivalService(db, award)
        self.state = self.service.state(1, 'inventory')
        def auth(authorization: str = Header(None)):
            if authorization not in ('Bearer one','Bearer two'): raise HTTPException(401)
            return {'id': 1 if authorization == 'Bearer one' else 2}
        self.app = FastAPI()
        api.install(self.app, db, auth, award)
        self.client = TestClient(self.app)
        self.headers = {'Authorization': 'Bearer one'}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def command(self, text):
        result = self.service.command(1, api.CommandInput(variant='inventory',revision=self.state['revision'],command=text))
        self.state = result['workspace']
        return result

    def prepare(self, body=None):
        files = dict(self.state['files'])
        files['app.py'] = body or reference('inventory')
        files['schema.sql'], files['pandora.service'] = SCHEMA, UNIT
        self.state = self.service.save(1, api.SaveInput(variant='inventory',revision=self.state['revision'],files=files))
        for text in ('ssh trainee@lab','python -m venv .venv','source .venv/bin/activate','pip install -r requirements.txt','python manage.py migrate','systemctl enable pandora','systemctl start pandora'):
            self.assertFalse(self.command(text)['output'].startswith('ERROR:'))

    def request(self, level=1):
        return api.GradeInput(variant='inventory',revision=self.state['revision'],level=level)

    def clear_cooldown(self):
        with self.db() as conn:
            conn.execute('UPDATE survival_workspaces SET last_grade=0')
            conn.commit()

    def test_no_auth_forged_payload_and_workspace_isolation(self):
        self.assertEqual(self.client.get('/api/survival/state').status_code, 401)
        self.assertEqual(self.client.post('/api/survival/grade',headers=self.headers,json={'revision':0,'level':1,'passed':True,'xp':150000}).status_code,422)
        self.prepare()
        other = self.client.get('/api/survival/state',headers={'Authorization':'Bearer two'}).json()
        self.assertNotEqual(other['files']['app.py'],self.state['files']['app.py'])
        before = dict(self.state['files'])
        before['server.py'] += '\n# hacked'
        self.assertEqual(self.client.post('/api/survival/save',headers=self.headers,json={'files':before,'revision':self.state['revision']}).status_code,422)
        for command in ('cat ../../etc/passwd','curl http://example.com:8080/health','python -c x','ssh root@real-host'):
            self.assertTrue(self.command(command)['output'].startswith('ERROR:'), command)

    def test_success_awards_once_and_reset_keeps_progress(self):
        self.prepare()
        self.assertEqual(self.command('curl http://localhost:8080/health')['response']['status'],200)
        result = self.service.run_grade(1,self.request())
        self.assertEqual(result['awarded'],10000)
        self.clear_cooldown()
        self.assertEqual(self.service.run_grade(1,self.request())['awarded'],0)
        self.state = self.service.reset(1,api.Input(variant='inventory',revision=self.state['revision']))
        self.assertTrue(self.state['levels'][0]['completed'])
        self.assertEqual(self.state['xp'],10000)
        self.assertFalse(self.state['shell']['running'])

    def test_wrong_solution_skip_locked_and_stale_process(self):
        self.prepare('def handle(request,state,env,db): return {"status": 501,"body":{}}')
        self.assertFalse(self.service.run_grade(1,self.request())['passed'])
        self.assertEqual(self.service.state(1,'inventory')['xp'],0)
        with self.assertRaises(HTTPException) as error:
            self.service.run_grade(1,self.request(11))
        self.assertEqual(error.exception.status_code,409)
        files = dict(self.state['files'])
        files['app.py'] = reference('inventory')
        self.state = self.service.save(1,api.SaveInput(variant='inventory',revision=self.state['revision'],files=files))
        with self.assertRaises(HTTPException): self.service.run_grade(1,self.request())

    def test_parallel_checks_cannot_duplicate_reward(self):
        self.prepare()
        data = self.request()
        def check():
            try: return self.service.run_grade(1,data)['awarded']
            except HTTPException as error: return error.status_code
        with concurrent.futures.ThreadPoolExecutor(2) as executor:
            results = list(executor.map(lambda _: check(),range(2)))
        self.assertIn(10000, results)
        self.assertEqual(self.service.state(1,'inventory')['xp'],10000)

    def test_edit_during_grading_cancels_reward(self):
        self.prepare()
        data = self.request()
        def race(*args, **kwargs):
            files = dict(self.state['files'])
            files['app.py'] += '\n# revised'
            self.service.save(1,api.SaveInput(variant='inventory',revision=self.state['revision'],files=files))
            return {'passed':True}
        with patch.object(api, 'grade', side_effect=race), self.assertRaises(HTTPException):
            self.service.run_grade(1,data)
        self.assertEqual(self.service.state(1,'inventory')['xp'],0)

    def test_export_has_runnable_transport(self):
        import io
        import zipfile
        response = self.client.get('/api/survival/export',headers=self.headers)
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertIn('server.py',archive.namelist())
            self.assertIn('ThreadingHTTPServer',archive.read('server.py').decode())

    def test_full_service_campaign_uses_exact_production_rewards(self):
        import os
        os.environ.setdefault('PANDORA_SKIP_STARTUP','1')
        import main
        self.service.award = main._award_survival_xp
        self.prepare()
        rewards = []
        with patch.object(main, 'apply_xp_change', side_effect=AssertionError('Multiplier path must not run')):
            for level, (_,amount,_) in enumerate(LEVELS,1):
                self.clear_cooldown()
                result = self.service.run_grade(1,self.request(level))
                self.assertTrue(result['passed'],result['checks'])
                self.assertEqual(result['awarded'],amount)
                rewards.append(amount)
        self.assertEqual(self.service.state(1,'inventory')['xp'],sum(rewards))
        with self.db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM survival_completions').fetchone()[0],11)
            api.ensure_schema(conn.cursor())
            conn.commit()

    def test_failed_award_rolls_back_the_completion_and_balance(self):
        self.prepare()
        original = self.service.award
        def broken(*args):
            original(*args)
            raise RuntimeError('Simulated ledger failure')
        self.service.award = broken
        with self.assertRaises(RuntimeError): self.service.run_grade(1,self.request())
        self.assertEqual(self.service.state(1,'inventory')['xp'],0)
        self.assertFalse(self.service.state(1,'inventory')['levels'][0]['completed'])

    def test_files_editor_console_and_active_scenario_survive_new_service(self):
        self.state = self.service.state(1,'telemetry')
        files = dict(self.state['files'])
        files['app.py'] += '\n# мой сохранённый код'
        ui = {'selected_file':'.env','selected_level':4,'cursor':12,'scroll':20,
              'terminal':[{'text':'HTTP 200','kind':'success'}], 'history':['ls','curl http://localhost:8080/health'],
              'command':'cat app.py', 'guide_open':True,'previous_open':False}
        self.state = self.service.save(1,api.SaveInput(variant='telemetry',revision=self.state['revision'],files=files,ui=ui))
        restored = api.SurvivalService(self.db,self.service.award).state(1)
        self.assertEqual(restored['variant'],'telemetry')
        self.assertEqual(restored['files'],files)
        self.assertEqual(restored['ui'],ui)
        self.assertEqual(self.service.state(2)['variant'],'inventory')
        self.assertEqual(self.service.state(2)['ui'],{})

    def test_session_saves_do_not_change_code_revision_or_allow_rewards(self):
        self.prepare()
        revision = self.state['revision']
        self.service.session(1,api.SessionInput(variant='inventory',revision=revision,ui={'selected_file':'schema.sql','selected_level':11}))
        self.assertEqual(self.service.state(1)['revision'],revision)
        with self.assertRaises(HTTPException): self.service.run_grade(1,self.request(11))
        self.assertEqual(self.service.run_grade(1,self.request())['awarded'],10000)
        for ui in ({'xp':150000},{'selected_file':'../../etc/passwd'},{'selected_level':True},{'terminal':[{'text':'a','kind':[]}]}):
            response=self.client.post('/api/survival/session',headers=self.headers,json={'variant':'inventory','revision':revision,'ui':ui})
            self.assertEqual(response.status_code,422)

    def test_migration_preserves_existing_workspaces_and_completions(self):
        self.prepare()
        self.service.run_grade(1,self.request())
        with self.db() as conn:
            conn.execute('ALTER TABLE survival_workspaces DROP COLUMN ui_json')
            api.ensure_schema(conn.cursor())
            api.ensure_schema(conn.cursor())
            conn.commit()
        restored=self.service.state(1)
        self.assertEqual(restored['files']['app.py'],self.state['files']['app.py'])
        self.assertTrue(restored['shell']['running'])
        self.assertEqual(restored['ui'],{})
        self.assertTrue(restored['levels'][0]['completed'])
        self.assertEqual(restored['xp'],10000)


if __name__ == '__main__':
    unittest.main()
