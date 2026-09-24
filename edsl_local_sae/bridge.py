"""Run real EDSL questions through a shared local inference runtime.

The fixed batch is preflighted with EDSL before its first model callback triggers
generation. Every callback is matched to a preflighted prompt; no arrival-order
batching or cross-condition intervention state is used.
"""
import ast
import asyncio
import copy
from importlib.metadata import version
import logging
import threading
from typing import Any

# The pinned EDSL logger otherwise creates a global ~/.edsl log at import.
# This standalone adapter keeps its evidence in the selected output directory.
if not logging.getLogger('edsl').handlers:
    logging.getLogger('edsl').addHandler(logging.NullHandler())

from edsl import Agent, AgentList, Cache, QuestionMultipleChoice, Scenario, Survey
from edsl.key_management import KeyLookup
from edsl.language_models import LanguageModel
from edsl.language_models.price_manager import ResponseCost

from label_pilot.common import append, digest
from paper_replication.common import parse_answer

if version('edsl') != '1.0.8':
    raise RuntimeError('This adapter is verified with edsl==1.0.8')

_INFERENCE_LOCK = threading.Lock()


def prompt_key(system, user):
    return digest({'system': system, 'user': user})


class FixedBatch:
    """One frozen condition, seed and ordered batch; one GPU generation call."""
    def __init__(self, runtime, rows, seed, *, zero=False, max_new_tokens=None,
                 raw_path=None, engineering_only=False):
        if not rows:
            raise ValueError('Empty batch')
        self.rows = copy.deepcopy(rows)
        first = self.rows[0]
        if first['generation'].get('frequency_penalty', 0) != 0 or first['generation'].get('presence_penalty', 0) != 0:
            raise ValueError('This local runtime only supports the original zero penalties')
        if first['condition'] == 'baseline' and first['edits']:
            raise ValueError('A baseline cannot have SAE edits')
        for row in self.rows:
            if any(row[k] != first[k] for k in ('game', 'condition', 'edits', 'generation', 'user_prompt')):
                raise ValueError('Batch mixes game, condition, prompts, edits or generation settings')
        self.by_prompt = {prompt_key(r['system_prompt'], r['user_prompt']): r for r in self.rows}
        if len(self.by_prompt) != len(self.rows):
            raise ValueError('Prompts must uniquely identify trials within a batch')
        if len({r['id'] for r in self.rows}) != len(self.rows):
            raise ValueError('Duplicate trial IDs')
        self.runtime, self.seed, self.zero = runtime, seed, zero
        self.max_new_tokens = max_new_tokens or first['generation']['max_new_tokens']
        self.raw_path, self.engineering_only = raw_path, engineering_only
        self.ready = False
        self.outputs = None
        self.seen = set()
        self.lock = threading.Lock()

    def validate_prompts(self, prompts):
        actual = [prompt_key(str(p['system_prompt']), str(p['user_prompt'])) for p in prompts]
        if len(actual) != len(self.rows) or set(actual) != set(self.by_prompt):
            raise ValueError('EDSL prompts differ from the frozen requests; inference blocked')
        self.ready = True
        return actual

    def call(self, system, user):
        with self.lock:
            key = prompt_key(system, user)
            if not self.ready or key not in self.by_prompt:
                raise ValueError('Unverified EDSL model request; inference blocked')
            row = self.by_prompt[key]
            if row['id'] in self.seen:
                raise ValueError('Unexpected repeat/retry; no additional generation allowed')
            if self.outputs is None:
                # Hooks and RNG state are mutable; serialize across batches even
                # if callers use different Python threads or model copies.
                with _INFERENCE_LOCK:
                    outputs = self.runtime.generate_batch(self.rows, self.seed, zero=self.zero,
                                                           max_new_tokens=self.max_new_tokens)
                if len(outputs) != len(self.rows):
                    raise ValueError('Runtime returned the wrong batch size')
                self.outputs = dict(zip([r['id'] for r in self.rows], outputs))
                if self.raw_path:
                    for source, result in zip(self.rows, outputs):
                        append(self.raw_path, dict(id=source['id'], game=source['game'],
                            condition=source['condition'], value=source['value'],
                            agent_index=source['agent_index'], prompt_sha256=prompt_key(source['system_prompt'], source['user_prompt']),
                            requested_edits=source['edits'], zero_edit=self.zero,
                            max_new_tokens=self.max_new_tokens, engineering_only=self.engineering_only,
                            mock=bool(getattr(self.runtime, 'mock', False)),
                            parse=parse_answer(source['game'], result['response']), **result))
            self.seen.add(row['id'])
            result = self.outputs[row['id']]
            # Preserve any invalid raw answer in the ledger, then fail visibly.
            # This bridge does not silently repair, relabel, or drop responses.
            if not parse_answer(row['game'], result['response'])['valid']:
                raise ValueError('Invalid first-line answer; raw batch retained for review')
            return dict(choices=[{'message': {'role': 'assistant', 'content': result['response']}}],
                usage={'prompt_tokens': result['input_tokens'], 'completion_tokens': result['generated_tokens']},
                local_sae=dict(trial_id=row['id'], backend='synthetic_cpu_check' if getattr(self.runtime, 'mock', False) else 'local_transformers',
                    prompt_sha256=key, zero_edit=self.zero, seed=self.seed, batch_size=len(self.rows),
                    max_new_tokens=self.max_new_tokens, edits=row['edits'], trace=result['trace']))


