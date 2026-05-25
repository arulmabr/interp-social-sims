#!/usr/bin/env python3
"""Audit git history for historical Goodfire label-to-index mappings."""

from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import re
import subprocess
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
EXPECTED_BASELINE_MAPPINGS = {
    "Altruistic and selfless behavior or intentions": {31935},
    "Descriptions of creative unconventional thinking, especially 'thinking outside the box'": {20117},
    "Executing potentially risky operations that require caution": {4237},
    "Professional innovation and creative problem-solving": {4992},
    "Willing to take risks or make sacrifices for a goal": {184},
}


@dataclass(frozen=True)
class GitRoot:
    """Named git repository root."""

    alias: str
    path: Path


@dataclass(frozen=True)
class BlobSource:
    """One historical blob path in a git repository."""

    alias: str
    repo_path: Path
    blob_sha: str
    path: str


def release_path(path: Path | str) -> str:
    """Return a repo-relative path when possible."""

    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def md_cell(value: Any) -> str:
    """Escape a value for use in a Markdown table cell."""

    return str(value).replace("|", "\\|").replace("\n", " ")


def parse_git_root(value: str) -> GitRoot:
    """Parse alias=/path/to/repo arguments."""

    if "=" in value:
        alias, raw_path = value.split("=", 1)
    else:
        raw_path = value
        alias = Path(value).name or "git_root"
    alias = re.sub(r"[^A-Za-z0-9_.-]+", "_", alias.strip())
    if not alias:
        raise ValueError(f"Invalid git-root alias in {value!r}")
    path = Path(raw_path).expanduser().resolve()
    if not (path / ".git").exists():
        raise FileNotFoundError(f"Not a git repository: {path}")
    return GitRoot(alias=alias, path=path)


def git(root: GitRoot, *args: str) -> str:
    """Run a git command and return stdout."""

    return subprocess.check_output(
        ["git", "-C", str(root.path), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    )


def git_count_commits(root: GitRoot) -> int:
    """Count reachable commits in a git root."""

    return int(git(root, "rev-list", "--all", "--count").strip())


def load_paper_labels(path: Path) -> tuple[list[str], int]:
    """Load old Goodfire labels and row count from the paper activation CSV."""

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


def should_scan_path(path: str) -> bool:
    """Return whether a historical file path is relevant to the audit."""

    parts = set(Path(path).parts)
    if parts & SKIP_PARTS:
        return False
    return Path(path).suffix in TEXT_EXTENSIONS


def iter_git_blob_sources(root: GitRoot) -> tuple[list[BlobSource], int]:
    """Return all reachable historical text-like blob paths for a git repo."""

    sources: list[BlobSource] = []
    all_objects = 0
    output = git(root, "rev-list", "--objects", "--all")
    for line in output.splitlines():
        all_objects += 1
        if " " not in line:
            continue
        blob_sha, path = line.split(" ", 1)
        if should_scan_path(path):
            sources.append(
                BlobSource(
                    alias=root.alias,
                    repo_path=root.path,
                    blob_sha=blob_sha,
                    path=path,
                )
            )
    return sources, all_objects


def batch_load_blobs(root: GitRoot, blob_shas: list[str]) -> dict[str, bytes]:
    """Load git blob contents with git cat-file --batch."""

    if not blob_shas:
        return {}
    process = subprocess.Popen(
        ["git", "-C", str(root.path), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    payload = "\n".join(blob_shas).encode("ascii") + b"\n"
    stdout, _ = process.communicate(payload)

    contents: dict[str, bytes] = {}
    stream = io.BytesIO(stdout)
    while True:
        header = stream.readline()
        if not header:
            break
        parts = header.rstrip(b"\n").split(b" ")
        if len(parts) < 3:
            break
        sha = parts[0].decode("ascii", errors="ignore")
        obj_type = parts[1].decode("ascii", errors="ignore")
        size = int(parts[2])
        data = stream.read(size)
        stream.read(1)
        if obj_type == "blob":
            contents[sha] = data
    return contents


def decode_blob(data: bytes) -> str:
    """Decode a git blob as text if possible."""

    if b"\x00" in data[:4096]:
        return ""
    return data.decode("utf-8", errors="ignore")


def source_file(source: BlobSource) -> str:
    """Return an alias-relative source path."""

    return f"{source.alias}/{source.path}"


def visit_dict_for_exact_pairs(
    obj: Any,
    *,
    paper_labels: set[str],
    evidence_method: str,
    source: BlobSource,
    rows: list[dict[str, Any]],
) -> None:
    """Collect strict label/index pairs from one dictionary object."""

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
                        "source_root": source.alias,
                        "source_file": source_file(source),
                        "source_commit": "",
                        "blob_sha": source.blob_sha,
                        "paper_label_count_in_blob": "",
                        "paper_labels_sample": "",
                    }
                )
        for value in obj.values():
            visit_dict_for_exact_pairs(
                value,
                paper_labels=paper_labels,
                evidence_method=evidence_method,
                source=source,
                rows=rows,
            )
    elif isinstance(obj, list):
        for value in obj:
            visit_dict_for_exact_pairs(
                value,
                paper_labels=paper_labels,
                evidence_method=evidence_method,
                source=source,
                rows=rows,
            )


def parse_python_dicts(
    text: str,
    *,
    paper_labels: set[str],
    evidence_method: str,
    source: BlobSource,
    rows: list[dict[str, Any]],
) -> None:
    """Parse literal Python dictionaries from historical source."""

    try:
        tree = ast.parse(text)
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
            source=source,
            rows=rows,
        )


