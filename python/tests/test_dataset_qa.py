"""Tests for C10 dataset QA."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from oa_embodied_ai.dataset_qa import find_schema, load_registry_file, load_schema, validate_registry
from oa_embodied_ai.dataset_qa.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "datasets" / "registry.yaml"


@pytest.fixture(scope="module")
def schema():
    return load_schema(find_schema(FIXTURES))


def test_valid_fixture_passes(schema):
    count, errors = validate_registry(load_registry_file(FIXTURES / "valid_release.yaml"), schema)
    assert (count, errors) == (1, [])


def test_missing_fields_fixture_fails(schema):
    _, errors = validate_registry(load_registry_file(FIXTURES / "invalid_missing_fields.yaml"), schema)
    text = "\n".join(errors)
    for field in ("c9_schema_ref", "sha256", "interfaces_commit"):
        assert f"'{field}' is a required property" in text


def test_bad_values_fixture_fails(schema):
    _, errors = validate_registry(load_registry_file(FIXTURES / "invalid_bad_values.yaml"), schema)
    failing_fields = {message.split(":")[0].rsplit(".", 1)[-1] for message in errors}
    assert {"sha256", "episodes", "c9_schema_ref", "quality_status"} <= failing_fields


def test_capture_date_stays_a_string():
    entry = load_registry_file(FIXTURES / "valid_release.yaml")
    assert entry["capture_date"] == "2026-01-01"


def test_duplicate_dataset_id_fails(schema):
    entry = load_registry_file(FIXTURES / "valid_release.yaml")
    _, errors = validate_registry([entry, dict(entry)], schema)
    assert any("duplicate dataset_id" in message for message in errors)


def test_non_mapping_document_fails(schema):
    _, errors = validate_registry("not a registry", schema)
    assert errors


def test_repository_registry_is_valid(schema):
    count, errors = validate_registry(load_registry_file(REGISTRY), schema)
    assert errors == []
    assert count == 0


def test_registry_commented_example_is_valid(schema):
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    start = lines.index("# Example entry (illustrative values, not a real release):") + 2
    example = []
    for line in lines[start:]:
        if not line.startswith("#"):
            break
        example.append(line[2:])
    data = load_registry_file_from_text("\n".join(example))
    assert validate_registry(data, schema) == (1, [])


def test_cli_exit_codes(capsys):
    assert main([str(FIXTURES / "valid_release.yaml")]) == 0
    assert main([str(FIXTURES / "invalid_missing_fields.yaml")]) == 1
    assert main([str(FIXTURES / "invalid_bad_values.yaml")]) == 1
    assert main([str(REGISTRY)]) == 0
    assert main([str(FIXTURES / "does_not_exist.yaml")]) == 2


def load_registry_file_from_text(text):
    from oa_embodied_ai.dataset_qa.validator import _StringDateLoader

    return yaml.load(text, Loader=_StringDateLoader)  # noqa: S506 safe loader subclass
