# B_DEVIATIONS.md

Track B deviations. The shared `logs/DEVIATIONS.md` belongs to the Friday session and is not edited
from this worktree; anything Track B departs from is recorded here instead.

Format: what was planned, what was done, why, and the before and after. A deviation is a *technical*
change only — `CLAUDE.md` rule 4 still forbids changing seeds, prompts, doses, thresholds, exclusions
or metrics because a result looks unhelpful.

*No deviations recorded yet.*

**Gate B2's text changes, twice, before any model data was fitted.** Both are author decisions of
22 Sept, recorded here because they alter the criteria `ICLR_PLAN.md` states for a gate, and both were
made while the only data in existence was synthetic. `CLAUDE.md` rule 4 is not in play: no result was
rerun, and no threshold was relaxed to accommodate an outcome.

**1. Lambda becomes a secondary parameter with its own gate.**
- *Planned:* Gate B2 passes when "parameter RMSE is at most half of each minimum detectable change",
  which covers alpha, gamma and lambda together, lambda's bar being 0.15.
- *Now:* Gate B2 is evaluated on **alpha and gamma only**. The RMSE bars and the 95% classification
  rule are unchanged for both. Lambda **keeps its 0.15 bar** and moves to its own gate, tested once a
  denser mixed-frame grid passes on synthetic agents; the smallest such grid is to be found by
  simulation.
- *Why:* the paper's tasks are in the gain domain and the first preference anchor of B3.2 shifts
  alpha, so lambda is not on the critical path for anything the Sept 25 paper claims. It is also not
  identified on the current grid at all: under the mandated contextual-utility normalisation lambda
  cancels exactly wherever outcomes share a sign, giving a largest change in z of **0.000000** across
  all 245 sure-gain and all 245 sure-loss trials (BD10, recorded before fitting). Holding the whole
  gate hostage to a parameter the grid cannot see would block alpha and gamma, which it can.
- *Before / after:* Gate B2 failed on lambda RMSE 0.416 against 0.15 in all 18 configurations. Under
  the amended text those configurations are judged on alpha (0.0091) and gamma (0.0044) against 0.05.
  Lambda's own gate remains unmet and unreported as passed.

**2. The misspecified agents become bases, not interventions.**
- *Planned:* mean-variance utility and the arbitrary monotone curve sat beside action, belief, noise
  and format as agent types, and Gate B2 required the decision rule to handle them "on the model-free
  layer" — a phrase the plan did not define.
- *Now:* they are **base agents**. Base in {CPT, mean-variance, monotone} is crossed with intervention
  in {preference shift within that family, action bias, belief distortion, noise, format}. On the two
  misspecified bases the **model-free layer** must classify the interventions correctly at **>= 95%**.
  The parametric layer is permitted to be wrong there, and how often it contradicts the model-free
  verdict with a share above 0.8 is reported rather than gated. **D1 is scored as a change from that
  base agent's own baseline**, not from the CPT baseline.
- *Why:* a mean-variance agent is not an intervention that looks odd; it is a different model of the
  subject, on which the same five interventions can be applied. Asking whether it "looks like a
  preference shift" was the wrong question. The right one is whether the diagnostics still work when
  the parametric model is wrong about the subject — which is what the two agents were put in the plan
  for. Track B had flagged the ambiguity rather than settling it (BD14), and this settles it.
- *Before / after:* under the old reading the two agents were scored by whether they looked clean, and
  mean-variance failed because it genuinely violates stochastic dominance, so D1 flagged it correctly
  and the gate counted that as a failure. Under the amended text that same behaviour is scored against
  the mean-variance baseline, where it is not an anomaly at all.

**B1 rebuilt with the social framing defect unfixed.** Author reply "audit ok", 22 Sept, after
`reports/B_PROMPT_AUDIT.md` flagged it (BD31).
- *Planned:* the social families state their game, as `Probes/tasks/prompts.py` does for the ultimatum.
- *Done:* they render as bare payoff pairs — `Reject: nothing` / `Accept: 90 tokens for sure` — with no
  proposer, no pie and no "both of you get 0".
- *Why it is acceptable here:* nothing in the current chain reads them. B2-cal, B3.1, B3.2 and the B2
  recovery study are risk-domain only. The defect is confined to the social families and to any future
  result that uses them.
- *Standing caveat:* **no social number from this build may be reported as a social preference.** With
  the framing absent, rejecting a low offer is an arithmetic error rather than inequity aversion, and
  the mini-ultimatum's alternatives never reach the model. Free-text cells carry the same caveat: they
  are scored by the first-token readout, not by sequence log-probability, so they are a second
  multiple-choice arm.
