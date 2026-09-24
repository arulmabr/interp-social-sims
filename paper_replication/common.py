import hashlib
import json
import re
from pathlib import Path

from label_pilot.common import read, write, append, digest, file_hash
from label_pilot.run import records

ROOT = Path(__file__).resolve().parent


def sources():
    return {str(p.relative_to(ROOT.parent)): file_hash(p)
            for folder in (ROOT, ROOT.parent/'label_pilot') for p in sorted(folder.glob('*.py'))}


def load_plan(path):
    path = Path(path)
    plan = read(path/'plan.json')
    content = {k:v for k,v in plan.items() if k!='plan_hash'}
    if digest(content) != plan['plan_hash']:
        raise ValueError('Plan hash mismatch')
    if file_hash(path/'requests.jsonl') != plan['requests_sha256']:
        raise ValueError('Request checksum mismatch')
    return plan


def parse_answer(game, response):
    """Parse an explicit first-line choice, never a mention inside the rationale."""
    options = ('Safe Option','Risky Option') if game=='lottery' else ('Accept','Reject')
    value=response.strip()
    if value.startswith('{'):
        try:
            answer=json.loads(value).get('answer')
            if isinstance(answer,str): value=answer
        except (ValueError,AttributeError): pass
    line=value.splitlines()[0].strip() if value else ''
    line=re.sub(r'^(?:answer|choice)\s*:\s*','',line,flags=re.I)
    line=line.strip(' \t"\'`*').rstrip('.!').strip()
    for option in options:
        if line.casefold()==option.casefold():
            return dict(valid=True,answer=option,target=int(option==options[1] if game=='lottery' else option==options[0]))
    return dict(valid=False,answer=None,target=None)


def batch_seed(game,value,start,base=20260924):
    # Common random numbers across conditions; exact replay requires fixed batches.
    return (int(hashlib.sha256(f'{game}:{value}:{start}:{base}'.encode()).hexdigest()[:8],16)+base)%(2**31)


def make_batches(rows,batch_size):
    from collections import defaultdict
    groups=defaultdict(list)
    for row in rows: groups[(row['game'],row['value'],row['condition'])].append(row)
    # Fix a broad-coverage schedule before seeing outcomes. Start at each game's
    # midpoint, then endpoints, then fill the largest remaining gaps. Prioritize
    # matched baseline/steering cells in both games within each coverage round.
    ranks={}
    for game in {key[0] for key in groups}:
        values=sorted({key[1] for key in groups if key[0]==game})
        midpoint=(values[0]+values[-1])/2
        ordered=[min(values,key=lambda v:(abs(v-midpoint),v))]
        while len(ordered)<len(values):
            remaining=[v for v in values if v not in ordered]
            ordered.append(max(remaining,key=lambda v:(min(abs(v-x)for x in ordered),-v)))
        ranks.update({(game,value):i for i,value in enumerate(ordered)})
    priorities={name:i for i,name in enumerate(('baseline','steering','lite_steering','prompting','barely_prompting','slightly_prompting'))}
    for key,group in sorted(groups.items(),key=lambda item:(ranks[item[0][:2]],priorities[item[0][2]],item[0][0])):
        group.sort(key=lambda r:r['agent_index'])
        for i in range(0,len(group),batch_size):
            yield group[i:i+batch_size],batch_seed(key[0],key[1],i)
