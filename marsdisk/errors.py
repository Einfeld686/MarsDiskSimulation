"""Custom exceptions for the :mod:`marsdisk` package."""
from __future__ import annotations


class MarsDiskError(Exception):
    """Base exception for Mars disk simulation errors."""


class ConfigurationError(MarsDiskError, ValueError):
    """設定ファイルやパラメータ検証のエラー。"""


class PhysicsError(MarsDiskError, ValueError):
    """物理計算で非物理的・不正な値が発生した場合のエラー。"""


class NumericalError(MarsDiskError, RuntimeError):
    """数値計算の収束失敗や安定性違反など、計算上のエラー。"""


class TableLoadError(MarsDiskError, RuntimeError):
    """テーブル読み込みが致命的に失敗した際のエラー。"""


__all__ = [
    "MarsDiskError",
    "ConfigurationError",
    "PhysicsError",
    "NumericalError",
    "TableLoadError",
]
