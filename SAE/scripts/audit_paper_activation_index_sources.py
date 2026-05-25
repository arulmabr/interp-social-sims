#!/usr/bin/env python3
"""Audit historical Goodfire activation labels for recoverable SAE indices."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {".csv", ".ipynb", ".json", ".jsonl", ".md", ".py", ".txt"}
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
RELEASE_GENERATED_AUDIT_EXCLUDES = {
    "DATA_MANIFEST.tsv",
    "README.md",
    "data/processed/paper_activation_index_search_audit.csv",
    "data/processed/paper_activation_label_crosswalk.csv",
    "data/processed/steering_feature_label_crosswalk.csv",
    "docs/LABELS.md",
    "docs/REPRODUCTION.md",
    "docs/STEERING.md",
    "reports/PAPER_ACTIVATION_INDEX_SEARCH_AUDIT.md",
    "reports/PAPER_ACTIVATION_LABEL_CROSSWALK.md",
    "scripts/audit_paper_activation_index_sources.py",
}


@dataclass(frozen=True)
class MetadataRoot:
    """Named metadata root used for privacy-preserving audit output."""

    alias: str
    path: Path


def release_path(path: Path | str) -> str:
    """Return a repo-relative path when possible."""

    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def parse_metadata_root(value: str) -> MetadataRoot:
    """Parse an alias=path metadata-root argument."""

    if "=" in value:
        alias, raw_path = value.split("=", 1)
    else:
        raw_path = value
        alias = Path(value).name or "metadata_root"
    alias = re.sub(r"[^A-Za-z0-9_.-]+", "_", alias.strip())
    if not alias:
        raise ValueError(f"Invalid metadata-root alias in {value!r}")
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    return MetadataRoot(alias=alias, path=path)


def load_paper_labels(path: Path) -> tuple[list[str], int]:
    """Load the unique old Goodfire labels from the paper activation CSV."""

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        labels = sorted(
            {
                str(row.get("feature_label", "")).strip()
                for row in reader
                if str(row.get("feature_label", "")).strip()
            }
        )
        row_count = reader.line_num - 1
    return labels, row_count


def read_text(path: Path) -> str:
    """Read a text-like file with best-effort decoding."""

    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def iter_files(root: MetadataRoot) -> list[Path]:
    """Return audit-relevant files beneath a metadata root."""

    paths: list[Path] = []
    for path in root.path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix not in TEXT_EXTENSIONS:
            continue
        if (
            root.alias == "release_repo"
            and path.relative_to(root.path).as_posix() in RELEASE_GENERATED_AUDIT_EXCLUDES
        ):
            continue
        paths.append(path)
    return sorted(paths)


def source_name(root: MetadataRoot, path: Path) -> str:
    """Return a root-alias-relative source path."""

    return f"{root.alias}/{path.relative_to(root.path).as_posix()}"


def visit_dict_for_exact_pairs(
    obj: Any,
    *,
    paper_labels: set[str],
    evidence_method: str,
    source_root: str,
    source_file: str,
    rows: list[dict[str, Any]],
) -> None:
    """Collect label/index pairs only when they share the same dictionary object."""

    if isinstance(obj, dict):
        label = obj.get("label") or obj.get("old_goodfire_label")
        feature_index = obj.get("index_in_sae")
        if feature_index is None:
            feature_index = obj.get("feature_index")
        if label and str(label) in paper_labels and feature_index is not None:
            try:
                parsed_index = int(feature_index)
            except (TypeError, ValueError):
                parsed_index = None
            if parsed_index is not None:
                rows.append(
                    {
                        "record_type": "exact_mapping_evidence",
                        "mapping_status": "exact_feature_index_match",
                        "old_goodfire_label": str(label),
                        "feature_index": parsed_index,
                        "evidence_method": evidence_method,
                        "source_root": source_root,
                        "source_file": source_file,
                        "paper_label_count_in_file": "",
                        "paper_labels_sample": "",
                    }
                )
        for value in obj.values():
            visit_dict_for_exact_pairs(
                value,
                paper_labels=paper_labels,
                evidence_method=evidence_method,
                source_root=source_root,
                source_file=source_file,
                rows=rows,
            )
    elif isinstance(obj, list):
        for value in obj:
            visit_dict_for_exact_pairs(
                value,
                paper_labels=paper_labels,
                evidence_method=evidence_method,
                source_root=source_root,
                source_file=source_file,
                rows=rows,
            )


def parse_python_dicts(
    source: str,
    *,
    paper_labels: set[str],
    evidence_method: str,
    source_root: str,
    source_file: str,
    rows: list[dict[str, Any]],
) -> None:
    """Parse literal Python dictionaries from source code."""

    try:
        tree = ast.parse(source)
    except Exception:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        try:
            obj = ast.literal_eval(node)
        except Exception:
            continue
        visit_dict_for_exact_pairs(
            obj,
            paper_labels=paper_labels,
            evidence_method=evidence_method,
            source_root=source_root,
            source_file=source_file,
            rows=rows,
        )


def parse_python_literal_outputs(
    text: str,
    *,
    paper_labels: set[str],
    source_root: str,
    source_file: str,
    rows: list[dict[str, Any]],
) -> None:
    """Parse notebook text/plain outputs containing Python controller reprs."""

    candidates: list[str] = []
    stripped = text.strip()
    if stripped.startswith("{") and "index_in_sae" in stripped:
        candidates.append(stripped)

    for match in re.finditer(r"\{'interventions':", text):
        start = match.start()
        depth = 0
        quote: str | None = None
        escaped = False
        for index, character in enumerate(text[start:], start):
            if quote:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
            else:
                if character in {"'", '"'}:
                    quote = character
                elif character == "{":
                    depth += 1
                elif character == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start : index + 1])
                        break

    for candidate in candidates:
        try:
            obj = ast.literal_eval(candidate)
        except Exception:
            continue
        visit_dict_for_exact_pairs(
            obj,
            paper_labels=paper_labels,
            evidence_method="ipynb_output_literal",
            source_root=source_root,
            source_file=source_file,
            rows=rows,
        )


def parse_csv_controllers(
    path: Path,
    *,
    paper_labels: set[str],
    source_root: str,
    source_file: str,
    rows: list[dict[str, Any]],
) -> None:
    """Parse serialized Goodfire controller metadata from EDSL result CSVs."""

    try:
        with path.open(encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            if "model.controller" not in (reader.fieldnames or []):
                return
            seen: set[str] = set()
            for record in reader:
                raw_controller = str(record.get("model.controller") or "")
                if "index_in_sae" not in raw_controller or raw_controller in seen:
                    continue
                seen.add(raw_controller)
                try:
                    controller = ast.literal_eval(raw_controller)
                except (SyntaxError, ValueError):
                    continue
                visit_dict_for_exact_pairs(
                    controller,
                    paper_labels=paper_labels,
                    evidence_method="csv_model_controller",
                    source_root=source_root,
                    source_file=source_file,
                    rows=rows,
                )
    except Exception:
        return


def parse_prose_label_index_patterns(
    text: str,
    *,
    paper_labels: set[str],
    source_root: str,
    source_file: str,
    rows: list[dict[str, Any]],
) -> None:
    """Parse explicit prose patterns like '<label>' followed by '(index 123)'."""

    for label in paper_labels:
        if label not in text:
            continue
        pattern = re.escape(label) + r"[^\n]{0,160}\bindex\s+([0-9]+)"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            rows.append(
                {
                    "record_type": "exact_mapping_evidence",
                    "mapping_status": "exact_feature_index_match",
                    "old_goodfire_label": label,
                    "feature_index": int(match.group(1)),
                    "evidence_method": "prose_label_index_pattern",
                    "source_root": source_root,
                    "source_file": source_file,
                    "paper_label_count_in_file": "",
                    "paper_labels_sample": "",
                }
            )


def parse_file_for_exact_pairs(
    path: Path,
    *,
    root: MetadataRoot,
    paper_labels: set[str],
    rows: list[dict[str, Any]],
) -> None:
    """Parse one file for strict label/index evidence rows."""

    rel_source = source_name(root, path)
    text = read_text(path)
    if path.suffix == ".csv":
        parse_csv_controllers(
            path,
            paper_labels=paper_labels,
            source_root=root.alias,
            source_file=rel_source,
            rows=rows,
        )
        return

    if path.suffix == ".py":
        parse_python_dicts(
            text,
            paper_labels=paper_labels,
            evidence_method="python_ast_dict",
            source_root=root.alias,
            source_file=rel_source,
            rows=rows,
        )
        return

    if path.suffix == ".ipynb":
        try:
            notebook = json.loads(text)
        except Exception:
            return
        visit_dict_for_exact_pairs(
            notebook,
            paper_labels=paper_labels,
            evidence_method="ipynb_json_object",
            source_root=root.alias,
            source_file=rel_source,
            rows=rows,
        )
        for cell in notebook.get("cells", []) or []:
            source = cell.get("source", "")
            source_text = "".join(source) if isinstance(source, list) else str(source)
            parse_python_dicts(
                source_text,
                paper_labels=paper_labels,
                evidence_method="ipynb_source_ast_dict",
                source_root=root.alias,
                source_file=rel_source,
                rows=rows,
            )
            for output in cell.get("outputs", []) or []:
                if not isinstance(output, dict):
                    continue
                output_texts: list[str] = []
                if "text" in output:
                    text_value = output["text"]
                    output_texts.append(
                        "".join(text_value) if isinstance(text_value, list) else str(text_value)
                    )
                data = output.get("data") or {}
                if isinstance(data, dict):
                    for value in data.values():
                        output_texts.append("".join(value) if isinstance(value, list) else str(value))
                for output_text in output_texts:
                    parse_python_literal_outputs(
                        output_text,
                        paper_labels=paper_labels,
                        source_root=root.alias,
                        source_file=rel_source,
                        rows=rows,
                    )
        return

    if path.suffix == ".jsonl":
        for line in text.splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                continue
            visit_dict_for_exact_pairs(
                obj,
                paper_labels=paper_labels,
                evidence_method="jsonl_object",
                source_root=root.alias,
                source_file=rel_source,
                rows=rows,
            )
        return

    if path.suffix == ".json":
        try:
            obj = json.loads(text)
        except Exception:
            return
        visit_dict_for_exact_pairs(
            obj,
            paper_labels=paper_labels,
            evidence_method="json_object",
            source_root=root.alias,
            source_file=rel_source,
            rows=rows,
        )
        return

    if path.suffix in {".md", ".txt"}:
        parse_prose_label_index_patterns(
            text,
            paper_labels=paper_labels,
            source_root=root.alias,
            source_file=rel_source,
            rows=rows,
        )


def add_rejected_candidate_rows(
    *,
    path: Path,
    root: MetadataRoot,
    paper_labels: set[str],
    exact_rows_by_file: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
) -> None:
    """Add one file-level row for co-located labels/indices without exact mapping."""

    text = read_text(path)
    labels_in_file = sorted(label for label in paper_labels if label in text)
    if not labels_in_file:
        return
    has_index_text = (
        "index_in_sae" in text
        or "feature_index" in text
        or re.search(r"\bindex\s+[0-9]+\b", text, flags=re.IGNORECASE) is not None
    )
    if not has_index_text:
        return
    rel_source = source_name(root, path)
    if exact_rows_by_file.get(rel_source):
        return
    rows.append(
        {
            "record_type": "candidate_file",
            "mapping_status": "candidate_rejected_no_same_object_mapping",
            "old_goodfire_label": "",
            "feature_index": "",
            "evidence_method": "co_located_label_and_index_text",
            "source_root": root.alias,
            "source_file": rel_source,
            "paper_label_count_in_file": len(labels_in_file),
            "paper_labels_sample": " | ".join(labels_in_file[:5]),
        }
    )


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate audit rows while preserving stable order."""

    seen: set[tuple[Any, ...]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(row.get(column, "") for column in AUDIT_COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


AUDIT_COLUMNS = [
    "record_type",
    "mapping_status",
    "old_goodfire_label",
    "feature_index",
    "evidence_method",
    "source_root",
    "source_file",
    "paper_label_count_in_file",
    "paper_labels_sample",
]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write audit rows."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize_exact(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize exact mapping evidence rows."""

    exact_rows = [row for row in rows if row["record_type"] == "exact_mapping_evidence"]
    by_label: dict[str, set[int]] = defaultdict(set)
    sources: dict[tuple[str, int], set[str]] = defaultdict(set)
    methods: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in exact_rows:
        label = str(row["old_goodfire_label"])
        index = int(row["feature_index"])
        by_label[label].add(index)
        sources[(label, index)].add(str(row["source_file"]))
        methods[(label, index)].add(str(row["evidence_method"]))
    return {
        "exact_rows": exact_rows,
        "by_label": by_label,
        "sources": sources,
        "methods": methods,
    }


def write_report(
    path: Path,
    *,
    audit_rows: list[dict[str, Any]],
    metadata_roots: list[MetadataRoot],
    paper_row_count: int,
    paper_label_count: int,
    files_scanned: int,
    output_csv: Path,
) -> None:
    """Write the Markdown audit report."""

    exact = summarize_exact(audit_rows)
    exact_rows = exact["exact_rows"]
    by_label = exact["by_label"]
    candidate_rows = [
        row
        for row in audit_rows
        if row["mapping_status"] == "candidate_rejected_no_same_object_mapping"
    ]
    exact_index_count = len({int(row["feature_index"]) for row in exact_rows})
    method_counts = Counter(row["evidence_method"] for row in exact_rows)
    root_counts = Counter(row["source_root"] for row in audit_rows)

    lines = [
        "# Paper Activation Index Search Audit",
        "",
        f"Generated from `{release_path(output_csv)}`.",
        "",
        "This audit searched the public release repo plus companion EDSL/Goodfire",
        "development checkouts for exact mappings from historical Goodfire labels",
        "to SAE `feature_index` values. A mapping is accepted only when the old",
        "Goodfire label and `index_in_sae` or `feature_index` occur in the same",
        "serialized controller/dictionary object, or in an explicit prose",
        "`label (index N)` source note. Co-located labels and index-like fields",
        "in the same notebook or JSONL file are rejected.",
        "",
        "## Scope",
        "",
        f"- Paper activation rows inspected: {paper_row_count:,}",
        f"- Unique old Goodfire labels inspected: {paper_label_count:,}",
        f"- Metadata roots searched: {', '.join(root.alias for root in metadata_roots)}",
        f"- Text/code files scanned: {files_scanned:,}",
        f"- Candidate files with paper labels and index-like text: {len(candidate_rows) + len(set(row['source_file'] for row in exact_rows)):,}",
        f"- Exact mapping evidence rows: {len(exact_rows):,}",
        f"- Unique old labels with exact feature indices: {len(by_label):,}",
        f"- Unique exact feature indices: {exact_index_count:,}",
        "",
        "## Result",
        "",
        "The cross-repo search did not recover any additional exact feature-index",
        "mappings beyond the five already used in the paper activation crosswalk.",
        "The old activation logs mostly store only `activation.feature.label` and",
        "`activation.activation`; they do not store the SAE index for each top",
        "paragraph feature.",
        "",
        "| Old Goodfire label | Feature index | Evidence methods | Source files |",
        "| --- | ---: | --- | ---: |",
    ]
    for label in sorted(by_label):
        for index in sorted(by_label[label]):
            key = (label, index)
            lines.append(
                "| "
                + " | ".join(
                    [
                        label,
                        str(index),
                        ", ".join(sorted(exact["methods"][key])),
                        str(len(exact["sources"][key])),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Rejected Co-Location",
            "",
            "Several notebooks contain both old activation labels and controller",
            "indices, but not in the same feature object. Those cases are kept as",
            "`candidate_rejected_no_same_object_mapping` in the audit CSV and are not",
            "used for Neuronpedia identity mapping.",
            "",
            "Top rejected candidate files by old-label coverage:",
            "",
            "| Source file | Old labels in file | Example labels |",
            "| --- | ---: | --- |",
        ]
    )
    top_candidates = sorted(
        candidate_rows,
        key=lambda row: (
            -int(row.get("paper_label_count_in_file") or 0),
            str(row.get("source_file")),
        ),
    )[:12]
    for row in top_candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["source_file"]),
                    str(row["paper_label_count_in_file"]),
                    str(row["paper_labels_sample"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Evidence Counts",
            "",
            f"- Audit rows by root: {dict(sorted(root_counts.items()))}",
            f"- Exact evidence rows by method: {dict(sorted(method_counts.items()))}",
            "",
            "This is why `feature_index` remains blank for the old-label-only rows in",
            "`data/processed/paper_activation_label_crosswalk.csv`: without the",
            "index stored in the historical activation row or same-object metadata,",
            "the old label alone is not a stable cross-system identifier.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_audit(
    *,
    paper_activations: Path,
    metadata_roots: list[MetadataRoot],
) -> tuple[list[dict[str, Any]], int, int, int]:
    """Build the strict mapping audit rows."""

    paper_labels, paper_row_count = load_paper_labels(paper_activations)
    paper_label_set = set(paper_labels)
    rows: list[dict[str, Any]] = []
    files_scanned = 0
    all_paths: list[tuple[MetadataRoot, Path]] = []
    for root in metadata_roots:
        for path in iter_files(root):
            files_scanned += 1
            all_paths.append((root, path))
            parse_file_for_exact_pairs(
                path,
                root=root,
                paper_labels=paper_label_set,
                rows=rows,
            )

    rows = dedupe_rows(rows)
    exact_rows_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["record_type"] == "exact_mapping_evidence":
            exact_rows_by_file[str(row["source_file"])].append(row)

    for root, path in all_paths:
        add_rejected_candidate_rows(
            path=path,
            root=root,
            paper_labels=paper_label_set,
            exact_rows_by_file=exact_rows_by_file,
            rows=rows,
        )

    rows = dedupe_rows(rows)
    rows.sort(
        key=lambda row: (
            str(row["record_type"]),
            str(row["old_goodfire_label"]),
            str(row["feature_index"]),
            str(row["source_root"]),
            str(row["source_file"]),
            str(row["evidence_method"]),
        )
    )
    return rows, paper_row_count, len(paper_labels), files_scanned


def check_outputs(audit_rows: list[dict[str, Any]]) -> None:
    """Validate the generated audit."""

    exact = summarize_exact(audit_rows)
    by_label = exact["by_label"]
    expected = {
        "Altruistic and selfless behavior or intentions": {31935},
        "Descriptions of creative unconventional thinking, especially 'thinking outside the box'": {20117},
        "Executing potentially risky operations that require caution": {4237},
        "Professional innovation and creative problem-solving": {4992},
        "Willing to take risks or make sacrifices for a goal": {184},
    }
    if dict(by_label) != expected:
        raise AssertionError(f"Unexpected exact mapping set: {dict(by_label)}")
    for row in audit_rows:
        if row["mapping_status"] == "exact_feature_index_match" and not row["feature_index"]:
            raise AssertionError("Exact audit row is missing feature_index")
        if (
            row["mapping_status"] == "candidate_rejected_no_same_object_mapping"
            and row["feature_index"]
        ):
            raise AssertionError("Rejected candidate row unexpectedly has feature_index")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-activations", type=Path, required=True)
    parser.add_argument(
        "--metadata-root",
        action="append",
        default=[],
        help="Named root to scan, formatted as alias=/path/to/root. May be repeated.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data/processed/paper_activation_index_search_audit.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "reports/PAPER_ACTIVATION_INDEX_SEARCH_AUDIT.md",
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the audit."""

    args = parse_args()
    if not args.paper_activations.exists():
        raise FileNotFoundError(args.paper_activations)
    roots = [parse_metadata_root(value) for value in args.metadata_root]
    if not roots:
        roots = [MetadataRoot(alias="release_repo", path=REPO_ROOT)]

    audit_rows, paper_row_count, paper_label_count, files_scanned = build_audit(
        paper_activations=args.paper_activations,
        metadata_roots=roots,
    )
    write_csv(args.output, audit_rows)
    write_report(
        args.report,
        audit_rows=audit_rows,
        metadata_roots=roots,
        paper_row_count=paper_row_count,
        paper_label_count=paper_label_count,
        files_scanned=files_scanned,
        output_csv=args.output,
    )
    if args.check:
        check_outputs(audit_rows)

    exact = summarize_exact(audit_rows)
    print(
        json.dumps(
            {
                "paper_rows": paper_row_count,
                "paper_unique_labels": paper_label_count,
                "metadata_roots": [root.alias for root in roots],
                "files_scanned": files_scanned,
                "audit_rows": len(audit_rows),
                "exact_mapping_evidence_rows": len(exact["exact_rows"]),
                "exact_old_labels": len(exact["by_label"]),
                "exact_feature_indices": len(
                    {
                        int(row["feature_index"])
                        for row in exact["exact_rows"]
                    }
                ),
                "output": release_path(args.output),
                "report": release_path(args.report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
