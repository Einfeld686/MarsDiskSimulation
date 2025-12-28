#!/usr/bin/env python3
"""Write base override lines from environment variables."""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def is_defined(name: str) -> bool:
    return name in os.environ and os.environ[name] != ""


def not_zero(name: str) -> bool:
    return os.environ.get(name, "") != "0"


def append(lines: list[str], key: str, value: str | None) -> None:
    if value is None or value == "":
        return
    lines.append(f"{key}={value}")


def append_literal(lines: list[str], literal: str) -> None:
    lines.append(literal)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Output overrides file.")
    args = ap.parse_args()

    lines: list[str] = []
    append_literal(lines, "numerics.dt_init=2")
    append(lines, "numerics.stop_on_blowout_below_smin", env("STOP_ON_BLOWOUT_BELOW_SMIN"))
    append_literal(lines, "phase.enabled=true")

    if env("GEOMETRY_MODE", "").upper() == "1D":
        append_literal(lines, "geometry.mode=1D")
        append(lines, "geometry.Nr", env("GEOMETRY_NR"))
        append(lines, "geometry.r_in", env("GEOMETRY_R_IN_M"))
        append(lines, "geometry.r_out", env("GEOMETRY_R_OUT_M"))

    append(lines, "qstar.coeff_units", env("QSTAR_UNITS"))
    append_literal(
        lines,
        "radiation.qpr_table_path=marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv",
    )
    append_literal(lines, "radiation.mars_temperature_driver.enabled=true")

    if env("COOL_MODE", "").lower() == "hyodo":
        append_literal(lines, "radiation.mars_temperature_driver.mode=hyodo")
        append_literal(lines, "radiation.mars_temperature_driver.hyodo.d_layer_m=1.0e5")
        append_literal(lines, "radiation.mars_temperature_driver.hyodo.rho=3000")
        append_literal(lines, "radiation.mars_temperature_driver.hyodo.cp=1000")
    else:
        append_literal(lines, "radiation.mars_temperature_driver.mode=table")
        append_literal(lines, "radiation.mars_temperature_driver.table.time_unit=day")
        append_literal(lines, "radiation.mars_temperature_driver.table.column_time=time_day")
        append_literal(lines, "radiation.mars_temperature_driver.table.column_temperature=T_K")
        append_literal(lines, "radiation.mars_temperature_driver.extrapolation=hold")

    append_literal(lines, "supply.enabled=true")
    append(lines, "supply.mode", env("SUPPLY_MODE"))
    append(lines, "supply.const.mu_orbit10pct", env("SUPPLY_MU_ORBIT10PCT"))
    append(lines, "supply.const.mu_reference_tau", env("SUPPLY_MU_REFERENCE_TAU"))
    append(lines, "supply.const.orbit_fraction_at_mu1", env("SUPPLY_ORBIT_FRACTION"))
    append(lines, "optical_depth.tau_stop", env("OPTICAL_TAU_STOP"))
    append(lines, "optical_depth.tau_stop_tol", env("OPTICAL_TAU_STOP_TOL"))
    append(lines, "shielding.mode", env("SHIELDING_MODE"))

    if is_defined("STREAM_MEM_GB"):
        append(lines, "io.streaming.memory_limit_gb", env("STREAM_MEM_GB"))
        print(f"[info] override io.streaming.memory_limit_gb={env('STREAM_MEM_GB')}")
    if is_defined("STREAM_STEP_INTERVAL"):
        append(lines, "io.streaming.step_flush_interval", env("STREAM_STEP_INTERVAL"))
        print(f"[info] override io.streaming.step_flush_interval={env('STREAM_STEP_INTERVAL')}")

    if is_defined("SUPPLY_RESERVOIR_M"):
        append_literal(lines, "supply.reservoir.enabled=true")
        append(lines, "supply.reservoir.mass_total_Mmars", env("SUPPLY_RESERVOIR_M"))
        append(lines, "supply.reservoir.depletion_mode", env("SUPPLY_RESERVOIR_MODE"))
        append(lines, "supply.reservoir.taper_fraction", env("SUPPLY_RESERVOIR_TAPER"))
        print(
            "[info] supply reservoir: M={m} M_Mars mode={mode} taper_fraction={taper}".format(
                m=env("SUPPLY_RESERVOIR_M", ""),
                mode=env("SUPPLY_RESERVOIR_MODE", ""),
                taper=env("SUPPLY_RESERVOIR_TAPER", ""),
            )
        )

    if not_zero("SUPPLY_FEEDBACK_ENABLED"):
        append_literal(lines, "supply.feedback.enabled=true")
        append(lines, "supply.feedback.target_tau", env("SUPPLY_FEEDBACK_TARGET"))
        append(lines, "supply.feedback.gain", env("SUPPLY_FEEDBACK_GAIN"))
        append(lines, "supply.feedback.response_time_years", env("SUPPLY_FEEDBACK_RESPONSE_YR"))
        append(lines, "supply.feedback.min_scale", env("SUPPLY_FEEDBACK_MIN_SCALE"))
        append(lines, "supply.feedback.max_scale", env("SUPPLY_FEEDBACK_MAX_SCALE"))
        append(lines, "supply.feedback.tau_field", env("SUPPLY_FEEDBACK_TAU_FIELD"))
        append(lines, "supply.feedback.initial_scale", env("SUPPLY_FEEDBACK_INITIAL"))
        print(
            "[info] supply feedback enabled: target_tau={target}, gain={gain}, tau_field={field}".format(
                target=env("SUPPLY_FEEDBACK_TARGET", ""),
                gain=env("SUPPLY_FEEDBACK_GAIN", ""),
                field=env("SUPPLY_FEEDBACK_TAU_FIELD", ""),
            )
        )

    if not_zero("SUPPLY_TEMP_ENABLED"):
        append_literal(lines, "supply.temperature.enabled=true")
        append(lines, "supply.temperature.mode", env("SUPPLY_TEMP_MODE"))
        append(lines, "supply.temperature.reference_K", env("SUPPLY_TEMP_REF_K"))
        append(lines, "supply.temperature.exponent", env("SUPPLY_TEMP_EXP"))
        append(lines, "supply.temperature.scale_at_reference", env("SUPPLY_TEMP_SCALE_REF"))
        append(lines, "supply.temperature.floor", env("SUPPLY_TEMP_FLOOR"))
        append(lines, "supply.temperature.cap", env("SUPPLY_TEMP_CAP"))
        if is_defined("SUPPLY_TEMP_TABLE_PATH"):
            append(lines, "supply.temperature.table.path", env("SUPPLY_TEMP_TABLE_PATH"))
            append(lines, "supply.temperature.table.value_kind", env("SUPPLY_TEMP_TABLE_VALUE_KIND"))
            append(lines, "supply.temperature.table.column_temperature", env("SUPPLY_TEMP_TABLE_COL_T"))
            append(lines, "supply.temperature.table.column_value", env("SUPPLY_TEMP_TABLE_COL_VAL"))
        print(f"[info] supply temperature coupling enabled: mode={env('SUPPLY_TEMP_MODE')}")

    append(lines, "supply.injection.mode", env("SUPPLY_INJECTION_MODE"))
    append(lines, "supply.injection.q", env("SUPPLY_INJECTION_Q"))
    append(lines, "supply.injection.s_inj_min", env("SUPPLY_INJECTION_SMIN"))
    append(lines, "supply.injection.s_inj_max", env("SUPPLY_INJECTION_SMAX"))

    if is_defined("SUPPLY_DEEP_TMIX_ORBITS"):
        append(lines, "supply.transport.t_mix_orbits", env("SUPPLY_DEEP_TMIX_ORBITS"))
        append_literal(lines, "supply.transport.mode=deep_mixing")
        print(
            "[info] deep reservoir enabled (legacy alias): t_mix={val} orbits".format(
                val=env("SUPPLY_DEEP_TMIX_ORBITS", "")
            )
        )

    append(lines, "supply.transport.t_mix_orbits", env("SUPPLY_TRANSPORT_TMIX_ORBITS"))
    append(lines, "supply.transport.mode", env("SUPPLY_TRANSPORT_MODE"))
    append(lines, "supply.transport.headroom_gate", env("SUPPLY_TRANSPORT_HEADROOM"))
    append(lines, "supply.headroom_policy", env("SUPPLY_HEADROOM_POLICY"))

    append(lines, "supply.injection.velocity.mode", env("SUPPLY_VEL_MODE"))
    append(lines, "supply.injection.velocity.e_inj", env("SUPPLY_VEL_E"))
    append(lines, "supply.injection.velocity.i_inj", env("SUPPLY_VEL_I"))
    append(lines, "supply.injection.velocity.vrel_factor", env("SUPPLY_VEL_FACTOR"))
    append(lines, "supply.injection.velocity.blend_mode", env("SUPPLY_VEL_BLEND"))
    append(lines, "supply.injection.velocity.weight_mode", env("SUPPLY_VEL_WEIGHT"))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
