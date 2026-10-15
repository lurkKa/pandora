import copy
import json
import os
import random
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.generate_python_expansion import PACK, build_tasks, curriculum
from task_shapes import public_task


class PythonExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks=build_tasks()
        cls.problems=curriculum()

    def test_exact_counts_unique_missions_and_no_hidden_answers_in_public_payload(self):
        self.assertEqual(Counter(t['tier'] for t in self.tasks),{tier:200 for tier in 'DCBAS'})
        self.assertEqual(len(set(t['id'] for t in self.tasks)),1000)
        self.assertEqual(len(set(t['title'] for t in self.tasks)),1000)
        for task in self.tasks:
            self.assertLessEqual(len(task['title']),40)
            self.assertGreaterEqual(len(task['check_logic']['cases']),3)
            self.assertGreaterEqual(len(task['check_logic']['hidden_cases']),5)
            self.assertNotIn('check_logic',public_task(task))
            self.assertNotIn('hidden_cases',public_task(task))
            self.assertIn('Примеры:',task['description'])
            outputs={json.dumps(c['expected'],sort_keys=True) for c in task['check_logic']['cases']+task['check_logic']['hidden_cases']}
            self.assertGreater(len(outputs),1,task['id'])

    def test_pack_on_disk_matches_generator(self):
        data=json.loads((ROOT/'tasks.json').read_text())
        pack=[t for t in data['tasks'] if t.get('source_pack')==PACK]
        self.assertEqual(pack,self.tasks)
        self.assertEqual(len({t['id'] for t in data['tasks']}),len(data['tasks']))

    def test_all_reference_inputs_are_preserved(self):
        for p in self.problems:
            f=p.reference()
            for data in p.inputs:
                original=copy.deepcopy(data)
                if p.tier=='D': f(*data)
                else: f(data)
                self.assertEqual(data,original,p.key)

    def test_all_1000_missions_in_real_python_runner(self):
        # Each curriculum problem runs in its own resource-limited subprocess.
        # All eight mission objectives and all visible/hidden fixtures are checked.
        by_id={t['id']:t for t in self.tasks}
        projections_d=[
            'v','v*2','v+b','v-a','[v//7,v%7]','str(v).zfill(4)',
            '{"value":v,"above_limit":v>a}', 'f"R={v};K={v%b}"',
        ]
        project_source='''
def project(v, mode):
    if mode==0: return v
    if mode==1: return {"count":len(v),"total":sum(v)}
    if mode==2: return [min(v),max(v)] if v else [0,0]
    if mode==3: return sum(i*x for i,x in enumerate(v,1))
    if mode==4: return [i for i,x in enumerate(v) if x!=0]
    if mode==5:
        out=[]; total=0
        for x in v: total+=x; out.append(total)
        return out
    if mode==6:
        out=[]
        for x in v:
            if out and out[-1][0]==x: out[-1][1]+=1
            else: out.append([x,1])
        return out
    return [[x,v.count(x)] for x in sorted(set(v))]
'''
        for p in self.problems:
            code='import math, bisect, heapq\nfrom collections import Counter, deque\n'
            code+='def compute('+p.signature+'):\n'+'\n'.join('    '+line for line in p.body.splitlines())+'\n'
            code+=project_source
            cases=[]
            for mode in range(8):
                if p.tier=='D':
                    code+=f'def solve_{mode}(a,b):\n    v=compute(a,b)\n    return {projections_d[mode]}\n'
                else:
                    code+=f'def solve_{mode}(data):\n    return project(compute(data),{mode})\n'
                task=by_id[f'py_expedition_{p.tier.lower()}_{p.key}_{mode+1:02d}']
                for case in task['check_logic']['cases']+task['check_logic']['hidden_cases']:
                    cases.append({**case,'code':case['code'].replace('solve(',f'solve_{mode}(',1)})
            result=subprocess.run([sys.executable,str(ROOT/'runners/python_harness.py')],input=json.dumps({'code':code,'cases':cases}),text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,(p.key,result.stderr))
            output=json.loads(result.stdout)
            self.assertTrue(output['passed'],(p.key,output.get('exec_error'),[c for c in output['cases'] if not c['passed']][:2]))

    def test_scc_and_distances_against_independent_transitive_closure(self):
        problems={p.key:p for p in self.problems if p.tier=='S'}
        for g in problems['scc'].inputs:
            n=g['n']; d=[[10**9]*n for _ in range(n)]
            for i in range(n):d[i][i]=0
            for u,v,w in g['edges']: d[u][v]=min(d[u][v],w)
            for k in range(n):
                for i in range(n):
                    for j in range(n): d[i][j]=min(d[i][j],d[i][k]+d[k][j])
            remaining=set(range(n)); sizes=[]
            while remaining:
                i=min(remaining)
                group={j for j in remaining if d[i][j]<10**9 and d[j][i]<10**9}
                sizes.append(len(group));remaining-=group
            self.assertEqual(problems['scc'].reference()(g),sorted(sizes))
            expected=[-1 if x==10**9 else x for x in d[0]] if n else []
            self.assertEqual(problems['dijkstra'].reference()(g),expected)

    def test_monotonic_algorithms_against_brute_force(self):
        problems={p.key:p for p in self.problems if p.tier=='A'}
        rng=random.Random(42)
        for _ in range(80):
            a=[rng.randrange(-5,6) for _ in range(rng.randrange(0,14))]
            expected=[sum(min(a[l:r+1]) for l in range(r+1)) for r in range(len(a))]
            self.assertEqual(problems['subarray_min'].reference()(a),expected)
            expected=[max(sum(a[l:r+1]) for l in range(r+1)) for r in range(len(a))]
            self.assertEqual(problems['kadane'].reference()(a),expected)
            heights=list(map(abs,a));expected=[]
            for i,x in enumerate(heights):
                width=max((r-l+1 for l in range(i+1) for r in range(i,len(a)) if min(heights[l:r+1])>=x),default=0)
                expected.append(x*width)
            self.assertEqual(problems['histogram'].reference()(a),expected)


if __name__=='__main__': unittest.main()
