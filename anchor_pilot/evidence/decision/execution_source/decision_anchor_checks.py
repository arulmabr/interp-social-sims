"""Report the preceding repair's stricter recovery rule without changing the new rule."""
import argparse
import json
from pathlib import Path
from .repair_design import recovery_check
from .smoke import save_json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args();root=args.root
    rows=json.loads((root/'frozen_rows.json').read_text());scores=json.loads((root/'frozen_scores_lora.json').read_text())
    result={}
    for template in ('original','transfer'):
        ids=[i for i,r in enumerate(rows) if r['template']==template]
        result[template]=recovery_check([rows[i] for i in ids],[scores[i] for i in ids])
    save_json(root/'prior_anchor_rule_checks.json',result)
    print(json.dumps({t:{'passed':v['passed_operational_recovery_target'],'teacher_rmse':v['teacher_probability_rmse'],'parameters':v['fit']['parameters']} for t,v in result.items()},indent=2))


if __name__=='__main__':main()