def parse_python_literal_outputs(
    text: str,
    *,
    paper_labels: set[str],
    source: BlobSource,
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
            source=source,
            rows=rows,
        )


def parse_csv_controllers(
    text: str,
    *,
    paper_labels: set[str],
    source: BlobSource,
    rows: list[dict[str, Any]],
) -> None:
    """Parse serialized controller objects from historical CSV blobs."""

    try:
        reader = csv.DictReader(io.StringIO(text))
    except Exception:
        return
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
            source=source,
            rows=rows,
        )


def parse_prose_label_index_patterns(
    text: str,
    *,
    paper_labels: set[str],
    source: BlobSource,
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
                    "source_root": source.alias,
                    "source_file": source_file(source),
                    "source_commit": "",
                    "blob_sha": source.blob_sha,
                    "paper_label_count_in_blob": "",
                    "paper_labels_sample": "",
                }
            )


def parse_blob_for_exact_pairs(
    text: str,
    *,
    source: BlobSource,
    paper_labels: set[str],
    rows: list[dict[str, Any]],
) -> None:
    """Parse one historical blob for strict mapping evidence."""

    suffix = Path(source.path).suffix
    if suffix == ".csv":
        parse_csv_controllers(
            text,
            paper_labels=paper_labels,
            source=source,
            rows=rows,
        )
        return
    if suffix == ".py":
        parse_python_dicts(
            text,
            paper_labels=paper_labels,
            evidence_method="python_ast_dict",
            source=source,
            rows=rows,
        )
        return
    if suffix == ".ipynb":
        try:
            notebook = json.loads(text)
        except Exception:
            return
        visit_dict_for_exact_pairs(
            notebook,
            paper_labels=paper_labels,
            evidence_method="ipynb_json_object",
            source=source,
            rows=rows,
        )
        for cell in notebook.get("cells", []) or []:
            source_value = cell.get("source", "")
            source_text = (
                "".join(source_value)
                if isinstance(source_value, list)
                else str(source_value)
            )
            parse_python_dicts(
                source_text,
                paper_labels=paper_labels,
                evidence_method="ipynb_source_ast_dict",
                source=source,
                rows=rows,
            )
            for output in cell.get("outputs", []) or []:
                if not isinstance(output, dict):
                    continue
                output_texts: list[str] = []
                if "text" in output:
                    text_value = output["text"]
                    output_texts.append(
                        "".join(text_value)
                        if isinstance(text_value, list)
                        else str(text_value)
                    )
                data = output.get("data") or {}
                if isinstance(data, dict):
                    for value in data.values():
                        output_texts.append(
                            "".join(value) if isinstance(value, list) else str(value)
                        )
                for output_text in output_texts:
                    parse_python_literal_outputs(
                        output_text,
                        paper_labels=paper_labels,
                        source=source,
                        rows=rows,
                    )
        return
    if suffix == ".jsonl":
        for line in text.splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                continue
            visit_dict_for_exact_pairs(
                obj,
                paper_labels=paper_labels,
                evidence_method="jsonl_object",
                source=source,
                rows=rows,
            )
        return
    if suffix == ".json":
        try:
            obj = json.loads(text)
        except Exception:
            return
        visit_dict_for_exact_pairs(
            obj,
            paper_labels=paper_labels,
            evidence_method="json_object",
            source=source,
            rows=rows,
        )
        return
    if suffix in {".md", ".txt"}:
        parse_prose_label_index_patterns(
            text,
            paper_labels=paper_labels,
            source=source,
            rows=rows,
        )


