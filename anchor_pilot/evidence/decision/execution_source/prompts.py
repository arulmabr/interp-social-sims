"""Small development fixtures, NOT a CPT identification or confirmatory grid."""


def smoke_prompts():
    rows = []
    for frame, sign in (("gain", 1), ("loss", -1)):
        for reverse in (False, True):
            safe_label, risky_label = ("B", "A") if reverse else ("A", "B")
            verb = "gain" if sign == 1 else "lose"
            options = {
                safe_label: f"{verb} 50 tokens for sure",
                risky_label: f"50% chance to {verb} 120 tokens and 50% chance of no change",
            }
            text = (
                "Evaluate changes relative to your current token balance.\n"
                f"Option A: {options['A']}.\nOption B: {options['B']}.\n"
                "Choose one option. Reply with exactly one letter: A or B."
            )
            rows.append({"id": f"{frame}-{'swapped' if reverse else 'original'}",
                         "frame": frame, "safe_label": safe_label,
                         "risky_label": risky_label, "text": text,
                         "split": "development_smoke_only"})
    return rows
