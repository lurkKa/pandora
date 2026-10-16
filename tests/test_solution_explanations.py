import json
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

os.environ.setdefault('PANDORA_SKIP_STARTUP', '1')
from fastapi import HTTPException
from starlette.requests import Request
import main
from solution_explanations import explanation_error

CODE = 'def solve(a, b):\n    return a + b\n'
TEXT = 'Функция solve принимает два числовых аргумента a и b. Она складывает эти значения и возвращает сумму как результат; при нулевых входных данных получается ноль.'
JS_CODE = 'function add(a, b) { return a + b; }'
JS_TEXT = 'The function add receives two numeric arguments a and b. It adds both numbers and returns their sum as the result, including zero inputs.'
REQUEST = Request({'type': 'http', 'method': 'POST', 'headers': [], 'client': ('127.0.0.1', 1), 'path': '/'})


class ExplanationQualityTests(unittest.TestCase):
    def test_explanations_in_both_languages(self):
        self.assertIsNone(explanation_error(TEXT, CODE))
        self.assertIsNone(explanation_error(JS_TEXT, JS_CODE))

    def test_short_explanations_start_at_ten_characters(self):
        self.assertEqual(len('Суммирую a'),10)
        self.assertIsNone(explanation_error('Суммирую a',CODE))
        self.assertIsNone(explanation_error('Сумма чисел',CODE))
        self.assertIsNone(explanation_error('Returns sum',JS_CODE))
        self.assertIsNone(explanation_error('Цвет текста', '<p>Текст</p>', 'frontend'))
        for text in ('Сумма a+b','          ','qwertyasdf','фывафывафыва','xyz abcdef'):
            with self.subTest(text=text): self.assertIsNotNone(explanation_error(text,CODE))

    def test_empty_noise_repeats_and_unrelated_text_rejected(self):
        for text in ('', 'решение', 'фыва '*100, 'qwerty '*100,
                     ' '.join(['hjkdfshjkf']*40),
                     'Сегодня я гулял по красивому городу и встретил нескольких старых друзей возле огромной башни в центре города.',
                     TEXT.replace('solve','another_function').replace(' a ', ' alpha ').replace(' b.', ' beta.')):
            with self.subTest(text=text[:25]):
                self.assertIsNotNone(explanation_error(text, CODE))
        self.assertIsNotNone(explanation_error(TEXT*100, CODE))


class ExplanationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database=patch.object(main,'DATABASE', self.temp.name+'/test.db')
        database.start(); self.addCleanup(database.stop)
        main.init_db()
        self.user={'id':901,'username':'test-explainer','role':'student'}
        self.admin={'id':903,'username':'test-teacher','role':'admin'}
        self.tasks={
            'python':{'id':'python','title':'Сумма','category':'python','tier':'D','xp':25,'initial_code':'def solve(a, b):\n    pass', 'check_logic':{'engine':'pyodide','cases':[{'code':'solve(2,3)','expected':5}]}},
            'javascript':{'id':'javascript','category':'javascript','tier':'D','xp':25,'check_logic':{'engine':'javascript','cases':[{'code':'add(2,3)','expected':5}]}},
            'frontend':{'id':'frontend','category':'frontend','tier':'D','xp':25,'check_logic':{'engine':'iframe','cases':[]}},
            'scratch':{'id':'scratch','category':'scratch','tier':'D','xp':25},
        }
        lookup=patch.object(main,'_tasks_by_id',return_value=self.tasks)
        lookup.start(); self.addCleanup(lookup.stop)
        with main.get_db() as conn:
            conn.executemany('INSERT INTO users (id,username,display_name,password_hash,role,xp,level) VALUES (?,?,?,?,?,?,?)',
                [(901,'test-explainer','Ученик','hash','student',1234,7),
                 (902,'other-student','Другой','hash','student',0,1),
                 (903,'test-teacher','Учитель','hash','admin',0,1)])
            for task in self.tasks:
                conn.execute('INSERT INTO completed_tasks(user_id,task_id,solution,xp_earned) VALUES (901,?,?,25)',(task,CODE))
            conn.commit()

    def test_legacy_half_state_is_limited_to_python_javascript(self):
        with main.get_db() as conn:
            self.assertEqual(main._partial_completion_ids(conn.cursor(),901), {'python','javascript','frontend'})
            conn.execute("UPDATE completed_tasks SET is_valid=0 WHERE task_id='javascript'")
            self.assertEqual(main._partial_completion_ids(conn.cursor(),901), {'python','frontend'})
        status=json.loads(main.get_roadmap_status(REQUEST,self.user).body)
        self.assertEqual(status['partial_ids'],['frontend','javascript','python'])

    def test_restoration_is_idempotent_private_and_never_awards_xp(self):
        before_etag=main._roadmap_state_etag(901)
        with main.get_db() as conn:
            before=dict(conn.execute('SELECT * FROM completed_tasks WHERE user_id=901 AND task_id="python"').fetchone())
        with patch.object(main,'_finalize_typing_session',return_value={'verified':True,'usable':True,'high_confidence':False}) as telemetry:
            result=main.complete_task_explanation(REQUEST,'python',main.TaskExplanationRequest(explanation=TEXT),self.user)
            self.assertEqual(result['xp_earned'],0)
            main.complete_task_explanation(REQUEST,'python',main.TaskExplanationRequest(explanation=TEXT),self.user)
            self.assertEqual(telemetry.call_count,1)
        with main.get_db() as conn:
            after=dict(conn.execute('SELECT * FROM completed_tasks WHERE user_id=901 AND task_id="python"').fetchone())
            self.assertEqual(after['explanation'],TEXT)
            for key in ('solution','xp_earned','completed_at','is_valid'):
                self.assertEqual(before[key],after[key])
            self.assertEqual(conn.execute('SELECT xp FROM users WHERE id=901').fetchone()[0],1234)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM task_solution_methods').fetchone()[0],0)
            self.assertEqual(main._partial_completion_ids(conn.cursor(),901),{'javascript','frontend'})
        self.assertNotEqual(before_etag,main._roadmap_state_etag(901))
        self.assertEqual(main.get_task_work('python',self.user)['solution'],CODE)
        self.assertIsNone(main.get_task_work('python',{'id':902})['solution'])

    def test_invalid_text_or_unverified_typing_cannot_restore(self):
        for text,integrity in [('qwerty '*30, {'verified':True,'usable':True}),
                               (TEXT, {'verified':False,'usable':False}),
                               (TEXT, {'verified':True,'usable':True,'high_confidence':True})]:
            with patch.object(main,'_finalize_typing_session',return_value=integrity):
                with self.assertRaises(HTTPException) as error:
                    main.complete_task_explanation(REQUEST,'python',main.TaskExplanationRequest(explanation=text),self.user)
                self.assertEqual(error.exception.status_code,422)
            self.assertEqual(main.get_task_work('python',self.user)['explanation'],'')
        with self.assertRaises(HTTPException):
            main.complete_task_explanation(REQUEST,'python',main.TaskExplanationRequest(explanation=TEXT),{'id':902})
        with self.assertRaises(HTTPException):
            main.complete_task_explanation(REQUEST,'scratch',main.TaskExplanationRequest(explanation=TEXT),self.user)

    def test_nonempty_noise_rejected_before_code_execution(self):
        with patch.object(main,'_get_task_with_check_logic',return_value=self.tasks['python']), patch.object(main,'verify_task') as runner:
            with self.assertRaises(HTTPException) as error:
                main.attempt_task(REQUEST,main.TaskAttemptRequest(task_id='python',code=CODE,explanation='qwerty '*20),self.user)
            self.assertEqual(error.exception.status_code,422)
            runner.assert_not_called()

    def attempt(self, sampled=False, explanation=TEXT, category='python', code=CODE, passed=True):
        with patch.object(main,'_get_task_with_check_logic',return_value=self.tasks[category]), \
             patch.object(main,'verify_task',return_value=({'passed':passed,'cases':[{'passed':passed}]},1)), \
             patch.object(main,'_unlock_state',return_value=(True,{})), \
             patch.object(main,'_is_top7_task_by_tier',return_value=False), \
             patch.object(main,'_extra_review_sample_required',return_value=sampled), \
             patch.object(main,'_finalize_typing_session',return_value={'verified':True,'usable':True,'high_confidence':False}), \
             patch.object(main,'ATTEMPT_COOLDOWN_S',0):
            return main.attempt_task(REQUEST,main.TaskAttemptRequest(task_id=category,code=code,explanation=explanation),self.user)

    def test_new_completion_and_same_method_both_keep_explanations(self):
        with main.get_db() as conn:
            conn.execute("DELETE FROM completed_tasks WHERE task_id='python'");conn.commit()
        first=self.attempt()
        self.assertEqual(first['status'],'completed')
        self.assertGreater(first['xp_earned'],0)
        self.assertEqual(main.get_task_work('python',self.user)['explanation'],TEXT)
        second=self.attempt()
        self.assertEqual(second['status'],'same_method')
        self.assertEqual(first['xp'],second['xp'])

    def delete_completion(self, category='python'):
        with main.get_db() as conn:
            conn.execute('DELETE FROM completed_tasks WHERE user_id=901 AND task_id=?',(category,))
            conn.commit()

    def add_explanation(self, category='python', text=TEXT):
        with patch.object(main,'_finalize_typing_session',return_value={'verified':True,'usable':True,'high_confidence':False}):
            return main.complete_task_explanation(REQUEST,category,main.TaskExplanationRequest(explanation=text),self.user)

    def test_code_only_gives_half_then_pays_fixed_remainder_once(self):
        self.delete_completion()
        first=self.attempt(explanation='')
        self.assertEqual(first['status'],'completed')
        self.assertEqual(first['xp_earned'],12)
        self.assertEqual(first['stars_earned'],.5)
        self.assertTrue(first['explanation_required'])
        self.assertEqual(first['completion_percent'],50)
        repeated=self.attempt(explanation='')
        self.assertEqual(repeated['status'],'same_method')
        self.assertEqual(repeated['xp_earned'],0)
        self.assertEqual(repeated['xp'],first['xp'])
        with main.get_db() as conn:
            row=conn.execute('SELECT * FROM completed_tasks WHERE user_id=901 AND task_id="python"').fetchone()
            self.assertEqual((row['xp_earned'],row['explanation_xp_pending'],row['star_fraction']),(12,13,.5))
            before_xp=conn.execute('SELECT xp FROM users WHERE id=901').fetchone()[0]
        final=self.add_explanation()
        self.assertEqual(final['xp_earned'],13)
        self.assertEqual(final['stars_earned'],.5)
        self.assertEqual(final['xp'],before_xp+13)
        self.assertEqual(self.add_explanation()['xp_earned'],0)
        with main.get_db() as conn:
            row=conn.execute('SELECT * FROM completed_tasks WHERE user_id=901 AND task_id="python"').fetchone()
            self.assertEqual((row['xp_earned'],row['explanation_xp_pending'],row['star_fraction']),(25,0,1))
            self.assertEqual(conn.execute('SELECT xp_earned FROM task_solution_methods WHERE user_id=901 AND task_id="python"').fetchone()[0],25)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM xp_log WHERE user_id=901 AND reason='task_explanation_completed'").fetchone()[0],1)

    def test_incorrect_code_without_explanation_gives_no_reward(self):
        self.delete_completion()
        result=self.attempt(explanation='',passed=False)
        self.assertEqual(result['status'],'failed')
        with main.get_db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM completed_tasks WHERE task_id="python"').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT xp FROM users WHERE id=901').fetchone()[0],1234)

    def test_explanation_in_same_code_attempt_upgrades_without_second_code_award(self):
        self.delete_completion()
        self.attempt(explanation='')
        final=self.attempt()
        self.assertEqual(final['status'],'same_method')
        self.assertEqual(final['xp_earned'],13)
        self.assertFalse(final['explanation_required'])
        self.assertEqual(self.attempt()['xp_earned'],0)

    def test_advanced_tier_stars_are_not_rounded_to_zero(self):
        self.delete_completion()
        self.tasks['python'].update(tier='A',xp=315)
        first=self.attempt(explanation='')
        self.assertEqual(first['xp_earned'],157)
        self.assertEqual(first['stars_earned'],1.5)
        with main.get_db() as conn:
            main._register_task_stars(conn,self.tasks)
            self.assertEqual(conn.execute('SELECT task_stars(task_id,star_fraction) FROM completed_tasks WHERE task_id="python"').fetchone()[0],1.5)
        final=self.add_explanation()
        self.assertEqual(final['xp_earned'],158)
        self.assertEqual(final['stars_earned'],1.5)

    def test_frontend_and_javascript_allow_code_only_and_accept_explanations(self):
        html='<div class="card">Hello</div>'
        description='На странице элемент div с классом card показывает приветствие. Разметка создаёт блок, а стили задают его ширину и расположение; результат отображается на экране.'
        self.assertIsNone(explanation_error(description,html,'frontend'))
        for category,code,text in [('frontend',html,description),('javascript',JS_CODE,JS_TEXT)]:
            self.delete_completion(category)
            first=self.attempt(explanation='',category=category,code=code)
            self.assertEqual(first['status'],'completed')
            self.assertTrue(first['explanation_required'])
            self.assertEqual(first['xp_earned'],12)
            self.assertEqual(self.add_explanation(category,text)['xp_earned'],13)

    def test_scratch_keeps_full_reward_without_explanation(self):
        self.delete_completion('scratch')
        with main.get_db() as conn:
            result=main.process_task_completion(conn.cursor(),901,'scratch',25,solution='project.sb3',code_language='scratch',allow_multiple_methods=False)
            conn.commit()
        self.assertEqual(result['xp_earned'],25)
        self.assertFalse(result['explanation_required'])
        self.assertEqual(result['stars_earned'],1)

    def test_teacher_approval_of_code_only_keeps_half_reward(self):
        self.delete_completion()
        pending=self.attempt(sampled=True,explanation='')
        with patch.object(main,'load_tasks',return_value={'tasks':list(self.tasks.values())}):
            reviewed=main.review_submission(pending['submission_id'],main.ReviewRequest(status='approved',score=10),self.admin)
        self.assertEqual(reviewed['xp_awarded'],12)
        self.assertEqual(main.get_task_work('python',self.user)['explanation'],'')
        self.assertEqual(self.add_explanation()['xp_earned'],13)
        reviews=main.get_submissions(status='approved',compact_duplicates=False,admin=self.admin)['submissions']
        review=next(s for s in reviews if s['id']==pending['submission_id'])
        self.assertEqual(review['explanation'],TEXT)

    def test_weekly_ranking_preserves_half_stars_and_counts_explanation_xp(self):
        self.delete_completion()
        self.attempt(explanation='')
        before=main.get_leaderboard_week(100)['leaderboard']
        before=next(u for u in before if u['id']==901)
        final=self.add_explanation()
        after=next(u for u in main.get_leaderboard_week(100)['leaderboard'] if u['id']==901)
        self.assertEqual(after['stars_week']-before['stars_week'],.5)
        self.assertEqual(after['xp_week']-before['xp_week'],final['xp_earned'])

    def test_pending_review_can_receive_explanation_for_the_same_code(self):
        self.delete_completion()
        pending=self.attempt(sampled=True,explanation='')
        updated=self.attempt(sampled=True)
        self.assertEqual(pending['submission_id'],updated['submission_id'])
        with main.get_db() as conn:
            self.assertEqual(conn.execute('SELECT explanation FROM submissions WHERE id=?',(pending['submission_id'],)).fetchone()[0],TEXT)

    def test_multiple_methods_keep_a_consistent_deferred_ledger(self):
        self.delete_completion()
        with main.get_db() as conn:
            cursor=conn.cursor()
            for simhash in ('0'*16,'f'*16):
                result=main.process_task_completion(cursor,901,'python',25,CODE,simhash,code_language='python',explanation='')
                self.assertEqual(result['status'],'success')
            row=cursor.execute('SELECT xp_earned,explanation_xp_pending FROM completed_tasks WHERE user_id=901 AND task_id="python"').fetchone()
            earned,pending=row
            self.assertGreater(pending,0)
            self.assertEqual(main._settle_explanation_reward(cursor,901,'python',TEXT),pending)
            self.assertEqual(main._settle_explanation_reward(cursor,901,'python',TEXT),0)
            total=cursor.execute('SELECT SUM(xp_earned),SUM(explanation_xp_pending) FROM task_solution_methods WHERE user_id=901 AND task_id="python"').fetchone()
            self.assertEqual(tuple(total),(earned+pending,0))
            conn.commit()

    def test_parallel_explanations_cannot_collect_the_remainder_twice(self):
        self.delete_completion()
        self.attempt(explanation='')
        def submit():
            return main.complete_task_explanation(REQUEST,'python',main.TaskExplanationRequest(explanation=TEXT),self.user)
        with patch.object(main,'_finalize_typing_session',return_value={'verified':True,'usable':True,'high_confidence':False}):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda _:submit(),range(2)))
        self.assertEqual(sum(r['xp_earned'] for r in results),13)
        self.assertEqual(sum(r.get('stars_earned',0) for r in results),.5)

    def test_explanation_does_not_consume_another_solution_slot(self):
        self.delete_completion()
        self.attempt(explanation='')
        with main.get_db() as conn:
            for i in range(2,main.MAX_METHODS_PER_TASK+1):
                conn.execute('INSERT INTO task_solution_methods(user_id,task_id,method_index,solution,xp_earned) VALUES (901,"python",?,?,0)',(i,CODE))
            conn.commit()
        self.assertEqual(self.add_explanation()['xp_earned'],13)
        with main.get_db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM task_solution_methods WHERE user_id=901 AND task_id="python"').fetchone()[0],main.MAX_METHODS_PER_TASK)

    def test_sampled_submission_preserves_explanation_until_teacher_approval(self):
        with main.get_db() as conn:
            conn.execute("DELETE FROM completed_tasks WHERE task_id='python'");conn.commit()
        pending=self.attempt(sampled=True)
        self.assertEqual(pending['status'],'pending_review')
        with main.get_db() as conn:
            self.assertEqual(conn.execute('SELECT explanation FROM submissions WHERE id=?',(pending['submission_id'],)).fetchone()[0],TEXT)
        with patch.object(main,'load_tasks',return_value={'tasks':list(self.tasks.values())}):
            main.review_submission(pending['submission_id'],main.ReviewRequest(status='approved',score=10),self.admin)
        self.assertEqual(main.get_task_work('python',self.user)['explanation'],TEXT)

    def test_manual_review_retains_explanation(self):
        with main.get_db() as conn:
            conn.execute("DELETE FROM completed_tasks WHERE task_id='python'")
            cursor=conn.execute('INSERT INTO submissions(user_id,task_id,category,tier,code,code_language,status,explanation) VALUES (901,?,?,?,?,?,?,?)',
                              ('python','python','D',CODE,'python','pending',TEXT))
            submission_id=cursor.lastrowid
            conn.commit()
        with patch.object(main,'load_tasks',return_value={'tasks':list(self.tasks.values())}), patch.object(main,'process_task_completion',return_value={'status':'same_method'}):
            # Insert the completed row as the completion helper would, to isolate
            # review's explanation propagation from the XP/event subsystem.
            with main.get_db() as conn:
                conn.execute('INSERT INTO completed_tasks(user_id,task_id,solution,xp_earned) VALUES (901,"python",?,25)',(CODE,));conn.commit()
            main.review_submission(submission_id,main.ReviewRequest(status='approved',score=10),self.admin)
        self.assertEqual(main.get_task_work('python',self.user)['explanation'],TEXT)

    def test_repeatable_migration_keeps_explanations_and_rank_ids(self):
        with main.get_db() as conn:
            conn.execute('UPDATE completed_tasks SET explanation=? WHERE task_id="python"',(TEXT,));conn.commit()
            before={r['name']:r['id'] for r in conn.execute('SELECT id,name FROM ranks')}
        main.init_db()
        with main.get_db() as conn:
            after={r['name']:r['id'] for r in conn.execute('SELECT id,name FROM ranks')}
            self.assertEqual(before,after)
            self.assertEqual(conn.execute('SELECT MAX(min_xp) FROM ranks').fetchone()[0],10**12)
            self.assertGreaterEqual(len(after),40)
            self.assertEqual(conn.execute('SELECT explanation FROM completed_tasks WHERE task_id="python"').fetchone()[0],TEXT)
            rank=conn.execute('SELECT name FROM ranks WHERE min_xp<=? ORDER BY min_xp DESC LIMIT 1',(10**12,)).fetchone()[0]
            self.assertEqual(rank,'Pandora Eternal')
            self.assertGreater(main.compute_level(10**12),1000)


if __name__=='__main__':
    unittest.main()
