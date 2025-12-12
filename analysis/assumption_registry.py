from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("assumption_registry.jsonl")
ALLOWED_STATUS = {"draft", "ok", "needs_ref"}
ALLOWED_SCOPE = {"project_default", "module_default", "toggle"}
ALLOWED_SOURCE_KIND = {"equation", "config", "code_comment", "test"}


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9:_-]+", "-", value).strip("-")
    cleaned = re.sub(r"-+", "-", cleaned).lower()
    return cleaned or "assumption"


def _ensure_list_of_str(name: str, value: object, allow_empty: bool = True) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [value] if value else []
    else:
        if not isinstance(value, list):
            raise ValueError(f"{name} must be a list of strings or string")
        items = []
        for item in value:
            if isinstance(item, str):
                items.append(item)
            else:
                raise ValueError(f"{name} entries must be strings")
    if not allow_empty and not items:
        raise ValueError(f"{name} must not be empty")
    return items


def _split_eq_ids(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if isinstance(value, str):
        parts = re.split(r"[\/,\s]+", value)
        return [p for p in parts if p]
    raise ValueError("eq_ids/eq_id must be string or list")


@dataclass
class InputRef:
    name: str
    unit: str
    provenance: str

    @classmethod
    def from_dict(cls, data: object) -> "InputRef":
        if not isinstance(data, dict):
            raise ValueError("inputs entries must be dictionaries")
        missing = [k for k in ("name", "unit", "provenance") if k not in data]
        if missing:
            raise ValueError(f"inputs entry missing keys: {', '.join(missing)}")
        name = data["name"]
        unit = data["unit"]
        provenance = data["provenance"]
        if not isinstance(name, str) or not name:
            raise ValueError("inputs.name must be a non-empty string")
        if not isinstance(unit, str) or not unit:
            raise ValueError("inputs.unit must be a non-empty string")
        if not isinstance(provenance, str) or not provenance:
            raise ValueError("inputs.provenance must be a non-empty string")
        return cls(name=name, unit=unit, provenance=provenance)

    def to_dict(self) -> dict:
        return {"name": self.name, "unit": self.unit, "provenance": self.provenance}


@dataclass
class Provenance:
    source_kind: str = "equation"
    paper_key: Optional[str] = None
    unknown_slug: Optional[str] = None
    note: Optional[str] = None
    type: Optional[str] = None

    @classmethod
    def from_dict(cls, data: object) -> "Provenance":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("provenance must be a dict")
        source_kind = data.get("source_kind", "equation")
        paper_key = data.get("paper_key")
        unknown_slug = data.get("unknown_slug")
        note = data.get("note")
        prov_type = data.get("type")
        if source_kind not in ALLOWED_SOURCE_KIND:
            raise ValueError(f"provenance.source_kind must be one of {sorted(ALLOWED_SOURCE_KIND)}")
        for field_name, field_value in (
            ("paper_key", paper_key),
            ("unknown_slug", unknown_slug),
            ("note", note),
            ("type", prov_type),
        ):
            if field_value is not None and not isinstance(field_value, str):
                raise ValueError(f"provenance.{field_name} must be a string or null")
        return cls(source_kind=source_kind, paper_key=paper_key, unknown_slug=unknown_slug, note=note, type=prov_type)

    def to_dict(self) -> dict:
        return {
            "source_kind": self.source_kind,
            "paper_key": self.paper_key,
            "unknown_slug": self.unknown_slug,
            "note": self.note,
            "type": self.type,
        }


@dataclass
class AssumptionRecord:
    id: str
    title: str
    description: str
    scope: Optional[str]
    eq_ids: list[str] = field(default_factory=list)
    assumption_tags: list[str] = field(default_factory=list)
    config_keys: list[str] = field(default_factory=list)
    code_path: list[str] = field(default_factory=list)
    run_stage: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=Provenance)
    tests: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    status: str = "draft"
    last_checked: Optional[str] = None

    @classmethod
    def from_dict(cls, data: object) -> "AssumptionRecord":
        if not isinstance(data, dict):
            raise ValueError("record must be a dictionary")

        # Legacy aliases
        legacy_id = data.get("id") or data.get("cluster_slug") or data.get("slug")
        if not legacy_id:
            legacy_id = _slugify(str(data.get("cluster_title") or data.get("title") or "assumption"))
        title = str(data.get("title") or data.get("cluster_title") or legacy_id)
        description = str(data.get("description") or data.get("notes") or data.get("description_text") or "")
        scope = data.get("scope")
        if scope is not None and scope not in ALLOWED_SCOPE:
            scope = None

        eq_ids = _split_eq_ids(data.get("eq_ids") or data.get("eq_id"))
        assumption_tags = _ensure_list_of_str("assumption_tags", data.get("assumption_tags") or [], allow_empty=True)
        config_keys = _ensure_list_of_str("config_keys", data.get("config_keys") or [], allow_empty=True)
        code_path = _ensure_list_of_str("code_path", data.get("code_path") or [], allow_empty=True)
        run_stage = _ensure_list_of_str("run_stage", data.get("run_stage") or [], allow_empty=True)
        tests = _ensure_list_of_str("tests", data.get("tests") or [], allow_empty=True)
        outputs = _ensure_list_of_str("outputs", data.get("outputs") or [], allow_empty=True)

        status = data.get("status", "draft")
        if status not in ALLOWED_STATUS:
            status = "draft"
        last_checked = data.get("last_checked")
        if last_checked is not None and not isinstance(last_checked, str):
            last_checked = None

        prov_raw = data.get("provenance")
        if prov_raw is None:
            paper_ref = data.get("paper_ref")
            paper_key = None
            if isinstance(paper_ref, str):
                paper_key = paper_ref.split(";")[0].strip() or None
            prov_raw = {"paper_key": paper_key, "source_kind": "equation"}
        provenance = Provenance.from_dict(prov_raw)

        return cls(
            id=legacy_id,
            title=title,
            description=description,
            scope=scope,
            eq_ids=eq_ids,
            assumption_tags=assumption_tags,
            config_keys=config_keys,
            code_path=code_path,
            run_stage=run_stage,
            provenance=provenance,
            tests=tests,
            outputs=outputs,
            status=status,
            last_checked=last_checked,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "scope": self.scope,
            "eq_ids": list(self.eq_ids),
            "assumption_tags": list(self.assumption_tags),
            "config_keys": list(self.config_keys),
            "code_path": list(self.code_path),
            "run_stage": list(self.run_stage),
            "provenance": self.provenance.to_dict(),
            "tests": list(self.tests),
            "outputs": list(self.outputs),
            "status": self.status,
            "last_checked": self.last_checked,
        }


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> list[AssumptionRecord]:
    registry_path = Path(path)
    records: list[AssumptionRecord] = []
    if not registry_path.exists():
        return records
    with registry_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
            records.append(AssumptionRecord.from_dict(raw))
    return records


