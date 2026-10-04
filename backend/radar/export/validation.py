"""Offline validation of the fixed UI contract."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_DIR = Path(__file__).with_name("schemas")

def validate(name: str, data) -> None:
    schema = json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(data)
