# oa_embodied_ai

Python tooling for OpenAMRobot embodied AI. Runtime dependencies are PyYAML and jsonschema only.

| Module | Status |
| --- | --- |
| `dataset_qa` | C10: validates dataset registry entries against `schemas/dataset_registry.schema.json` |
| `conversion` | Planned, README only |
| `training` | Planned, README only |
| `evaluation` | Planned, README only |

```bash
pip install -e "python[test]"
oa-dataset-qa datasets/registry.yaml
pytest python/tests
```

`oa-dataset-qa` finds the schema by searching upward from the input file and from this package
for `schemas/dataset_registry.schema.json`. Pass `--schema <path>` to use another file.