def add_rejected_candidate_row(
    *,
    text: str,
    source: BlobSource,
    paper_labels: set[str],
    exact_sources: set[tuple[str, str]],
    rows: list[dict[str, Any]],
) -> None:
    """Record historical co-location without same-object mapping evidence."""

    labels_in_blob = sorted(label for label in paper_labels if label in text)
    if not labels_in_blob:
        return
    has_index_text = (
        "index_in_sae" in text
        or "feature_index" in text
        or re.search(r"\bindex\s+[0-9]+\b", text, flags=re.IGNORECASE) is not None
    )
    if not has_index_text:
        return
    source_key = (source_file(source), source.blob_sha)
    if source_key in exact_sources:
        return
    rows.append(
        {
            "record_type": "candidate_blob",
            "mapping_status": "candidate_rejected_no_same_object_mapping",
            "old_goodfire_label": "",
            "feature_index": "",
            "evidence_method": "co_located_label_and_index_text",
            "source_root": source.alias,
            "source_file": source_file(source),
            "source_commit": "",
            "blob_sha": source.blob_sha,
            "paper_label_count_in_blob": len(labels_in_blob),
            "paper_labels_sample": " | ".join(labels_in_blob[:5]),
        }
    )


AUDIT_COLUMNS = [
    "record_type",
    "mapping_status",
    "old_goodfire_label",
    "feature_index",
    "evidence_method",
    "source_root",
    "source_file",
    "source_commit",
    "blob_sha",
    "paper_label_count_in_blob",
    "paper_labels_sample",
]


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove exact duplicate rows."""

    seen: set[tuple[Any, ...]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(row.get(column, "") for column in AUDIT_COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def find_example_commit(row: dict[str, Any], roots: dict[str, GitRoot]) -> str:
    """Find one reachable commit for a historical blob."""

    root = roots.get(str(row["source_root"]))
    if root is None:
        return ""
    blob_sha = str(row["blob_sha"])
    try:
        return git(
            root,
            "log",
            "--all",
            f"--find-object={blob_sha}",
            "--format=%H",
            "--max-count=1",
        ).strip().splitlines()[0]
    except Exception:
        return ""


def attach_example_commits(rows: list[dict[str, Any]], roots: list[GitRoot]) -> None:
    """Attach an example commit to exact rows and top candidate rows."""

    by_alias = {root.alias: root for root in roots}
    needs_commit = [
        row
        for row in rows
        if row["mapping_status"] == "exact_feature_index_match"
        or int(row.get("paper_label_count_in_blob") or 0) >= 5
    ]
    commit_cache: dict[tuple[str, str], str] = {}
    for row in needs_commit:
        key = (str(row["source_root"]), str(row["blob_sha"]))
        if key not in commit_cache:
            commit_cache[key] = find_example_commit(row, by_alias)
        row["source_commit"] = commit_cache[key]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write audit rows to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize_exact(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize exact mapping evidence."""

    exact_rows = [row for row in rows if row["record_type"] == "exact_mapping_evidence"]
    by_label: dict[str, set[int]] = defaultdict(set)
    sources: dict[tuple[str, int], set[str]] = defaultdict(set)
    methods: dict[tuple[str, int], set[str]] = defaultdict(set)
    commits: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in exact_rows:
        label = str(row["old_goodfire_label"])
        index = int(row["feature_index"])
        key = (label, index)
        by_label[label].add(index)
        sources[key].add(str(row["source_file"]))
        methods[key].add(str(row["evidence_method"]))
        if row.get("source_commit"):
            commits[key].add(str(row["source_commit"]))
    return {
        "exact_rows": exact_rows,
        "by_label": by_label,
        "sources": sources,
        "methods": methods,
        "commits": commits,
    }