def dump_registry(records: Iterable[AssumptionRecord], path: Path | str = DEFAULT_REGISTRY_PATH) -> None:
    registry_path = Path(path)
    with registry_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False))
            fh.write("\n")


def validate_registry(records: Iterable[AssumptionRecord]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for record in records:
        if not record.id:
            errors.append("missing id")
        if record.id in seen_ids:
            errors.append(f"duplicate id: {record.id}")
        seen_ids.add(record.id)
        if record.scope and record.scope not in ALLOWED_SCOPE:
            errors.append(f"invalid scope for {record.id}: {record.scope}")
        if record.status not in ALLOWED_STATUS:
            errors.append(f"invalid status for {record.id}: {record.status}")
        if record.provenance.source_kind not in ALLOWED_SOURCE_KIND:
            errors.append(f"invalid source_kind for {record.id}: {record.provenance.source_kind}")
    return errors


def _print_stats(records: list[AssumptionRecord]) -> None:
    print(f"records: {len(records)}")
    status_counter = Counter(record.status for record in records)
    print("status counts:")
    for status, count in status_counter.items():
        print(f"  {status}: {count}")
    scopes = Counter(record.scope or "unspecified" for record in records)
    print("scope counts:")
    for scope, count in scopes.items():
        print(f"  {scope}: {count}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Assumption registry utilities")
    parser.add_argument("--path", type=Path, default=DEFAULT_REGISTRY_PATH, help="Path to assumption_registry.jsonl")
    parser.add_argument("--out", type=Path, help="Write normalised registry to this path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true", help="Validate the registry and report errors")
    group.add_argument("--stats", action="store_true", help="Print basic registry statistics")

    args = parser.parse_args(argv)
    records = load_registry(args.path)

    if args.validate:
        errors = validate_registry(records)
        if errors:
            print("Validation errors:")
            for err in errors:
                print(f"- {err}")
            return 1
        print("Registry OK")
        if args.out:
            dump_registry(records, args.out)
        return 0

    _print_stats(records)
    if args.out:
        dump_registry(records, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
