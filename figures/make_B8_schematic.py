"""figures/B8_schematic.{png,pdf} - what the SAE anchor work did, and what it found.

Top panel is a schematic of the three steps. Bottom panels place every direction
against both anchors on both games, in multiples of that anchor's own random
feature null, so one band serves every column.

Every value is read from the saved result files. Nothing is typed in here.

    python figures/make_B8_schematic.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# Surfaces and ink, the repository's existing figure tokens.
S, INK, INK2, MUT, HAIR, AX = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
# Categorical slots 1 and 2 of the reference palette. The palette file documents
# the first three slots as clearing every all-pairs gate in both modes, so they
# are used unchanged; both series are direct-labelled as well as coloured.
ANSWER, BIAS = "#2a78d6", "#eb6834"

REP = Path("reports")
LOT = json.loads((REP / "b8_sae_geometry.json").read_text())
ULT = json.loads((REP / "b8_sae_geometry_ultimatum.json").read_text())

ROWS = [("lottery_184", "feature 184\nwilling to take risks"),
        ("lottery_4237", "feature 4237\nrisky operations"),
        ("ultimatum_31935", "feature 31935\naltruistic and selfless"),
        ("FITTED", "fitted combinations\nfour of them")]
FITTED = ["sae10_combined_seed31", "sae10_combined_seed73",
          "sae10_neutral_seed31", "sae10_neutral_seed73"]


def _cos(rec, pole):
    """The two result files name their columns differently; accept either."""
    for k in ("cos_" + pole, pole):
        if k in rec:
            return rec[k]
    raise KeyError(pole)


def series(src, answer_key, bias_key):
    """Cosines in multiples of that pole's own 95th percentile null."""
    n = src.get("_null_abs_cos_random_feature") or src["_null"]
    na, nb = n[answer_key]["p95"], n[bias_key]["p95"]
    out = {}
    for key, _ in ROWS:
        names = FITTED if key == "FITTED" else [key]
        out[key] = ([_cos(src[m], answer_key) / na for m in names if m in src],
                    [_cos(src[m], bias_key) / nb for m in names if m in src])
    return out


LOT_S = series(LOT, "L48_sum", "L48_bias")
ULT_S = series(ULT, "L48_answer", "L48_bias")

fig = plt.figure(figsize=(10.4, 9.0), dpi=200)
fig.patch.set_facecolor(S)

# ---------------------------------------------------------------- schematic
ax = fig.add_axes([0.0, 0.560, 1.0, 0.425])
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.set_facecolor(S)
ax.text(0.035, 0.915, "What was done", fontsize=15.5, color=INK, va="bottom")
ax.text(0.035, 0.862, "Two changes of known kind are built without the dictionary, "
        "then every feature is measured against them.",
        fontsize=9.5, color=INK2, va="bottom")

BOX = dict(boxstyle="round,pad=0.022,rounding_size=0.018", linewidth=1.1)
steps = [
    (0.035, 0.288, "Step 1   Build the anchors", ANSWER,
     "The answer push is the direction that\n"
     "most efficiently changes which word is\n"
     "typed. It is computed once per option\n"
     "order, then split into the part common\n"
     "to both and the part that flips.\n\n"
     "The weight push is extra weights trained\n"
     "so the model gains a constant lean toward\n"
     "one answer and nothing else. Its direction\n"
     "is measured as the average change it\n"
     "makes inside the model."),
    (0.357, 0.288, "Step 2   Place every feature", BIAS,
     "Each feature direction is compared with\n"
     "each anchor.\n\n"
     "Two thousand features drawn at random go\n"
     "through the same comparison and set the\n"
     "level an ordinary feature reaches.\n\n"
     "A feature scoring below that level is\n"
     "doing no better than one picked\n"
     "blindfolded."),
    (0.679, 0.288, "Step 3   Steer and watch", INK2,
     "Each direction is added to the model\n"
     "while it answers, over a ladder of\n"
     "strengths.\n\n"
     "The change in the answer is compared\n"
     "with the unsteered answer. If the model\n"
     "still reacts to the amounts of money then\n"
     "the steering added something. If it no\n"
     "longer reacts then the steering erased\n"
     "the thing being measured."),
]
for x, w, title, colour, body in steps:
    ax.add_patch(FancyBboxPatch((x, 0.055), w, 0.735, facecolor="#ffffff",
                                edgecolor=HAIR, **BOX, transform=ax.transAxes))
    ax.plot([x + 0.011, x + 0.011], [0.085, 0.760], color=colour, lw=3.2,
            solid_capstyle="round")
    ax.text(x + 0.030, 0.715, title, fontsize=10.5, color=INK, va="bottom",
            fontweight="bold")
    ax.text(x + 0.030, 0.090, body, fontsize=8.1, color=INK2, va="bottom",
            linespacing=1.6)
