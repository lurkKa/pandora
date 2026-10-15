"""500 independently specified Python quests; no output-mode multiplication."""
from dataclasses import dataclass
import bisect
import collections
import copy
import functools
import heapq
import itertools
import math
import re

PACK = 'python_oddities_500_20261015'


@dataclass
class Quest:
    tier: str
    key: str
    title: str
    contract: str
    source: str
    samples: list
    topic: str

    def solution(self):
        from .support import COMMON
        return 'import math, re, heapq, bisect, itertools, functools, collections\nfrom collections import Counter, defaultdict, deque\n' + (COMMON if self.tier=='S' else '') + 'def solve(data):\n' + '\n'.join('    '+line for line in self.source.splitlines()) + '\n'

    def reference(self):
        env = {}
        exec(self.solution(), env)
        return env['solve']


def register(tier):
    quests = []
    def add(key, title, contract, source, samples, topic='algorithms'):
        if len(samples) < 8:
            raise ValueError(f'{key}: need at least eight deliberately chosen inputs')
        quests.append(Quest(tier,key,title,contract,source,samples,topic))
    return quests, add


def all_quests():
    from . import tier_d, tier_c, tier_b, tier_a, tier_s
    return [q for module in (tier_d,tier_c,tier_b,tier_a,tier_s) for q in module.quests()]