class LocalSAEModel(LanguageModel):
    _model_ = 'local-llama-3.3-70b-instruct-sae-l50'
    # EDSL 1.0.8 has a closed service enum. "test" is its in-process slot;
    # this custom class calls our runtime, never EDSL's canned TestService.
    # local_sae.backend and the run manifest distinguish GPU vs synthetic runs.
    _inference_service_ = 'test'
    _parameters_ = {'temperature': .5, 'top_p': 1., 'max_tokens': 1000,
                    'local_batch_identity': '', 'local_zero_edit': False}
    key_sequence = ['choices', 0, 'message', 'content']
    usage_sequence = ['usage']
    input_token_name = 'prompt_tokens'
    output_token_name = 'completion_tokens'

    def __init__(self, backend):
        self.backend = backend
        g = backend.rows[0]['generation']
        super().__init__(key_lookup=KeyLookup(), skip_api_key_check=True,
            rpm=1000000, tpm=1000000000, temperature=g['temperature'], top_p=g['top_p'],
            max_tokens=backend.max_new_tokens, local_zero_edit=backend.zero,
            local_batch_identity=digest({'rows': backend.rows, 'seed': backend.seed, 'mock': bool(getattr(backend.runtime, 'mock', False))}))

    def copy(self):
        return type(self)(self.backend)

    def __deepcopy__(self, memo):
        return self.copy()

    def cost(self, raw_response):
        # No per-token API billing or remote price lookup. GPU rental is separate.
        usage = raw_response['usage']
        return ResponseCost(input_tokens=usage['prompt_tokens'], output_tokens=usage['completion_tokens'],
                            input_price_per_million_tokens=0., output_price_per_million_tokens=0., total_cost=0.)

    async def async_execute_model_call(self, user_prompt: str, system_prompt: str,
                                       files_list=None, **kwargs) -> dict[str, Any]:
        if self.remote or files_list:
            raise ValueError('Only local text inference is supported')
        return self.backend.call(system_prompt, user_prompt)


def make_job(backend):
    first = backend.rows[0]
    game = first['game']
    if game not in ('lottery', 'ultimatum'):
        raise ValueError('Unsupported game')
    name = 'safe_risky_choice' if game == 'lottery' else 'ultimatum_response'
    options = ['Safe Option', 'Risky Option'] if game == 'lottery' else ['Accept', 'Reject']
    # The saved prompt already includes EDSL's historical option/rationale text.
    # Explicit templates prevent a newer EDSL release from adding it a second time.
    question = QuestionMultipleChoice(question_name=name, question_text=first['user_prompt'],
        question_options=options, question_presentation='{{ question_text }}', answering_instructions='',
        include_comment=True, use_code=False, permissive=False)
    agents = []
    for row in backend.rows:
        system = row['system_prompt']
        prefix = 'Your traits: '
        if not system.startswith(prefix):
            raise ValueError('Unsupported historical system-prompt format')
        traits = ast.literal_eval(system[len(prefix):])
        if not isinstance(traits, dict):
            raise ValueError('Expected a trait dictionary')
        agents.append(Agent(name=row['id'], traits=traits, instruction=''))
    model = LocalSAEModel(backend)
    survey = Survey([question])
    prompts = [a.create_invigilator(question=question, scenario=Scenario({}), model=model,
                    survey=survey, cache=Cache()).get_prompts() for a in agents]
    hashes = backend.validate_prompts(prompts)
    return survey.by(AgentList(agents)).by(model), name, hashes


async def run_batch_async(backend):
    job, name, hashes = make_job(backend)
    # Both old and new switches are required by this pinned EDSL release.
    results = await job.run_async(cache=False, disable_remote_inference=True,
        disable_remote_cache=True, offload_execution=False, use_api_proxy=False,
        check_api_keys=False, skip_retry=True, raise_validation_errors=True,
        stop_on_exception=True, progress_bar=False, verbose=False, fresh=True)
    data = results.to_dict()
    if len(data['data']) != len(backend.rows) or backend.seen != {r['id'] for r in backend.rows}:
        raise ValueError('EDSL dropped, duplicated, or bypassed a local model call')
    expected = {r['id']: r for r in backend.rows}
    checked = set()
    for result in data['data']:
        raw = result['raw_model_response'][name + '_raw_model_response']
        rid = raw['local_sae']['trial_id']
        if rid in checked:
            raise ValueError('Duplicate EDSL result')
        checked.add(rid)
        parsed = parse_answer(expected[rid]['game'], backend.outputs[rid]['response'])
        if result['answer'][name] != parsed['answer']:
            raise ValueError('EDSL answer differs from the generated first-line choice')
        if result['cache_used_dict'].get(name) is not False:
            raise ValueError('Unexpected EDSL cache reuse')
    return data


def run_batch(backend):
    return asyncio.run(run_batch_async(backend))
