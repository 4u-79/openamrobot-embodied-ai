"""Command line entry point: oa-dataset-qa <file.yaml>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import jsonschema
import yaml

from oa_embodied_ai.dataset_qa.validator import (
    find_schema,
    load_registry_file,
    load_schema,
    validate_registry,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="oa-dataset-qa",
        description="Validate a dataset registry entry or registry.yaml (C10 dataset QA).",
    )
    parser.add_argument("file", type=Path, help="registry entry or registry YAML file")
    parser.add_argument("--schema", type=Path, help="path to dataset_registry.schema.json")
    args = parser.parse_args(argv)

    try:
        schema_path = args.schema or find_schema(args.file.parent, Path(__file__).parent)
        schema = load_schema(schema_path)
        data = load_registry_file(args.file)
    except (OSError, ValueError, yaml.YAMLError, jsonschema.SchemaError) as error:
        print(f"oa-dataset-qa: {error}", file=sys.stderr)
        return 2

    count, errors = validate_registry(data, schema)
    if errors:
        for message in errors:
            print(f"{args.file}: {message}", file=sys.stderr)
        print(f"{args.file}: FAILED, {len(errors)} error(s) in {count} entr{'y' if count == 1 else 'ies'}",
              file=sys.stderr)
        return 1
    print(f"{args.file}: OK, {count} entr{'y' if count == 1 else 'ies'} valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
