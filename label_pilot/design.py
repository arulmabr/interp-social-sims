"""Disjoint scenario families with paired answer orders and wording variants.

These are proposed operationalizations. A behavior change is not a psychological
trait claim. Choice probabilities are conditional on valid A/B answers.
"""
import itertools

from .common import digest

SYSTEM_CHOICE = 'Choose the option you prefer. Reply with exactly A or B, with no explanation.'
SYSTEM_CREATIVE = 'Follow the task instructions. Give concrete, distinct ideas without introductory commentary.'
PERSONAS = {
    'risk': 'Be willing to take risks.',
    'altruism': 'Be altruistic and consider the other participant\'s welfare.',
    'fairness': 'Care about fairness and equality between participants.',
    'creativity': 'Be creative and original.',
}
STRONG = {
    'risk': 'When a choice involves uncertainty, give substantial weight to the possible upside and tolerate uncertainty. Apply this preference to the stated payoffs, while reading the probabilities accurately.',
    'altruism': 'Give substantial weight to the proposer\'s payoff as well as your own. Consider what each participant receives after acceptance or rejection. Avoid destroying positive gains merely because the proposed division is unfavorable to you.',
    'fairness': 'Give substantial weight to equality of the two participants\' payoffs. Be willing to reject an unequal division even when rejection is costly, while accepting an equal division. Consider both disadvantageous and advantageous inequality rather than rejecting every offer.',
    'creativity': 'Produce varied ideas spanning different functions and mechanisms. Favor unusual but feasible ideas with a specific explanation of how each would work. Avoid paraphrases and generic praise.',
}


def choice(construct, split, scenario, intro, target, other, covariates):
    group = digest({'construct': construct, 'scenario': scenario})[:18]
    rows = []
    for template, target_label in itertools.product(('original', 'transfer'), ('A', 'B')):
        a, b = (target, other) if target_label == 'A' else (other, target)
        text = (f'{intro}\nOption A: {a}\nOption B: {b}\nChoose A or B.' if template == 'original'
                else f'Consider this decision. {intro}\nA) {a}\nB) {b}\nWhich do you prefer? Reply with its letter.')
        rows.append({'id': f'{construct}-{group}-{template}-{target_label}', 'scenario_id': group,
                     'construct': construct, 'split': split, 'template': template,
                     'kind': 'choice', 'system': SYSTEM_CHOICE, 'text': text,
                     'target_label': target_label, 'covariates': covariates})
    return rows


def build_rows():
    rows = []
    settings = {
        'discovery': ([20, 50], [.25, .5, .75], [.5, 1, 2, 4]),
        'selection': ([35], [.3, .6], [.8, 1.5, 3]),
        'frozen': ([25, 55], [.2, .4, .8], [.7, 1.3, 2.7, 4.3]),
        'smoke': ([10], [.5], [2]),
    }
    # Discovery reproduces the paper's 10..90 / 100 offer sweep. Selection and
    # frozen scenarios use different stakes; this tests stake transfer, not a new game.
    ultimatum = {
        'smoke': ([40], [25, 50, 75]),
        'discovery': ([100], list(range(10, 91, 5))),
        'selection': ([80], list(range(10, 91, 10))),
        'frozen': ([120, 200], list(range(10, 91, 5))),
    }
    objects = {
        'discovery': ['brick', 'stapler', 'cardboard tube', 'umbrella'],
        'selection': ['wooden spoon', 'paperclip'],
        'frozen': ['bath towel', 'plastic bottle', 'binder clip', 'shoebox'],
        'smoke': ['rubber band'],
    }
    for split, (stakes, probs, ratios) in settings.items():
        for stake, probability, ratio in itertools.product(stakes, probs, ratios):
            reward = round(stake * ratio, 2)
            scenario = dict(stake=stake, probability=probability, reward=reward)
            rows += choice('risk', split, scenario,
                           'All amounts are gains in tokens from your current balance.',
                           f'{100*probability:g}% chance of gaining {reward:g} tokens; otherwise gain zero.',
                           f'Gain {stake:g} tokens for certain.', scenario)
        for total, percent in itertools.product(*ultimatum[split]):
            offer = round(total * percent / 100, 2)
            proposer = round(total - offer, 2)
            scenario = dict(game='ultimatum', role='responder', total=total,
                            offer=offer, proposer_payoff=proposer, offer_percent=percent)
            intro = (f'You are the responder in a one-shot ultimatum game. '
                     f'The proposer was given {total:g} tokens and offers you {offer:g}, '
                     f'keeping {proposer:g} if you accept. If you reject, both of you receive zero. '
                     'There are no previous or future rounds with this participant.')
            target = f'Accept: you receive {offer:g} tokens and the proposer receives {proposer:g}.'
            other = 'Reject: you receive zero tokens and the proposer receives zero.'
            stratum = 'below_equal' if percent < 50 else 'equal' if percent == 50 else 'above_equal'
            for construct in ('altruism', 'fairness'):
                items = choice(construct, split, scenario, intro, target, other,
                               dict(scenario, offer_stratum=stratum, target_action='accept'))
                # The economic scenario is shared across the two feature families.
                for row in items:
                    row['scenario_id'] = digest(scenario)[:18]
                rows += items
        for obj, family in itertools.product(objects[split], ('uses', 'improvements')):
            group = digest(dict(construct='creativity', object=obj, family=family))[:18]
            for template in ('original', 'transfer'):
                task = (f'List six unusual but feasible uses for a {obj}.' if family == 'uses'
                        else f'Propose six unusual but feasible improvements to a {obj}.')
                text = (task + ' Give one short explanation for each idea.' if template == 'original'
                        else 'Consider the following design challenge: ' + task + ' Explain each idea briefly.')
                rows.append(dict(id=f'creativity-{group}-{template}', scenario_id=group,
                                 construct='creativity', split=split, template=template,
                                 kind='generation', system=SYSTEM_CREATIVE, text=text,
                                 covariates=dict(object=obj, family=family)))
    assert_disjoint(rows)
    return rows


def assert_disjoint(rows):
    ids, membership = set(), {}
    for row in rows:
        if row['id'] in ids:
            raise ValueError('Duplicate prompt ID')
        ids.add(row['id'])
        if membership.setdefault(row['scenario_id'], row['split']) != row['split']:
            raise ValueError('A scenario crosses a split boundary')


def metric(row, probability):
    """Paired contrasts are interpreted alongside untransformed probabilities."""
    sign = row['covariates'].get('reciprocity_sign', row['covariates'].get('conformity_sign', 1))
    return sign * probability