def write_report(
    path: Path,
    *,
    rows: list[dict[str, Any]],
    roots: list[GitRoot],
    commit_counts: dict[str, int],
    object_counts: dict[str, int],
    blob_counts: dict[str, int],
    paper_row_count: int,
    paper_label_count: int,
    output_csv: Path,
) -> None:
    """Write a Markdown git-history audit report."""

    exact = summarize_exact(rows)
    exact_rows = exact["exact_rows"]
    by_label = exact["by_label"]
    exact_indices = {int(row["feature_index"]) for row in exact_rows}
    candidate_rows = [
        row
        for row in rows
        if row["mapping_status"] == "candidate_rejected_no_same_object_mapping"
    ]
    method_counts = Counter(row["evidence_method"] for row in exact_rows)
    root_counts = Counter(row["source_root"] for row in rows)
    new_labels = sorted(set(by_label) - set(EXPECTED_BASELINE_MAPPINGS))

    lines = [
        "# Paper Activation Git-History Audit",
        "",
        f"Generated from `{release_path(output_csv)}`.",
        "",
        "This audit searches reachable git history for exact mappings from",
        "historical Goodfire labels to SAE `feature_index` values. The acceptance",
        "rule is strict: the label and index must occur in the same serialized",
        "controller/dictionary object, or in explicit prose of the form",
        "`label (index N)`. Co-located labels and indices in a historical file are",
        "recorded as rejected candidates.",
        "",
        "## Scope",
        "",
        f"- Paper activation rows inspected: {paper_row_count:,}",
        f"- Unique old Goodfire labels inspected: {paper_label_count:,}",
        f"- Git roots searched: {', '.join(root.alias for root in roots)}",
        f"- Reachable commits searched: {sum(commit_counts.values()):,}",
        f"- Reachable git objects enumerated: {sum(object_counts.values()):,}",
        f"- Historical text-like blob paths scanned: {sum(blob_counts.values()):,}",
        f"- Exact mapping evidence rows: {len(exact_rows):,}",
        f"- Unique old labels with exact feature indices: {len(by_label):,}",
        f"- Unique exact feature indices: {len(exact_indices):,}",
        f"- New exact old labels beyond the current crosswalk: {len(new_labels):,}",
        "",
        "## Result",
        "",
    ]
    if new_labels:
        lines.append("Git history recovered additional exact labels that should be reviewed:")
        for label in new_labels:
            lines.append(f"- {label}: {sorted(by_label[label])}")
    else:
        lines.extend(
            [
                "Git history did not recover any additional exact feature-index",
                "mappings beyond the five already used in the paper activation",
                "crosswalk.",
            ]
        )

    lines.extend(
        [
            "",
            "| Old Goodfire label | Feature index | Evidence methods | Historical paths | Example commit |",
            "| --- | ---: | --- | ---: | --- |",
        ]
    )
    for label in sorted(by_label):
        for index in sorted(by_label[label]):
            key = (label, index)
            example_commit = sorted(exact["commits"][key])[0] if exact["commits"][key] else ""
            lines.append(
                "| "
                + " | ".join(
                    [
                        md_cell(label),
                        str(index),
                        md_cell(", ".join(sorted(exact["methods"][key]))),
                        str(len(exact["sources"][key])),
                        example_commit[:12],
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Rejected Historical Co-Location",
            "",
            "These historical blobs contain paper labels and index-like text but no",
            "same-object label/index mapping. They are audit evidence for why nearby",
            "matching is unsafe.",
            "",
            "| Source file | Old labels in blob | Example labels | Example commit |",
            "| --- | ---: | --- | --- |",
        ]
    )
    top_candidates = sorted(
        candidate_rows,
        key=lambda row: (
            -int(row.get("paper_label_count_in_blob") or 0),
            str(row.get("source_file")),
            str(row.get("blob_sha")),
        ),
    )[:12]
    for row in top_candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(row["source_file"]),
                    str(row["paper_label_count_in_blob"]),
                    md_cell(row["paper_labels_sample"]),
                    str(row.get("source_commit", ""))[:12],
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Commits by root: {dict(sorted(commit_counts.items()))}",
            f"- Text-like blob paths by root: {dict(sorted(blob_counts.items()))}",
            f"- Audit rows by root: {dict(sorted(root_counts.items()))}",
            f"- Exact evidence rows by method: {dict(sorted(method_counts.items()))}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_audit(
    *,
    paper_activations: Path,
    roots: list[GitRoot],
) -> tuple[list[dict[str, Any]], int, int, dict[str, int], dict[str, int], dict[str, int]]:
    """Build a git-history audit."""

    labels, paper_row_count = load_paper_labels(paper_activations)
    label_set = set(labels)
    rows: list[dict[str, Any]] = []
    commit_counts: dict[str, int] = {}
    object_counts: dict[str, int] = {}
    blob_counts: dict[str, int] = {}
    exact_source_keys: set[tuple[str, str]] = set()
    deferred_candidates: list[tuple[str, BlobSource, str]] = []

    for root in roots:
        commit_counts[root.alias] = git_count_commits(root)
        sources, object_count = iter_git_blob_sources(root)
        object_counts[root.alias] = object_count
        blob_counts[root.alias] = len(sources)

        by_sha: dict[str, list[BlobSource]] = defaultdict(list)
        for source in sources:
            by_sha[source.blob_sha].append(source)
        contents = batch_load_blobs(root, sorted(by_sha))
        for blob_sha, data in contents.items():
            text = decode_blob(data)
            if not text:
                continue
            has_label = any(label in text for label in label_set)
            if not has_label:
                continue
            has_index_text = (
                "index_in_sae" in text
                or "feature_index" in text
                or re.search(r"\bindex\s+[0-9]+\b", text, flags=re.IGNORECASE) is not None
            )
            if not has_index_text:
                continue
            for source in by_sha[blob_sha]:
                before = len(rows)
                parse_blob_for_exact_pairs(
                    text,
                    source=source,
                    paper_labels=label_set,
                    rows=rows,
                )
                if len(rows) > before:
                    exact_source_keys.add((source_file(source), source.blob_sha))
                deferred_candidates.append((text, source, source.blob_sha))

    rows = dedupe_rows(rows)
    exact_source_keys = {
        (str(row["source_file"]), str(row["blob_sha"]))
        for row in rows
        if row["record_type"] == "exact_mapping_evidence"
    }
    for text, source, _blob_sha in deferred_candidates:
        add_rejected_candidate_row(
            text=text,
            source=source,
            paper_labels=label_set,
            exact_sources=exact_source_keys,
            rows=rows,
        )
    rows = dedupe_rows(rows)
    attach_example_commits(rows, roots)
    rows.sort(
        key=lambda row: (
            str(row["record_type"]),
            str(row["old_goodfire_label"]),
            str(row["feature_index"]),
            str(row["source_root"]),
            str(row["source_file"]),
            str(row["blob_sha"]),
            str(row["evidence_method"]),
        )
    )
    return rows, paper_row_count, len(labels), commit_counts, object_counts, blob_counts


