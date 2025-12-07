"""設定ファイルの整合性検証ユーティリティ

このモジュールは、シミュレーション設定の物理的整合性を包括的に検証します。

Usage:
    python -m marsdisk.config_validator configs/scenarios/fiducial.yml
    python -m marsdisk.config_validator --strict configs/scenarios/fiducial.yml
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from marsdisk.schema import Config


class Severity(Enum):
    """検証メッセージの重要度"""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationMessage:
    """検証結果メッセージ"""
    severity: Severity
    code: str
    message: str
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        s = f"[{self.severity.value}] {self.code}: {self.message}"
        if self.suggestion:
            s += f"\n  → 提案: {self.suggestion}"
        return s


@dataclass
class ValidationResult:
    """検証結果の集約"""
    messages: List[ValidationMessage] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(m.severity == Severity.ERROR for m in self.messages)

    @property
    def has_warnings(self) -> bool:
        return any(m.severity == Severity.WARNING for m in self.messages)

    def summary(self) -> str:
        errors = sum(1 for m in self.messages if m.severity == Severity.ERROR)
        warns = sum(1 for m in self.messages if m.severity == Severity.WARNING)
        infos = sum(1 for m in self.messages if m.severity == Severity.INFO)
        return f"検証結果: {errors} errors, {warns} warnings, {infos} info"

    def print_all(self) -> None:
        print(self.summary())
        print("-" * 50)
        for msg in self.messages:
            print(msg)
            print()


def validate_config(config: "Config") -> ValidationResult:
    """設定の整合性を包括的に検証"""
    messages: List[ValidationMessage] = []

    # --- 1. 温度パラメータの整合性 ---
    messages.extend(_check_temperature_consistency(config))

    # --- 2. サイズビンの妥当性 ---
    messages.extend(_check_size_bins(config))

    # --- 3. gas-poor 仮定との整合性 ---
    messages.extend(_check_gas_poor_assumptions(config))

    # --- 4. 円盤幾何の物理的妥当性 ---
    messages.extend(_check_disk_geometry(config))

    # --- 5. 数値パラメータの安定性 ---
    messages.extend(_check_numerical_stability(config))

    # --- 6. 物理モデル間の整合性 ---
    messages.extend(_check_physics_consistency(config))

    return ValidationResult(messages)


def _check_temperature_consistency(config: "Config") -> List[ValidationMessage]:
    """温度パラメータの整合性チェック"""
    msgs: List[ValidationMessage] = []

    # 有効な火星温度を取得
    try:
        TM = config.get_effective_TM_K()
    except Exception:
        msgs.append(ValidationMessage(
            Severity.ERROR,
            "TEMP000",
            "火星温度が未指定です (radiation.TM_K または mars_temperature_driver.constant が必要)",
            "radiation.TM_K もしくは mars_temperature_driver.constant を設定してください"
        ))
        return msgs
    T_sub = config.sinks.T_sub if config.sinks else 1300.0

    # phase thresholds
    T_cond = 1700.0
    T_vap = 2000.0
    if config.phase and config.phase.thresholds:
        T_cond = config.phase.thresholds.T_condense_K
        T_vap = config.phase.thresholds.T_vaporize_K

    # 昇華温度と凝縮温度の関係
    if T_sub > T_cond:
        msgs.append(ValidationMessage(
            Severity.WARNING,
            "TEMP001",
            f"昇華温度 ({T_sub} K) > 凝縮温度 ({T_cond} K)",
            "通常 T_sub ≤ T_condense が物理的に妥当"
        ))

    # 凝縮温度と蒸発温度の順序
    if T_cond >= T_vap:
        msgs.append(ValidationMessage(
            Severity.ERROR,
            "TEMP002",
            f"凝縮温度 ({T_cond} K) ≥ 蒸発温度 ({T_vap} K)",
            "T_condense < T_vaporize に修正してください"
        ))

    # 火星温度と相転移温度の関係
    if TM < T_cond:
        msgs.append(ValidationMessage(
            Severity.INFO,
            "TEMP003",
            f"火星温度 ({TM} K) < 凝縮温度 ({T_cond} K)",
            "円盤は主に固相で進化します"
        ))
    elif TM > T_vap:
        msgs.append(ValidationMessage(
            Severity.WARNING,
            "TEMP004",
            f"火星温度 ({TM} K) > 蒸発温度 ({T_vap} K)",
            "円盤は蒸気相が支配的になる可能性があります"
        ))

    return msgs


def _check_size_bins(config: "Config") -> List[ValidationMessage]:
    """サイズビンの妥当性チェック"""
    msgs: List[ValidationMessage] = []

    s_min = config.sizes.s_min
    s_max = config.sizes.s_max
    n_bins = config.sizes.n_bins

    # 対数範囲が大きすぎないか
    log_range = math.log10(s_max / s_min)
    bins_per_decade = n_bins / log_range

    if bins_per_decade < 5:
        msgs.append(ValidationMessage(
            Severity.WARNING,
            "SIZE001",
            f"ビン解像度が低い ({bins_per_decade:.1f} bins/decade)",
            "n_bins を増やすか、サイズ範囲を狭めてください"
        ))

    # blow-out サイズとの関係（概算）
    # a_blow ~ 1e-6 m (典型的)
    if s_min > 1e-5:
        msgs.append(ValidationMessage(
            Severity.WARNING,
            "SIZE002",
            f"s_min ({s_min} m) がblow-out境界より大きい可能性",
            "s_min ≤ 1e-6 m を推奨"
        ))

    return msgs


def _check_gas_poor_assumptions(config: "Config") -> List[ValidationMessage]:
    """gas-poor 仮定との整合性チェック"""
    msgs: List[ValidationMessage] = []

    if config.sinks and config.sinks.enable_gas_drag:
        if config.sinks.rho_g < 1e-10:
            msgs.append(ValidationMessage(
                Severity.WARNING,
                "GAS001",
                "ガス抗力有効だがガス密度が非常に低い",
                "rho_g を適切に設定するか、enable_gas_drag=false に"
            ))
        else:
            msgs.append(ValidationMessage(
                Severity.INFO,
                "GAS002",
                "gas-rich モードで実行（非標準）",
                "Hyodo et al. 2017 の gas-poor 仮定から逸脱します"
            ))

    return msgs


def _check_disk_geometry(config: "Config") -> List[ValidationMessage]:
    """円盤幾何の物理的妥当性チェック"""
    msgs: List[ValidationMessage] = []

    if config.disk is None:
        return msgs

    r_in = config.disk.geometry.r_in_RM
    r_out = config.disk.geometry.r_out_RM

    # ロッシュ限界（~2.4 R_Mars）との関係
    ROCHE_LIMIT = 2.4

    if r_in > ROCHE_LIMIT:
        msgs.append(ValidationMessage(
            Severity.WARNING,
            "DISK001",
            f"内縁 ({r_in} R_M) がロッシュ限界 (~{ROCHE_LIMIT} R_M) 外",
            "ロッシュ限界内での円盤形成が標準仮定"
        ))

    if r_out > 3.5:
        msgs.append(ValidationMessage(
            Severity.INFO,
            "DISK002",
            f"外縁 ({r_out} R_M) が広い",
            "Deimos 軌道 (~6.9 R_M) より十分内側であることを確認"
        ))

    return msgs


def _check_numerical_stability(config: "Config") -> List[ValidationMessage]:
    """数値パラメータの安定性チェック"""
    msgs: List[ValidationMessage] = []

    safety = config.numerics.safety

    if safety > 0.5:
        msgs.append(ValidationMessage(
            Severity.WARNING,
            "NUM001",
            f"safety factor ({safety}) が大きい",
            "安定性のため safety ≤ 0.1 を推奨"
        ))

    if config.numerics.atol > 1e-8:
        msgs.append(ValidationMessage(
            Severity.INFO,
            "NUM002",
            f"atol ({config.numerics.atol}) がやや緩い",
            "質量保存精度のため atol ≤ 1e-10 を推奨"
        ))

    return msgs


def _check_physics_consistency(config: "Config") -> List[ValidationMessage]:
    """物理モデル間の整合性チェック"""
    msgs: List[ValidationMessage] = []

    # f_wake と τ の関係（高τでのみ意味がある）
    if config.dynamics.f_wake > 1.5:
        msgs.append(ValidationMessage(
            Severity.INFO,
            "PHYS001",
            f"f_wake ({config.dynamics.f_wake}) > 1.5: 自己重力ウェイク効果を仮定",
            "高光学的厚さ (τ > 1) でのみ有効な近似"
        ))

    # wavy PSD と alpha の整合性
    alpha = config.psd.alpha
    wavy = config.psd.wavy_strength
    if wavy > 0 and abs(alpha - 1.83) > 0.2:
        msgs.append(ValidationMessage(
            Severity.INFO,
            "PHYS002",
            f"wavy補正有効だが alpha ({alpha}) が Dohnanyi (1.83) から乖離",
            "wavy 構造は衝突平衡 PSD を前提としています"
        ))

    return msgs


def load_and_validate(config_path: str | Path) -> tuple["Config", ValidationResult]:
    """設定ファイルを読み込んで検証"""
    from ruamel.yaml import YAML

    from marsdisk.schema import Config

    yaml = YAML()
    with open(config_path) as f:
        data = yaml.load(f)

    # メタデータを除去
    data.pop("_scenario", None)
    data.pop("_experimental", None)
    data.pop("_extends", None)

    # pydantic でパース
    config = Config(**data)

    # 検証
    result = validate_config(config)

    return config, result


# =============================================================================
# CLI
# =============================================================================
def main() -> None:
    """コマンドラインから設定を検証"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="設定ファイルの整合性検証",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
    python -m marsdisk.config_validator configs/scenarios/fiducial.yml
    python -m marsdisk.config_validator --strict configs/base_sublimation.yml
        """
    )
    parser.add_argument("config", help="設定ファイルパス")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="警告もエラーとして扱う"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="INFO メッセージを抑制"
    )
    args = parser.parse_args()

    try:
        config, result = load_and_validate(args.config)
    except Exception as e:
        print(f"[ERROR] 設定ファイルの読み込みに失敗: {e}")
        sys.exit(1)

    # 結果の表示
    if args.quiet:
        # INFO を除外
        result.messages = [
            m for m in result.messages
            if m.severity != Severity.INFO
        ]

    result.print_all()

    # 終了コード
    if result.has_errors:
        print("\n❌ 検証失敗（エラーあり）")
        sys.exit(1)
    if args.strict and result.has_warnings:
        print("\n❌ 検証失敗（--strict モードで警告あり）")
        sys.exit(1)

    print("\n✅ 検証完了")


if __name__ == "__main__":
    main()