for x in (0.331, 0.653):
    ax.add_patch(FancyArrowPatch((x, 0.42), (x + 0.020, 0.42), transform=ax.transAxes,
                                 arrowstyle="-|>", mutation_scale=11, color=MUT, lw=1.1))

fig.text(0.0335, 0.500, "What was found", fontsize=15.5, color=INK, va="bottom")
fig.text(0.0335, 0.470, "Every direction against both anchors, on both games.",
         fontsize=9.5, color=INK2, va="bottom")

# ---------------------------------------------------------------- results
for i, (data, game) in enumerate(((LOT_S, "Lottery"), (ULT_S, "Ultimatum"))):
    a = fig.add_axes([0.255 + i * 0.372, 0.095, 0.325, 0.330])
    a.set_facecolor(S)
    a.axvspan(-1, 1, color=HAIR, zorder=0, lw=0)
    a.axvline(0, color=AX, lw=0.9, zorder=1)
    for j, (key, _) in enumerate(ROWS):
        y = len(ROWS) - 1 - j
        for vals, colour, off in ((data[key][0], ANSWER, 0.17), (data[key][1], BIAS, -0.17)):
            a.plot(vals, [y + off] * len(vals), "o", ms=7.0, color=colour,
                   markeredgecolor=S, markeredgewidth=1.3, zorder=3)
    a.set_yticks(range(len(ROWS)))
    a.set_yticklabels([lab for _, lab in ROWS][::-1], fontsize=8.2, color=INK2,
                      linespacing=1.4)
    a.set_ylim(-0.62, len(ROWS) + 0.30)
    a.set_xlim(-3.9, 3.9)
    a.set_xticks([-3, -2, -1, 0, 1, 2, 3])
    a.tick_params(axis="x", labelsize=8, colors=INK2, length=3)
    a.tick_params(axis="y", length=0)
    for s in ("top", "right", "left"):
        a.spines[s].set_visible(False)
    a.spines["bottom"].set_color(AX)
    a.set_title(game, fontsize=11.5, color=INK, loc="left", pad=14)
    a.text(0, len(ROWS) - 0.12, "no better than a random feature",
           fontsize=7.6, color=MUT, ha="center", va="bottom")
    if i == 0:
        a.plot([], [], "o", ms=7.0, color=ANSWER, label="against the answer push")
        a.plot([], [], "o", ms=7.0, color=BIAS, label="against the weight push")
        handles, labels = a.get_legend_handles_labels()
        leg = fig.legend(handles, labels, fontsize=9.0, frameon=False,
                         loc="lower left", bbox_to_anchor=(0.435, 0.452),
                         ncol=2, handletextpad=0.5, columnspacing=2.2)
        for txt in leg.get_texts():
            txt.set_color(INK2)
    else:
        a.set_yticklabels([])

fig.text(0.585, 0.038, "agreement with the anchor, in multiples of what a random feature reaches",
         fontsize=8.6, color=INK2, ha="center")

out = Path("figures")
for ext in ("png", "pdf"):
    fig.savefig(out / f"B8_schematic.{ext}", facecolor=S, bbox_inches="tight")
print("wrote figures/B8_schematic.png and .pdf")
