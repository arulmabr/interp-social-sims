# B7_RECOVERY.md — the ultimatum anchor fails its pre-GPU check

Script: `cv_bench/estimator/social_recovery.py`. Agent and MDC: `logs/B_DECISIONS.md`
BD54 and BD55, both recorded before any of these numbers existed. Values as
`MANIFEST_B.csv:B7.*`. **No GPU time was spent.** This check exists to decide whether
spending it is worthwhile, and on this evidence it is not yet.

## What was built

A Fehr-Schmidt inequity-averse responder, `u_accept = offer - beta_adv * max(pie - 2*offer, 0)`
against `u_reject = 0`, normalised by the pie so the agent is scale invariant across pies of
20, 100 and 1,000. Reference `beta_adv` 0.60, giving an acceptance threshold of 27.27 percent
of the pie. The MDC is the reduction in `beta_adv` that moves that threshold by the same
fraction of its grid as one risk MDC moves the lottery switching point, which is
**0.225771**. Eight tests cover it, including the packed against unpacked agreement that the
whole estimator depends on.

## What the check says

Simulated choices of agents whose parameters are known exactly, 384 trials by 40 replicates.

| arm | planted | recovered | error | share on preference | verdict |
|---|---|---|---|---|---|
| preference at 1 MDC | 0.2258 | 0.2204 | **0.02 MDC** | **1.000** | recovery is excellent |
| preference at 3 MDC | 0.6773 | railed at the bound | not available | 1.000 | **not representable** |
| bias, a pure accept push | 0.0000 | 0.1292 | 0.57 MDC | **0.984** | **specificity fails** |

**The first row is the good news and it is real.** The estimator retrieves a planted inequity
shift to within a fortieth of a detectable change, and gives it all of the evidence weight.

**The second row is arithmetic, not a result.** Three times this MDC is 0.6773, and
`beta_adv` starts at 0.60, so a three times anchor in the declared direction requires a
negative weight on inequity. The lottery's three times anchor exists because alpha has room
above it. Here there is no room below. A three times anchor is available only in the opposite
direction, as a **more** inequity-averse responder, which is not what BD54 declared.

**The third row is the one that stops the run.** A planted pure accept bias is attributed to
preference at 0.984. The identical control on the lottery returns preference **0.000**. An
attribution step that calls a known bias a preference change cannot certify anything, and
training adapters to imitate these agents would produce an anchor whose gate is already known
to be uninformative.

## Why it fails, which is structural rather than a bug

Two properties of the responder grid, both measured:

**The planted preference effect never changes sign.** Across the offer grid the change in the
latent runs +1.904 at an offer of nothing, +0.952 at a quarter of the pie, and exactly 0 from
half the pie upward. It is non-negative everywhere. On the lottery the same implant is −0.113
at a reward of 30 and +0.334 at 150. That sign change is what makes a curvature change
unmistakably unlike a constant push, and the ultimatum implant does not have it.

**The one region where the two differ is saturated.** From half the pie upward the preference
implant does nothing and the bias still adds 0.600, so that region is where the two could be
told apart. The reference agent already accepts there with probability 0.985 to 0.999, so an
extra 0.600 moves behaviour by under one percent. Only **96 of 384** trials sit in the range
where the choice is genuinely uncertain.

Where there is information, between a tenth and four tenths of the pie, the preference effect
runs 1.52 down to 0.38 with a mean near 0.9, and a flat 0.6 approximates it well. The two
families are close to observationally equivalent on exactly the trials that carry the data.

Excluding or keeping the catch trials changes this only a little. With them dropped the bias
arm attributes 0.984 to preference; with them kept it attributes 0.775. Neither is near zero.

## What this does not say

It does not say the ultimatum game cannot be anchored. It says this responder grid with this
one-sided agent cannot separate a constant accept push from an inequity change, and that the
separation fails for a reason visible in the geometry rather than in any model output.

## Options, for the authors

1. **Report it as it stands.** The ultimatum anchor recovers size and fails attribution,
   stated beside the lottery's result. Costs nothing further and is honest.
2. **Change the game rather than the agent.** The proposer, dictator and mini-ultimatum
   generators already exist in `cv_bench/tasks/social.py`. The mini-ultimatum in particular
   judges one split against a named alternative, which is a different saturation pattern.
   Whether any of them separates the two families is an open question that the same
   synthetic check would answer in minutes.
3. **Two-sided Fehr-Schmidt.** Adding a weight on being ahead restores a sign change above
   half the pie. Checked by hand it does not fix the saturation, since accepting a generous
   offer stays strongly preferred unless the ahead-weight exceeds 0.5, which would mean
   rejecting generous offers and is what the plan calls a catch trial. Likely insufficient
   on its own.

Option 2 is the one worth the time. Any change made in response to this page has to be logged
in `logs/B_DEVIATIONS.md` with the before and after, because it is being made after a result
was seen.
