from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("assumption_registry.jsonl")
ALLOWED_STATUS = {"draft", "ok", "needs_ref"}


def _require_list_of_strings(name: str, values: object, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{name} must be a list of strings")
    if not allow_empty and len(values) == 0:
        raise ValueError(f"{name} must not be empty")
    for item in values:
        if not isinstance(item, str):
            raise ValueError(f"{name} entries must be strings")
    return list(values)


@dataclass
class InputRef:
    name: str
    unit: str
    provenance: str

    @classmethod
    def from_dict(cls, data: object) -> "InputRef":
        if not isinstance(data, dict):
            raise ValueError("inputs entries must be dictionaries")

        missing = [key for key in ("name", "unit", "provenance") if key not in data]
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
class AssumptionRecord:
    cluster_slug: str
    cluster_title: str
    description: str
    eq_id: str
    source_doc: str
    paper_ref: Optional[str]
    assumption_tags: list[str]
    config_keys: list[str]
    code_path: list[str]
    run_stage: list[str]
    inputs: list[InputRef]
    outputs: list[str]
    tests: list[str]
    status: str
    owner: Optional[str]
    last_checked: Optional[str]
    notes: Optional[str]

    @classmethod
    def from_dict(cls, data: object) -> "AssumptionRecord":
        if not isinstance(data, dict):
            raise ValueError("record must be a dictionary")

        required_keys = [
            "cluster_slug",
            "cluster_title",
            "description",
            "eq_id",
            "source_doc",
            "paper_ref",
            "assumption_tags",
            "config_keys",
            "code_path",
            "run_stage",
            "inputs",
            "outputs",
            "tests",
            "status",
            "owner",
            "last_checked",
            "notes",
        ]
        missing = [key for key in required_keys if key not in data]
        if missing:
            raise ValueError(f"record missing keys: {', '.join(missing)}")

        cluster_slug = data["cluster_slug"]
        cluster_title = data["cluster_title"]
        description = data["description"]
        eq_id = data["eq_id"]
        source_doc = data["source_doc"]
        paper_ref = data.get("paper_ref")
        assumption_tags = _require_list_of_strings("assumption_tags", data["assumption_tags"])
        config_keys = _require_list_of_strings("config_keys", data["config_keys"])
        code_path = _require_list_of_strings("code_path", data["code_path"])
        run_stage = _require_list_of_strings("run_stage", data["run_stage"])
        inputs_raw = data["inputs"]
        outputs = _require_list_of_strings("outputs", data["outputs"])
        tests = _require_list_of_strings("tests", data["tests"])
        status = data["status"]
        owner = data.get("owner")
        last_checked = data.get("last_checked")
        notes = data.get("notes")

        if not isinstance(cluster_slug, str) or not cluster_slug:
            raise ValueError("cluster_slug must be a non-empty string")
        if not isinstance(cluster_title, str) or not cluster_title:
            raise ValueError("cluster_title must be a non-empty string")
        if not isinstance(description, str) or not description:
            raise ValueError("description must be a non-empty string")
        if not isinstance(eq_id, str) or not eq_id:
            raise ValueError("eq_id must be a non-empty string")
        if not isinstance(source_doc, str) or not source_doc:
            raise ValueError("source_doc must be a non-empty string")

        if paper_ref is not None and not isinstance(paper_ref, str):
            raise ValueError("paper_ref must be a string or null")
        if owner is not None and not isinstance(owner, str):
            raise ValueError("owner must be a string or null")
        if last_checked is not None and not isinstance(last_checked, str):
            raise ValueError("last_checked must be a string in YYYY-MM-DD or null")
        if notes is not None and not isinstance(notes, str):
            raise ValueError("notes must be a string or null")

        if not isinstance(inputs_raw, list):
            raise ValueError("inputs must be a list")
        inputs = [InputRef.from_dict(item) for item in inputs_raw]

        return cls(
            cluster_slug=cluster_slug,
            cluster_title=cluster_title,
            description=description,
            eq_id=eq_id,
            source_doc=source_doc,
            paper_ref=paper_ref,
            assumption_tags=assumption_tags,
            config_keys=config_keys,
            code_path=code_path,
            run_stage=run_stage,
            inputs=inputs,
            outputs=outputs,
            tests=tests,
            status=status,
            owner=owner,
            last_checked=last_checked,
            notes=notes,
        )

    def to_dict(self) -> dict:
        return {
            "cluster_slug": self.cluster_slug,
            "cluster_title": self.cluster_title,
            "description": self.description,
            "eq_id": self.eq_id,
            "source_doc": self.source_doc,
            "paper_ref": self.paper_ref,
            "assumption_tags": list(self.assumption_tags),
            "config_keys": list(self.config_keys),
            "code_path": list(self.code_path),
            "run_stage": list(self.run_stage),
            "inputs": [ref.to_dict() for ref in self.inputs],
            "outputs": list(self.outputs),
            "tests": list(self.tests),
            "status": self.status,
            "owner": self.owner,
            "last_checked": self.last_checked,
            "notes": self.notes,
        }


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> list[AssumptionRecord]:
    registry_path = Path(path)
    records: list[AssumptionRecord] = []
    with registry_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_no}: {exc}") from exc
            records.append(AssumptionRecord.from_dict(raw))
    return records


def save_registry(records: Sequence[AssumptionRecord], path: Path | str = DEFAULT_REGISTRY_PATH) -> None:
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False))
            fh.write("\n")


def validate_registry(records: Sequence[AssumptionRecord]) -> list[str]:
    errors: list[str] = []
    seen_slug: set[str] = set()

    for idx, record in enumerate(records):
        prefix = f"[{idx}] {record.cluster_slug}"

        if record.cluster_slug in seen_slug:
            errors.append(f"{prefix}: duplicate cluster_slug")
        else:
            seen_slug.add(record.cluster_slug)

        if not record.eq_id:
            errors.append(f"{prefix}: eq_id is empty")

        if record.status not in ALLOWED_STATUS:
            errors.append(f"{prefix}: invalid status '{record.status}'")

        if record.last_checked is not None and len(record.last_checked) != 10:
            errors.append(f"{prefix}: last_checked should be YYYY-MM-DD or null")

        if not record.assumption_tags:
            errors.append(f"{prefix}: assumption_tags is empty")

    return errors


def find_by_cluster_slug(records: Iterable[AssumptionRecord], slug: str) -> Optional[AssumptionRecord]:
    for record in records:
        if record.cluster_slug == slug:
            return record
    return None


def find_by_config_key(records: Iterable[AssumptionRecord], key: str) -> list[AssumptionRecord]:
    return [record for record in records if key in record.config_keys]


def find_by_tag(records: Iterable[AssumptionRecord], tag: str) -> list[AssumptionRecord]:
    return [record for record in records if tag in record.assumption_tags]


def _print_stats(records: Sequence[AssumptionRecord]) -> None:
    print(f"Total records: {len(records)}")
    print("cluster_slugs:")
    for slug in (record.cluster_slug for record in records):
        print(f"  - {slug}")

    status_counter = Counter(record.status for record in records)
    print("status counts:")
    for status, count in status_counter.items():
        print(f"  {status}: {count}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Assumption registry utilities")
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help="Path to assumption_registry.jsonl",
    )
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
        return 0

    _print_stats(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
