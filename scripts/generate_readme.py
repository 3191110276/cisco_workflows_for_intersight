#!/usr/bin/env python3
"""Generate the workflow catalog embedded in README.md."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
START_MARKER = "<!-- BEGIN GENERATED WORKFLOW CATALOG -->"
END_MARKER = "<!-- END GENERATED WORKFLOW CATALOG -->"
# Validation marks requested by the user on October 22, 2026.
VALIDATED_WORKFLOW_IDS = frozenset({
    'definition_workflow_02XRJDF2FUHSO3HtFwPPkJV2NMJpxcIoiPS',
    'definition_workflow_02XP0RZYOPW3K5uNxe1lxsEKYitrytU7ppX',
    'definition_workflow_02XOKCY8L727P2I1njlKiu2ypB4dBBGZlFn',
    'definition_workflow_02XOKCY8L72750O16dIOUNNs1cg8DXkf6Hq',
    'definition_workflow_02XOKCY8L727B7OOCP8uxBfJRJdbgfhqpkd',
    'definition_workflow_02XP097ZMQU745jOdPbsN5Aa8WP1nK8RtrE',
    'definition_workflow_02XOKCY8L727N6XRbUaRIiFCevRevuGnIMH',
    'definition_workflow_02Z9OCT19FIX0040ae20ce543829d5ec413',
})
INTERNAL_HELPER_IDS = frozenset({
    "definition_workflow_02Z3AAXNVAM5J0U5WnISWfQYpmPub7WNRcv",  # JSON field facts
    "definition_workflow_02Z3AAXNVAM5J0xM0D2y8biAn7z2tVtcqCp",  # Error formatter
    "definition_workflow_02Z3AAXNVAM5J0GKOTHddwSfPM4yIPtuayy",  # Collection facts
    "definition_workflow_02Z3AAXNVAM5J0ZVf4y38LuOgNTLyGMs1pX",  # Organization recipe
})


@dataclass(frozen=True)
class Definition:
    kind: str
    name: str
    description: str
    unique_name: str
    dependencies: tuple[str, ...]
    path: Path


def load_definition(path: Path, kind: str) -> Definition:
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        workflow = document["workflow"]
        properties = workflow.get("properties", {})
        name = workflow.get("name") or workflow.get("title")
        unique_name = workflow["unique_name"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"Cannot read workflow metadata from {path}: {error}") from error

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Workflow name is missing in {path}")
    if not isinstance(unique_name, str) or not unique_name.strip():
        raise ValueError(f"Workflow unique_name is missing in {path}")

    description = properties.get("description", "")
    if not isinstance(description, str):
        description = str(description)
    raw_dependencies = document.get("atomic_workflows", [])
    if not isinstance(raw_dependencies, list) or not all(
        isinstance(item, str) for item in raw_dependencies
    ):
        raise ValueError(f"atomic_workflows must be a list of IDs in {path}")

    return Definition(
        kind=kind,
        name=name.strip(),
        description=" ".join(description.split()),
        unique_name=unique_name.strip(),
        dependencies=tuple(raw_dependencies),
        path=path,
    )


def discover_definitions() -> list[Definition]:
    definitions: list[Definition] = []
    for kind in ("Atomics", "Workflows"):
        directory = ROOT / kind
        for path in sorted(directory.glob("*/*.json")):
            definitions.append(load_definition(path, kind))

    unique_names: dict[str, Path] = {}
    for definition in definitions:
        previous = unique_names.get(definition.unique_name)
        if previous:
            raise ValueError(
                f"Duplicate workflow ID {definition.unique_name}: {previous} and {definition.path}"
            )
        unique_names[definition.unique_name] = definition.path
    return definitions


def markdown_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


def display_name(definition: Definition) -> str:
    return definition.name.removeprefix("Cisco Intersight - ")


def is_internal_helper(definition: Definition) -> bool:
    return (definition.name.startswith("Cisco Intersight - Native ")
            or definition.unique_name in INTERNAL_HELPER_IDS)


def markdown_link(definition: Definition) -> str:
    relative_path = definition.path.relative_to(ROOT).as_posix()
    target = quote(relative_path, safe="/._-~")
    return f"[{markdown_text(display_name(definition))}]({target})"


def html_link(definition: Definition) -> str:
    relative_path = definition.path.relative_to(ROOT).as_posix()
    target = quote(relative_path, safe="/._-~")
    return (
        f'<a href="{html.escape(target, quote=True)}">'
        f"{html.escape(display_name(definition))}</a>"
    )


def summary(description: str) -> str:
    if not description:
        return "No description provided."
    match = re.search(r"(?<=[.!?])\s", description)
    first_sentence = description[: match.start()] if match else description
    return markdown_text(first_sentence)


def validation_indicator(definition: Definition, validated_ids: set[str]) -> str:
    return "✅" if definition.unique_name in validated_ids else "❌"


def render_catalog(definitions: list[Definition]) -> str:
    atomics = sorted(
        (item for item in definitions if item.kind == "Atomics"),
        key=lambda item: item.name.casefold(),
    )
    workflows = sorted(
        (item for item in definitions if item.kind == "Workflows"),
        key=lambda item: item.name.casefold(),
    )
    atomics_by_id = {item.unique_name: item for item in atomics}
    definitions_by_id = {item.unique_name: item for item in definitions}

    missing_validated_workflows = VALIDATED_WORKFLOW_IDS - definitions_by_id.keys()
    if missing_validated_workflows:
        raise ValueError(
            "Validated workflow IDs are missing from the repository: "
            + ", ".join(sorted(missing_validated_workflows))
        )

    unknown_dependencies = sorted(
        {
            dependency
            for workflow in definitions
            for dependency in workflow.dependencies
            if dependency not in atomics_by_id
        }
    )
    if unknown_dependencies:
        raise ValueError(
            "Workflow catalog contains unknown atomic dependencies: "
            + ", ".join(unknown_dependencies)
        )

    validated_ids = set(VALIDATED_WORKFLOW_IDS)
    for workflow in workflows:
        if workflow.unique_name in VALIDATED_WORKFLOW_IDS:
            validated_ids.update(workflow.dependencies)

    lines = [
        START_MARKER,
        "# Workflows",
        "",
        "| Validation | Workflow | Purpose | Required atomics |",
        "|:---:|---|---|---|",
    ]

    for workflow in workflows:
        dependencies = "".join(
            f"<li>{html_link(atomics_by_id[item])}</li>"
            for item in workflow.dependencies
        )
        dependencies = f"<ul>{dependencies}</ul>" if dependencies else "None"
        lines.append(
            f"| {validation_indicator(workflow, validated_ids)} "
            f"| {markdown_link(workflow)} | {summary(workflow.description)} "
            f"| {dependencies} |"
        )

    lines.extend(
        [
            "",
            "# Atomics",
            "",
            "Import the listed dependencies before parent workflows. Development recipes and characterization helpers are listed separately below.",
            "",
            "| Validation | Atomic workflow | Purpose | Dependencies |",
            "|:---:|---|---|---|",
        ]
    )
    for atomic in atomics:
        if is_internal_helper(atomic):
            continue
        dependencies = ", ".join(markdown_link(atomics_by_id[item]) for item in atomic.dependencies) or "None"
        lines.append(
            f"| {validation_indicator(atomic, validated_ids)} "
            f"| {markdown_link(atomic)} | {summary(atomic.description)} | {dependencies} |"
        )

    internal = [item for item in atomics if is_internal_helper(item)]
    if internal:
        lines.extend(["", "<details>", f"<summary>Shared dependencies and development recipes ({len(internal)})</summary>", "", "Required parent dependencies are linked in the workflow table. Other exports here preserve migration recipes and characterization contracts. All atomic exports are now flat after repairing the remaining 23 internal helpers. Check cloud import and runtime validation separately for each export. Local checks do not certify warning-free imports.", "", "| Helper | Purpose |", "|---|---|"])
        lines.extend(f"| {markdown_link(item)} | {summary(item.description)} |" for item in internal)
        lines.extend(["", "</details>"])

    lines.extend(["", END_MARKER])
    return "\n".join(lines)


def update_readme(current: str, catalog: str) -> str:
    has_start = START_MARKER in current
    has_end = END_MARKER in current
    if has_start != has_end:
        raise ValueError("README.md contains only one workflow catalog marker")

    if has_start:
        before, remainder = current.split(START_MARKER, 1)
        _, after = remainder.split(END_MARKER, 1)
        return before.rstrip() + "\n\n" + catalog + after.rstrip() + "\n"

    return current.rstrip() + "\n\n" + catalog + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if README.md does not match the generated catalog",
    )
    arguments = parser.parse_args()

    try:
        current = README.read_text(encoding="utf-8")
        expected = update_readme(current, render_catalog(discover_definitions()))
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if arguments.check:
        if current != expected:
            print("README.md workflow catalog is out of date", file=sys.stderr)
            print("Run: python3 scripts/generate_readme.py", file=sys.stderr)
            return 1
        print("README.md workflow catalog is up to date")
        return 0

    README.write_text(expected, encoding="utf-8")
    print(f"Updated {README.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