def check_outputs(rows: list[dict[str, Any]]) -> None:
    """Validate the git-history audit."""

    exact = summarize_exact(rows)
    by_label = exact["by_label"]
    for label, indices in EXPECTED_BASELINE_MAPPINGS.items():
        if by_label.get(label) != indices:
            raise AssertionError(f"Missing expected git-history mapping for {label}: {indices}")
    for label, indices in by_label.items():
        if len(indices) != 1:
            raise AssertionError(f"Ambiguous git-history mapping for {label}: {sorted(indices)}")
    for row in rows:
        if row["mapping_status"] == "exact_feature_index_match" and not row["feature_index"]:
            raise AssertionError("Exact git-history audit row is missing feature_index")
        if (
            row["mapping_status"] == "candidate_rejected_no_same_object_mapping"
            and row["feature_index"]
        ):
            raise AssertionError("Rejected git-history candidate unexpectedly has feature_index")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-activations", type=Path, required=True)
    parser.add_argument(
        "--git-root",
        action="append",
        default=[],
        help="Named git root to scan, formatted as alias=/path/to/repo. May be repeated.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data/processed/paper_activation_git_history_audit.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "reports/PAPER_ACTIVATION_GIT_HISTORY_AUDIT.md",
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the git-history audit."""

    args = parse_args()
    if not args.paper_activations.exists():
        raise FileNotFoundError(args.paper_activations)
    roots = [parse_git_root(value) for value in args.git_root]
    if not roots:
        roots = [GitRoot(alias="release_repo", path=REPO_ROOT)]

    rows, paper_row_count, paper_label_count, commit_counts, object_counts, blob_counts = build_audit(
        paper_activations=args.paper_activations,
        roots=roots,
    )
    write_csv(args.output, rows)
    write_report(
        args.report,
        rows=rows,
        roots=roots,
        commit_counts=commit_counts,
        object_counts=object_counts,
        blob_counts=blob_counts,
        paper_row_count=paper_row_count,
        paper_label_count=paper_label_count,
        output_csv=args.output,
    )
    if args.check:
        check_outputs(rows)

    exact = summarize_exact(rows)
    print(
        json.dumps(
            {
                "paper_rows": paper_row_count,
                "paper_unique_labels": paper_label_count,
                "git_roots": [root.alias for root in roots],
                "commits": commit_counts,
                "text_like_blob_paths": blob_counts,
                "audit_rows": len(rows),
                "exact_mapping_evidence_rows": len(exact["exact_rows"]),
                "exact_old_labels": len(exact["by_label"]),
                "exact_feature_indices": len(
                    {int(row["feature_index"]) for row in exact["exact_rows"]}
                ),
                "new_exact_labels_beyond_current_crosswalk": sorted(
                    set(exact["by_label"]) - set(EXPECTED_BASELINE_MAPPINGS)
                ),
                "output": release_path(args.output),
                "report": release_path(args.report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
