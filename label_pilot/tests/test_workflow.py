import io
import tarfile
from types import SimpleNamespace

import pytest

from label_pilot import prepare as preparation
from label_pilot import runtime
from label_pilot.common import digest, file_hash, read, write
from label_pilot.design import build_rows
from label_pilot.run import execute, records
from label_pilot.analyze import analyze, lock_selection
from label_pilot.deploy import source_archive, attach
from label_pilot import deploy


@pytest.fixture
def plan(tmp_path, monkeypatch):
    csv = tmp_path/'labels.csv'
    csv.write_text('id,label,index_in_sae\na,taking risks,1\nb,altruistic selfless,2\nc,fairness equality,3\nd,creative innovation,4\n')
    # Small real prompt subset: runner orchestration, not experimental evidence.
    rows, counts = [], {}
    for row in build_rows():
        key = row['construct'], row['split'], row['covariates'].get('offer_stratum')
        counts[key] = counts.get(key, 0) + 1
        if counts[key] <= 4:
            rows.append(row)
    monkeypatch.setattr(preparation, 'build_rows', lambda: rows)
    path = tmp_path/'plan'; preparation.prepare(csv, path, 1)
    return path


class FakeRuntime:
    def __init__(self, features):
        self.features = sorted(set(features)); self.metadata = {'test_double': True}

    def activations(self, row):
        examples = [dict(feature_id=f, activation=2.0, scope='user_content',
                         row_id=row['id'], split=row['split'], scenario_id=row['scenario_id'],
                         token_position=1, token='synthetic', context='test context', sampling='top')
                    for f in self.features]
        return {str(f): 2.0 for f in self.features}, examples

    def evaluate(self, row, condition, max_new_tokens):
        if row['kind'] == 'generation':
            return {'response': 'synthetic test response', 'generated_tokens': 3,
                    'quality_score': None, 'elapsed_seconds': .01}
        effect = condition.get('actual_delta', 0) / 20
        return {'p_target': .5 + effect, 'answer_mass': .99, 'elapsed_seconds': .01}


def test_complete_stage_workflow_and_completed_resume(plan, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'Runtime', FakeRuntime)
    def args(stage, **kw):
        return SimpleNamespace(plan=plan, output=tmp_path/stage, stage=stage,
                               max_seconds=100, resume=False, calibration=kw.get('calibration'), lock=kw.get('lock'))
    assert execute(args('smoke'))['status'] == 'completed'
    assert execute(args('harvest'))['status'] == 'completed'
    calibration = tmp_path/'harvest/calibration.json'
    assert read(calibration)['split'] == 'discovery'
    assert execute(args('selection', calibration=calibration))['status'] == 'completed'
    lock = tmp_path/'lock.json'
    locked = lock_selection(plan, tmp_path/'selection', calibration, lock)
    assert all('zero_edit' in v for v in locked['conditions'].values())
    confirmation = args('confirm', calibration=calibration, lock=lock)
    assert execute(confirmation)['status'] == 'completed'
    report = analyze(plan, tmp_path/'confirm', tmp_path/'report.json')
    assert report['zero_edit_exact'] is True
    assert all(s['split'] == 'frozen' for s in records(tmp_path/'confirm/scores.jsonl'))
    confirmation.resume = True
    monkeypatch.setattr(runtime, 'Runtime', lambda _: pytest.fail('Completed resume must not load the model'))
    assert execute(confirmation)['status'] == 'completed'


def test_incomplete_selection_cannot_be_locked(plan, tmp_path):
    protocol = read(plan/'plan.json')
    calibration = tmp_path/'calibration.json'
    write(calibration, {'features': {str(f): {'scale': 2.0} for f in range(1,5)}})
    run = tmp_path/'selection'; run.mkdir()
    write(run/'run.json', {'status':'completed', 'identity': {'stage':'selection',
          'plan_hash':protocol['plan_hash'], 'calibration_sha256':file_hash(calibration)}})
    (run/'scores.jsonl').write_text('')
    with pytest.raises(ValueError, match='cover exactly'):
        lock_selection(plan, run, calibration, tmp_path/'lock.json')


def test_upload_archive_is_allowlisted_and_contains_no_catalog_or_credentials(plan):
    package = source_archive(plan)
    with tarfile.open(fileobj=io.BytesIO(package)) as archive:
        names = archive.getnames()
    assert 'plan/plan.json' in names and 'label_pilot/runtime.py' in names
    assert not any(any(part in name for part in ('.credentials', '.venv', 'sqlite', '.git/', '.csv')) for name in names)
    assert all(name.startswith(('plan/', 'label_pilot/')) for name in names)


def test_console_attach_rejects_oversized_budget_before_connecting(tmp_path):
    args = SimpleNamespace(host='example.invalid',port=22,pod_id='test',deadline='2099-01-01T00:00:00+00:00',
                           rate=9.18,budget=150)
    with pytest.raises(ValueError, match='budget'):
        attach(args)


def test_console_session_does_not_use_unverified_account_key(monkeypatch):
    monkeypatch.setattr(deploy, 'load_credentials', lambda: {'RUNPOD_API_KEY': 'test-only-placeholder'})
    assert not deploy.uses_account_api({'origin': 'console_deployment'})
    assert deploy.uses_account_api({'origin': 'api_deployment'})
