"""Validate a dataset registry entry or a whole registry against the registry schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

SCHEMA_RELPATH = Path("schemas") / "dataset_registry.schema.json"


class _StringDateLoader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings so the schema sees what the file contains."""


_StringDateLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def find_schema(*starts: Path) -> Path:
    """Search upward from each start path for schemas/dataset_registry.schema.json."""
    for start in starts:
        start = Path(start).resolve()
        for directory in (start, *start.parents):
            candidate = directory / SCHEMA_RELPATH
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"could not find {SCHEMA_RELPATH} above {', '.join(map(str, starts))}")


def load_schema(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def load_registry_file(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_StringDateLoader)  # noqa: S506 safe loader subclass


def validate_registry(data: Any, schema: dict[str, Any]) -> tuple[int, list[str]]:
    """Validate one entry (mapping) or a registry (list of entries).

    Returns the number of entries checked and a list of error messages; no errors means valid.
    """
    if isinstance(data, dict):
        entries, labels = [data], ["entry"]
    elif isinstance(data, list):
        entries = data
        labels = [f"entries[{index}]" for index in range(len(data))]
    else:
        kind = "empty" if data is None else type(data).__name__
        return 0, [f"expected a registry entry (mapping) or a registry (list), got {kind}"]

    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors: list[str] = []
    seen: dict[str, str] = {}
    for label, entry in zip(labels, entries):
        if isinstance(entry, dict) and isinstance(entry.get("dataset_id"), str):
            label = f"{label} ({entry['dataset_id']})"
            if entry["dataset_id"] in seen:
                errors.append(f"{label}: duplicate dataset_id, first used by {seen[entry['dataset_id']]}")
            else:
                seen[entry["dataset_id"]] = label
        for error in sorted(validator.iter_errors(entry), key=lambda e: list(e.absolute_path)):
            where = ".".join(str(part) for part in error.absolute_path)
            errors.append(f"{label}{'.' + where if where else ''}: {error.message}")
    return len(entries), errors
