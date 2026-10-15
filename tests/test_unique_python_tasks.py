import ast
import copy
import itertools
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.unique_python import PACK, all_quests
from scripts.generate_unique_python import build_tasks
from task_shapes import public_task


class UniquePythonQuestsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quests=all_quests();cls.by_key={q.key:q for q in cls.quests}
        cls.tasks=build_tasks()

    def test_500_independent_contracts_and_saved_pack(self):
        from collections import Counter
        self.assertEqual(Counter(q.tier for q in self.quests),{t:100 for t in 'DCBAS'})
        self.assertEqual(len({q.title for q in self.quests}),500)
        self.assertEqual(len({ast.dump(ast.parse(q.source)) for q in self.quests}),500)
        self.assertEqual(len({q.contract for q in self.quests}),500)
        signatures=[]
        for task in self.tasks:
            cases=task['check_logic']['cases']+task['check_logic']['hidden_cases']
            self.assertEqual(len(task['check_logic']['cases']),3)
            self.assertGreaterEqual(len(task['check_logic']['hidden_cases']),5)
            self.assertGreater(len({json.dumps(c['expected'],sort_keys=True) for c in cases}),1)
            self.assertLessEqual(len(task['title']),40,task['id'])
            self.assertNotIn('check_logic',public_task(task))
            self.assertNotIn('hidden_cases',public_task(task))
            signatures.append(tuple(sorted((c['code'],json.dumps(c['expected'],sort_keys=True)) for c in cases)))
        self.assertEqual(len(set(signatures)),500)
        data=json.loads((ROOT/'tasks.json').read_text())
        self.assertEqual([t for t in data['tasks'] if t.get('source_pack')==PACK],self.tasks)
        self.assertEqual(len({t['id'] for t in data['tasks']}),len(data['tasks']))
        self.assertEqual(sum(t.get('source_pack')=='python_expeditions_20261015' for t in data['tasks']),1000)
        old_titles={t['title'] for t in data['tasks'] if t.get('source_pack')!=PACK}
        self.assertFalse(old_titles & {t['title'] for t in self.tasks})

    def test_every_quest_in_real_sandbox_runner(self):
        by_id={t['id']:t for t in self.tasks}
        for q in self.quests:
            task=by_id[f'py_oddity_{q.tier.lower()}_{q.key}']
            cases=task['check_logic']['cases']+task['check_logic']['hidden_cases']
            request={'code':q.solution(),'cases':cases}
            result=subprocess.run([sys.executable,str(ROOT/'runners/python_harness.py')],input=json.dumps(request),text=True,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,(q.key,result.stderr))
            output=json.loads(result.stdout)
            self.assertTrue(output['passed'],(q.key,output.get('exec_error'),[c for c in output.get('cases',[]) if not c['passed']][:2]))
            self.assertEqual(len(output['cases']),len(cases))

    def test_references_never_mutate_shared_input_fixtures(self):
        for q in self.quests:
            f=q.reference()
            for sample in q.samples:
                original=copy.deepcopy(sample);f(sample)
                self.assertEqual(sample,original,q.key)

    def check(self,key,values):
        f=self.by_key[key].reference()
        for data,expected in values:
            self.assertEqual(f(copy.deepcopy(data)),expected,(key,data))

    def test_hand_checked_puzzle_answers(self):
        golden={
            'elevator_skip':[(104,93),(4,3)],
            'sleepy_clock':[(-1,'23:59'),(1441,'00:01')],
            'clock_angle':[([3,0],180),([12,30],330)],
            'snail_day':[([10,3,2],8)],
            'snake_seat':[([2,4,1],8)],
            'inside_quotes':[("'hi'",'hi')],
            'cups_rest':[(6,3)],
            'backspace_scroll':[('ab#c##d','d')],
            'escaped_separator':[(r'a\|b|c',['a|b','c']),(r'a\\|b',['a\\','b'])],
            'roman_tokens':[('MCMXCIV',1994)],
            'isbn_checksum':[('030640615','2')],
            'luhn_tail':[('7992739871',3)],
            'near_palindrome':[('abca',True),('abcd',False)],
            'nested_quotes_extract':[('x "a" y "b"','b'),('"a" "b','a')],
            'carry_flashes':[(['999','1'],3)],
            'matrix_spiral_peel':[([[1,2],[3,4]],[1,2,4,3])],
            'matrix_gravity':[([[1,0],[0,2]],[[0,0],[1,2]])],
            'rect_union_two':[([[0,0,2,2],[1,1,3,3]],7)],
            'grid_corner_squares':[([[i,j] for i in range(3) for j in range(3)],5)],
            'cyclic_adjacent_merge':[([1,2,1],[[1,2],[2,1]])],
            'refund_machine':[([5,5,10,20],True)],
            'josephus_names':[([list('abcde'),3],list('caebd'))],
            'max_sum_one_erasure':[([1,-2,0,3],4)],
            'circular_max_sum':[([5,-3,5],10)],
            'three_equal_parts':[([0,0,0,0],3)],
            'distinct_subarray_sum':[([1,2],4)],
            'minimum_window_multiset':[(['ADOBECODEBANC','ABC'],'BANC')],
            'word_break_count':[(['aaaa',['a','aa']],5)],
            'expression_plus_minus':[('(-4)-(-2)',-2)],
            'minimum_turn_grid':[([[0,0],[0,0]],1)],
            'stairs_no_repeat':[(3,3)],
            'coin_exact_count':[([4,2,[1,2,3]],2)],
            'derangement_badges':[(4,9)],
            'colored_fence':[([3,2],6)],
            'fraction_decimal_cycle':[([1,6],'0.1(6)')],
            'capacity_flow':[([4,[[0,1,4],[0,2,3],[1,3,2],[2,3,5]]],5)],
            'strong_augmentation':[([3,[[0,1],[1,2]]],1)],
            'blocked_queens':[([4,[]],2)],
            'toroidal_queens':[(5,10)],
            'domino_holes':[([[0,0],[0,0]],2)],
            'tromino_strip':[(3,5)],
            'assignment_min_cost':[([[1,9],[9,1]],2)],
            'game_twentyfour':[([3,3,8,8],True)],
            'wildcard_digit_decode':[('**',96)],
            'distinct_subsequence_count':[('aba',6)],
            'distinct_pal_subsequence':[('bccb',6)],
            'general_crt':[([[2,3],[3,5]],[8,15])],
            'floor_sum_euclid':[([5,3,2,1],7)],
            'pell_minimum':[(13,[649,180])],
            'last_nonzero_factorial':[(10,8)],
            'permutation_inversion_count':[([3,1],2)],
            'burst_balloons':[([3,1,5,8],167)],
            'remove_boxes':[([1,3,2,2,2,3,4,3,1],23)],
            'strange_printer':[('aba',2)],
            'egg_dropping':[([2,100],14)],
            'bridge_torch':[([1,2,5,10],17)],
            'river_conflict_boat':[([3,[[0,1],[1,2]]],7)],
            'sliding_puzzle_six':[([[4,1,2],[5,0,3]],5)],
            'stick_cut_order':[([7,[1,3,4,5]],16)],
            'minimum_square_tiling':[([6,7],5)],
            'quadtree_error_budget':[([[[0,1],[1,0]],0],5),([[[0,1],[1,0]],2],1)],
        }
        for key,values in golden.items():
            if values:self.check(key,values)

    def test_flow_against_exhaustive_cuts(self):
        f=self.by_key['capacity_flow'].reference();rng=random.Random(7)
        for _ in range(60):
            n=rng.randrange(2,7);edges=[[a,b,rng.randrange(1,8)] for a in range(n) for b in range(n) if a!=b and rng.random()<.25]
            expected=min(sum(w for a,b,w in edges if mask>>a&1 and not mask>>b&1) for mask in range(1<<n) if mask&1 and not mask>>(n-1)&1)
            self.assertEqual(f([n,edges]),expected)

    def test_array_optimisations_against_exhaustive_search(self):
        rng=random.Random(82)
        for _ in range(80):
            a=[rng.randrange(-4,5) for _ in range(rng.randrange(0,8))]; n=len(a)
            if n:
                erased=max(sum(a[i:j])-a[k] if k is not None else sum(a[i:j]) for i in range(n) for j in range(i+1,n+1) for k in [None]+(list(range(i,j)) if j-i>1 else []))
                self.check('max_sum_one_erasure',[(a,erased)])
                circular=max(sum((a*2)[i:i+length]) for i in range(n) for length in range(1,n+1))
                self.check('circular_max_sum',[(a,circular)])
            target=rng.randrange(-3,9)
            shortest=min((j-i for i in range(n) for j in range(i+1,n+1) if sum(a[i:j])>=target),default=-1)
            self.check('short_subarray_target',[([target,a],shortest)])
            k=rng.randrange(0,4); best=0
            for mask in range(1<<n):
                runs=sum(mask>>i&1 and (i==0 or not mask>>(i-1)&1) for i in range(n))
                if runs<=k:best=max(best,sum(a[i] for i in range(n) if mask>>i&1))
            self.check('k_nonoverlap_segments',[([k,a],best)])

    def test_number_theory_against_direct_enumeration(self):
        rng=random.Random(45)
        for _ in range(60):
            n=rng.randrange(0,300);s=rng.randrange(0,20)
            self.check('digit_sum_limit',[([n,s],sum(sum(map(int,str(x)))==s for x in range(n+1)))])
            self.check('no_repeated_decimal',[(n,sum(len(set(str(x)))==len(str(x)) for x in range(n+1)))])
            self.check('binary_no_adjacent_ones',[(n,sum('11' not in bin(x) for x in range(n+1)))])
            a=rng.randrange(0,30);b=rng.randrange(0,30)
            self.check('coprime_grid_pairs',[([a,b],sum(math.gcd(x,y)==1 for x in range(1,a+1) for y in range(1,b+1)))])
            m=rng.randrange(1,30);a=rng.randrange(0,50);b=rng.randrange(0,50)
            self.check('floor_sum_euclid',[([n,m,a,b],sum((a*i+b)//m for i in range(n)))])

    def test_lights_out_against_button_subsets(self):
        f=self.by_key['lights_out'].reference()
        for bits in range(16):
            board=[[(bits>>(i*2+j))&1 for j in range(2)] for i in range(2)]; best=5
            for pressed in range(16):
                a=copy.deepcopy(board)
                for cell in range(4):
                    if pressed>>cell&1:
                        i,j=divmod(cell,2)
                        for x,y in ((i,j),(i-1,j),(i+1,j),(i,j-1),(i,j+1)):
                            if 0<=x<2 and 0<=y<2:a[x][y]^=1
                if not any(map(any,a)):best=min(best,pressed.bit_count())
            self.assertEqual(f(board),best if best<5 else -1)


if __name__=='__main__':unittest.main()
