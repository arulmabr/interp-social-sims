import asyncio
import copy
import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from edsl_local_sae.bridge import FixedBatch, LocalSAEModel, make_job, run_batch
from edsl_local_sae.check import SyntheticRuntime, verify_guard
from paper_replication.common import batch_seed, parse_answer

FIXTURE = Path(__file__).parent/'fixtures/original_prompt_requests.jsonl'


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('The in-process adapter must not connect to a hosted service')
    monkeypatch.setattr(socket.socket, 'connect', denied)


@pytest.fixture(scope='module')
def rows():
    return [json.loads(s) for s in FIXTURE.read_text().splitlines()]


def subset(rows, game, condition):
    value = 100 if game == 'lottery' else 30
    return [r for r in rows if (r['game'], r['condition'], r['value']) == (game, condition, value)][:8]


@pytest.mark.parametrize('game', ['lottery', 'ultimatum'])
def test_real_edsl_routes_batches_and_resets_conditions(rows, game):
    runtime = SyntheticRuntime()
    for condition, zero in [('steering', False), ('baseline', False), ('steering', True), ('baseline', False)]:
        batch = subset(rows, game, condition)
        seed = batch_seed(game, batch[0]['value'], 0)
        backend = FixedBatch(runtime, batch, seed, zero=zero)
        job, _, _ = make_job(backend)
        assert isinstance(job.models[0].copy(), LocalSAEModel)
        result = run_batch(backend)
        assert len(result['data']) == 8
        call = runtime.calls[-1]
        assert call['ids'] == [r['id'] for r in batch]
        assert call['edits'] == batch[0]['edits']
        assert call['zero'] == zero
        assert call['seed'] == seed
        assert len(backend.seen) == 8
        assert all(parse_answer(game, x['response'])['valid'] for x in backend.outputs.values())
    assert len(runtime.calls) == 4  # exactly one generation per fixed eight-agent batch
    assert runtime.calls[1]['edits'] == runtime.calls[3]['edits'] == []


def test_unknown_prompt_and_missing_preflight_do_not_generate(rows):
    runtime = SyntheticRuntime()
    batch = subset(rows, 'ultimatum', 'baseline')
    b = FixedBatch(runtime, batch, 1)
    with pytest.raises(ValueError, match='Unverified'):
        b.call(batch[0]['system_prompt'], batch[0]['user_prompt'])
    make_job(b)
    with pytest.raises(ValueError, match='Unverified'):
        b.call(batch[0]['system_prompt'], batch[0]['user_prompt'] + ' Be altruistic.')
    assert runtime.calls == []


def test_duplicate_request_does_not_regenerate(rows):
    runtime = SyntheticRuntime()
    batch = subset(rows, 'ultimatum', 'steering')
    b = FixedBatch(runtime, batch, 1)
    make_job(b)
    b.call(batch[0]['system_prompt'], batch[0]['user_prompt'])
    with pytest.raises(ValueError, match='repeat/retry'):
        b.call(batch[0]['system_prompt'], batch[0]['user_prompt'])
    assert len(runtime.calls) == 1


def test_mixed_conditions_rejected(rows):
    batch = subset(rows, 'lottery', 'baseline')[:4] + subset(rows, 'lottery', 'steering')[4:]
    with pytest.raises(ValueError, match='mixes'):
        FixedBatch(SyntheticRuntime(), batch, 1)


def test_preflight_detects_changed_edsl_messages(rows):
    batch = subset(rows, 'lottery', 'baseline')
    backend = FixedBatch(SyntheticRuntime(), batch, 1)
    bad = [{'system_prompt': r['system_prompt'], 'user_prompt': r['user_prompt']} for r in batch]
    bad[-1]['system_prompt'] += ' Follow a different persona.'
    with pytest.raises(ValueError, match='prompts differ'):
        backend.validate_prompts(bad)
    assert not backend.ready


def test_invalid_output_is_retained_without_silent_relabeling(rows, tmp_path):
    class InvalidRuntime(SyntheticRuntime):
        def generate_batch(self, *args, **kwargs):
            result = super().generate_batch(*args, **kwargs)
            result[0]['response'] = 'I cannot choose an option.'
            return result
    runtime = InvalidRuntime()
    batch = subset(rows, 'ultimatum', 'baseline')
    path = tmp_path/'raw.jsonl'
    backend = FixedBatch(runtime, batch, 1, raw_path=path)
    make_job(backend)
    with pytest.raises(ValueError, match='Invalid first-line'):
        backend.call(batch[0]['system_prompt'], batch[0]['user_prompt'])
    saved = [json.loads(s) for s in path.read_text().splitlines()]
    assert len(saved) == 8
    assert saved[0]['parse']['valid'] is False
    assert saved[0]['mock'] is True


def test_model_refuses_remote_mode(rows):
    runtime = SyntheticRuntime()
    backend = FixedBatch(runtime, subset(rows, 'lottery', 'baseline'), 1)
    model = LocalSAEModel(backend)
    model.remote = True
    with pytest.raises(ValueError, match='local text'):
        asyncio.run(model.async_execute_model_call('test', 'test'))
    assert runtime.calls == []


def test_parameter_identity_distinguishes_zero_edit(rows):
    batch = subset(rows, 'ultimatum', 'steering')
    active = LocalSAEModel(FixedBatch(SyntheticRuntime(), batch, 1))
    zero = LocalSAEModel(FixedBatch(SyntheticRuntime(), batch, 1, zero=True))
    assert active.parameters != zero.parameters


def test_gpu_validation_requires_a_fresh_guard():
    with pytest.raises(ValueError, match='approved session'):
        verify_guard(None, None, None)
    with pytest.raises(ValueError, match='remaining'):
        verify_guard('pod', 1, '2020-01-01T00:00:00+00:00')


def test_distinct_batches_do_not_overlap_mutable_runtime_hooks(rows):
    class ConcurrentRuntime(SyntheticRuntime):
        active = 0
        max_active = 0
        def generate_batch(self, *args, **kwargs):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            time.sleep(.02)
            result = super().generate_batch(*args, **kwargs)
            self.active -= 1
            return result
    runtime = ConcurrentRuntime()
    backends = [FixedBatch(runtime, subset(rows, 'lottery', c), 1) for c in ('baseline', 'steering')]
    for backend in backends:
        make_job(backend)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(b.call, b.rows[0]['system_prompt'], b.rows[0]['user_prompt']) for b in backends]
        for future in futures:
            future.result()
    assert runtime.max_active == 1
