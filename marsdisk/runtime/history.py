"""History containers used by the zero-D runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

import pyarrow as pa


class ColumnarBuffer:
    """Column-oriented record buffer for streaming-friendly output."""

    def __init__(self, columns: Iterable[str] | None = None) -> None:
        self._columns: Dict[str, List[Any]] = {}
        self._column_order: List[str] = []
        self._row_count = 0
        if columns:
            for name in columns:
                self._columns[name] = []
                self._column_order.append(name)

    @property
    def row_count(self) -> int:
        return self._row_count

    def __len__(self) -> int:
        return self._row_count

    def __bool__(self) -> bool:
        return self._row_count > 0

    def columns(self) -> List[str]:
        return list(self._column_order)

    def append_row(self, record: Mapping[str, Any]) -> None:
        if record is None:
            return
        if not isinstance(record, Mapping):
            record = dict(record)
        for key in record:
            if key not in self._columns:
                self._columns[key] = [None] * self._row_count
                self._column_order.append(key)
        for name in self._column_order:
            self._columns[name].append(record.get(name))
        self._row_count += 1

    def append(self, record: Mapping[str, Any]) -> None:
        self.append_row(record)

    def extend_rows(self, records: Iterable[Mapping[str, Any]]) -> None:
        for record in records:
            self.append_row(record)

    def extend_buffer(self, other: "ColumnarBuffer") -> None:
        if other is self:
            raise ValueError("Cannot extend ColumnarBuffer with itself")
        if other.row_count == 0:
            return
        for key in other._column_order:
            if key not in self._columns:
                self._columns[key] = [None] * self._row_count
                self._column_order.append(key)
        other_rows = other.row_count
        for key in self._column_order:
            values = self._columns[key]
            other_values = other._columns.get(key)
            if other_values is None:
                values.extend([None] * other_rows)
            else:
                values.extend(other_values)
        self._row_count += other_rows

    def set_column_constant(self, name: str, value: Any) -> None:
        if name not in self._columns:
            self._columns[name] = [None] * self._row_count
            self._column_order.append(name)
        if self._row_count == 0:
            return
        self._columns[name] = [value] * self._row_count

    def clear(self) -> None:
        for values in self._columns.values():
            values.clear()
        self._row_count = 0

    def to_records(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for idx in range(self._row_count):
            row: Dict[str, Any] = {}
            for name in self._column_order:
                values = self._columns.get(name, [])
                row[name] = values[idx] if idx < len(values) else None
            rows.append(row)
        return rows

    def to_table(self, ensure_columns: Iterable[str] | None = None) -> pa.Table:
        ensure_list = list(ensure_columns) if ensure_columns is not None else []
        ensure_set = set(ensure_list)
        ordered_names: List[str] = []
        if ensure_list:
            ordered_names.extend(ensure_list)
        for name in self._column_order:
            if name not in ensure_set:
                ordered_names.append(name)
        data: Dict[str, List[Any]] = {}
        for name in ordered_names:
            if name in self._columns:
                data[name] = self._columns[name]
            else:
                data[name] = [None] * self._row_count
        return pa.Table.from_pydict(data)


@dataclass
class ZeroDHistory:
    """Per-step history bundle used by the full-feature zero-D driver."""

    records: List[Dict[str, Any]] | ColumnarBuffer = field(default_factory=list)
    psd_hist_records: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] | ColumnarBuffer = field(default_factory=list)
    mass_budget: List[Dict[str, float]] = field(default_factory=list)
    mass_budget_cells: List[Dict[str, float]] = field(default_factory=list)
    step_diag_records: List[Dict[str, Any]] = field(default_factory=list)
    debug_records: List[Dict[str, Any]] = field(default_factory=list)
    orbit_rollup_rows: List[Dict[str, float]] = field(default_factory=list)
    temperature_track: List[float] = field(default_factory=list)
    beta_track: List[float] = field(default_factory=list)
    ablow_track: List[float] = field(default_factory=list)
    gate_factor_track: List[float] = field(default_factory=list)
    t_solid_track: List[float] = field(default_factory=list)
    extended_total_rate_track: List[float] = field(default_factory=list)
    extended_total_rate_time_track: List[float] = field(default_factory=list)
    extended_ts_ratio_track: List[float] = field(default_factory=list)
    mass_budget_violation: Optional[Dict[str, float]] = None
    violation_triggered: bool = False
    tau_gate_block_time: float = 0.0
    total_time_elapsed: float = 0.0
