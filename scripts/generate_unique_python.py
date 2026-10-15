#!/usr/bin/env python3
"""Compile 500 separately authored contracts and their verification fixtures.

Shared scaffolding adds examples/resources only. Each quest has its own algorithm,
input contract, reference implementation and selected edge cases.
"""
import ast
import copy
import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.unique_python import PACK, all_quests


def build_tasks():
    quests=all_quests()
    assert Counter(q.tier for q in quests)=={t:100 for t in 'DCBAS'}
    assert len({q.key for q in quests})==500
    sources=[ast.dump(ast.parse(q.source)) for q in quests]
    assert len(set(sources))==500, 'Repeated solver: write a separate problem, not a reporting variant'
    tasks=[]
    for q in quests:
        reference=q.reference()
        cases=[]
        for original in q.samples:
            data=copy.deepcopy(original)
            result=reference(data)
            assert data==original, f'{q.key}: reference mutates input'
            # Round-trip guards against sets, tuples, infinities and unsafe integers.
            def json_value(v):
                if isinstance(v,bool) or v is None or isinstance(v,str):return
                if isinstance(v,int):
                    assert abs(v)<=2**53-1,(q.key,'unsafe integer',v);return
                if isinstance(v,list):
                    for item in v:json_value(item)
                    return
                if isinstance(v,dict):
                    assert all(isinstance(k,str) for k in v),(q.key,'non-string keys')
                    for item in v.values():json_value(item)
                    return
                raise AssertionError((q.key,'non JSON result',type(v)))
            json_value(result)
            cases.append({'code':f'solve({original!r})','expected':result})
        assert len({json.dumps(c['expected'],sort_keys=True) for c in cases})>1,(q.key,'constant fixtures')
        encoded=[json.dumps(c['expected'],sort_keys=True) for c in cases]
        second=next(i for i,x in enumerate(encoded) if x!=encoded[0])
        third=max((i for i in range(len(cases)) if i not in (0,second)),key=lambda i:len(json.dumps(q.samples[i],ensure_ascii=False)))
        visible_indices=[0,second,third]
        visible=[cases[i] for i in visible_indices]
        hidden=[c for i,c in enumerate(cases) if i not in visible_indices]
        description=(f'Реализуй функцию `solve(data)`.\n\n{q.contract}\n\n'
                     'Верни результат через return. Не изменяй входные данные. '
                     'Индексы начинаются с нуля, если в условии не указано иначе.\n\nПримеры:\n'+
                     '\n'.join(f"{c['code']} → {c['expected']!r}" for c in visible)+
                     '\n\nВ объяснении укажи правила обработки данных, алгоритм и граничный случай.')
        tasks.append({'id':f'py_oddity_{q.tier.lower()}_{q.key}', 'category':'python','tier':q.tier,'topic':q.topic,
                      'xp':{'D':25,'C':70,'B':160,'A':315,'S':550}[q.tier],
                      'title':q.title,'story':q.title+'. Исследуй необычное правило и создай работающий алгоритм.',
                      'description':description,'initial_code':'def solve(data):\n    # Прочитай контракт входа и результата в условии.\n    pass\n',
                      'resources':{'docs':[{'title':'Python: официальный учебник','url':'https://docs.python.org/3/tutorial/'}],
                                   'videos':[{'title':'Python: курс freeCodeCamp (EN)','url':'https://www.youtube.com/watch?v=rfscVS0vtbw'}]},
                      'check_logic':{'engine':'pyodide','cases':visible,'hidden_cases':hidden},'source_pack':PACK})
    assert len({t['title'] for t in tasks})==500
    return tasks


def main():
    path=ROOT/'tasks.json';data=json.loads(path.read_text());new=build_tasks()
    existing=[t for t in data['tasks'] if t.get('source_pack')!=PACK]
    assert not ({t['id'] for t in existing}&{t['id'] for t in new})
    # Existing tasks and their order stay intact; this pack is independently reproducible.
    data['tasks']=existing+new
    data['meta'][PACK]={'total':500,'per_tier':100,'independent_contracts':500}
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    catalog=['# 500 самостоятельных задач Python', '',
             'По 100 задач D, C, B, A и S. Каждая строка ниже — самостоятельный контракт, '
             'а не вариант оформления ответа другой задачи. Примеры и скрытые проверки находятся в tasks.json.', '']
    for tier in 'DCBAS':
        catalog.extend([f'## Ранг {tier}', ''])
        for q in (q for q in all_quests() if q.tier==tier):
            catalog.append(f'- **{q.title}** (`py_oddity_{tier.lower()}_{q.key}`). {q.contract}')
        catalog.append('')
    (ROOT/'docs'/'python_unique_500.md').write_text('\n'.join(catalog))
    print('Added 500 independently specified Python tasks (100 per tier).')


if __name__=='__main__':main()
