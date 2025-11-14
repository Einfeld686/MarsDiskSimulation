"""SiO2 disk cooling simulation and documentation updater.

This script evaluates the radiative cooling of the Martian surface and the
resulting equilibrium temperature of SiO2 dust grains located between
1.0--2.4 Martian radii. The model assumes optically thin conditions without
mutual irradiation, the dust grains remain at fixed orbital radii, and
thermal inertia is neglected so that grain temperatures instantaneously match
the radiative equilibrium value. Glass transition (1475 K) and liquidus
(1986 K) thresholds representative of pure SiO2 are adopted; variations with
composition or pressure are not considered.
"""
from __future__ import annotations

import csv
import math
import statistics
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

try:
    import matplotlib

    matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:  # pragma: no cover - fallback for minimal environments
    matplotlib = None
    plt = None
    HAS_MATPLOTLIB = False

if HAS_MATPLOTLIB:
    plt.rcParams["font.size"] = 12

    def _configure_japanese_font() -> None:
        """Pick a CJK-capable font so matplotlib renders Japanese labels."""

        try:
            from matplotlib import font_manager
        except Exception:
            return

        candidate_fonts = [
            "Hiragino Sans",
            "Hiragino Kaku Gothic ProN",
            "Yu Gothic",
            "YuGothic",
            "Yu Gothic UI",
            "IPAexGothic",
            "IPAPGothic",
            "Noto Sans CJK JP",
            "Noto Sans JP",
            "TakaoPGothic",
            "MS Gothic",
        ]
        available = {font.name for font in font_manager.fontManager.ttflist}
        for font_name in candidate_fonts:
            if font_name in available:
                plt.rcParams["font.family"] = font_name
                plt.rcParams["font.sans-serif"] = [font_name]
                return

        # Fallback: still register candidate list so that once installed it'll be used.
        plt.rcParams["font.family"] = candidate_fonts

    _configure_japanese_font()

# ---------------------------------------------------------------------------
# 定数定義
# ---------------------------------------------------------------------------
SIGMA = 5.670374419e-8  # Stefan-Boltzmann constant [W/m^2/K^4]
R_MARS = 3.3895e6  # Martian radius [m]
RHO = 3000.0  # Regolith density [kg/m^3]
CP = 1000.0  # Specific heat [J/(kg K)]
D_LAYER = 1.0e5  # Thickness of the cooling layer [m]
DT_HOURS = 6.0  # Time resolution [hours]
YEARS = 2.0  # Total simulation duration [years]
YEAR_SECONDS = 365.25 * 24 * 3600
DT_SECONDS = DT_HOURS * 3600.0
N_R = 300  # Number of radial grid points
R_RATIO_MIN = 1.0
R_RATIO_MAX = 2.4
T0_LIST = [6000.0, 4000.0, 2000.0]  # Initial surface temperatures [K]
T_GLASS = 1475.0  # Glass transition temperature [K]
T_LIQUIDUS = 1986.0  # Liquidus temperature [K]
ISOTHERM_LEVELS = [2000.0, 1700.0, 1500.0]
OUTPUT_FILES = {
    6000.0: ("map_T0_6000K.png", "times_T0_6000K.csv"),
    4000.0: ("map_T0_4000K.png", "times_T0_4000K.csv"),
    2000.0: ("map_T0_2000K.png", "times_T0_2000K.csv"),
}


@dataclass(frozen=True)
class Params:
    """Parameter set passed to the thermal model."""

    sigma: float = SIGMA
    rho: float = RHO
    cp: float = CP
    d_layer: float = D_LAYER
    r_mars: float = R_MARS
    year_seconds: float = YEAR_SECONDS


PARAMS = Params()


# ---------------------------------------------------------------------------
# モデル関数
# ---------------------------------------------------------------------------
def tmars(time_s: List[float], t0: float, params: Params = PARAMS) -> List[float]:
    """Return the Martian surface temperature evolution.

    Parameters
    ----------
    time_s:
        Time array [s].
    t0:
        Initial temperature [K].
    params:
        Collection of physical constants.

    Returns
    -------
    List[float]
        Temperature [K] at each time sample.
    """

    coeff = params.sigma / (params.d_layer * params.rho * params.cp)
    # 解析解 T_Mars(t) = (T0^{-3} + 3 σ t / (D ρ c_p))^{-1/3}
    base = t0 ** -3
    return [(base + 3.0 * coeff * t) ** (-1.0 / 3.0) for t in time_s]


def tp_of_rt(
    radii_m: List[float],
    time_s: List[float],
    t0: float,
    params: Params = PARAMS,
) -> List[List[float]]:
    """Return the grain temperature field for given radii and times."""

    mars_temp = tmars(time_s, t0, params)
    field: List[List[float]] = []
    for radius_m in radii_m:
        factor = math.sqrt(params.r_mars / (2.0 * radius_m))
        field.append([temp * factor for temp in mars_temp])
    return field


def first_crossing_time(
    radius_m: float,
    t0: float,
    tcrit: float,
    time_s: List[float],
    params: Params = PARAMS,
) -> float:
    """Return the first time [s] when T_p <= tcrit; NaN if not reached."""

    temps = tp_of_rt([radius_m], time_s, t0, params)[0]
    for idx, temp in enumerate(temps):
        if temp <= tcrit:
            return float(time_s[idx])
    return math.nan


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------
def ensure_directory(path: Path) -> None:
    """Create directory if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)


def format_range(r_values: List[float], times: List[float]) -> str:
    """Format radial range string for summary output."""

    valid = [r for r, t in zip(r_values, times) if not math.isnan(t)]
    if not valid:
        return "到達なし"
    return f"{min(valid):.3f}–{max(valid):.3f} R_Mars"


def representative_time(times: List[float]) -> str:
    """Return a representative time in years for logging."""

    finite = sorted(t for t in times if not math.isnan(t))
    if not finite:
        return "該当なし"
    median = statistics.median(finite)
    return f"{median:.3f} 年"


def compute_crossing_times(
    temp_matrix: List[List[float]],
    threshold: float,
    time_s: List[float],
) -> List[float]:
    """Compute first crossing time for each radius in a matrix."""

    results: List[float] = []
    for row in temp_matrix:
        crossing = math.nan
        for time_val, temp in zip(time_s, row):
            if temp <= threshold:
                crossing = time_val / YEAR_SECONDS
                break
        results.append(crossing)
    return results


def build_arrival_field(times_years: List[float], time_years: List[float]) -> List[List[float]]:
    """Construct a 2D field where cells retain arrival time once reached."""

    field: List[List[float]] = []
    for value in times_years:
        row: List[float] = []
        for t in time_years:
            if math.isnan(value) or t < value:
                row.append(math.nan)
            else:
                row.append(value)
        field.append(row)
    return field


def upsert_marked_block(path: Path, marker_begin: str, marker_end: str, body: str) -> None:
    """Insert or replace a marked text block in the target file."""

    block = f"{marker_begin}\n{body.strip()}\n{marker_end}\n"
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = ""

    if marker_begin in text and marker_end in text:
        start = text.index(marker_begin)
        end = text.index(marker_end) + len(marker_end)
        new_text = text[:start] + block + text[end:]
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        new_text = text + ("\n" if text else "") + block

    path.write_text(new_text, encoding="utf-8")


def create_simulation_readme(path: Path) -> None:
    """Create or overwrite the simulation specific README."""

    lines = [
        "# SiO₂ Disk Cooling シミュレーション",
        "",
        "このフォルダでは、火星表面が黒体放射で冷却すると仮定した場合の SiO₂ 粒子の距離×時間マップを生成します。",  # noqa: E501
        "",
        "## 物理モデル",
        "- 冷却方程式: $\\frac{dT}{dt}=-(\\sigma/(D\\rho c_p))T^4$",
        "- 解析解: $T_{\\mathrm{Mars}}(t)=(T_0^{-3}+3\\sigma t/(D\\rho c_p))^{-1/3}$",
        "- 粒子温度: $T_p(r,t)=T_{\\mathrm{Mars}}(t)\\sqrt{R_{\\mathrm{Mars}}/(2r)}$",
        "- 閾値: $T_{\\mathrm{glass}}=1475~\\mathrm{K}$, $T_{\\mathrm{liquidus}}=1986~\\mathrm{K}$",
        "",
        "## パラメータ",
        "| 記号 | 値 | 単位 |",
        "| --- | --- | --- |",
        "| $R_{\\mathrm{Mars}}$ | $3.3895\\times10^6$ | m |",
        "| $\\sigma$ | $5.670374419\\times10^{-8}$ | W m$^{-2}$ K$^{-4}$ |",
        "| $\\rho$ | 3000 | kg m$^{-3}$ |",
        "| $c_p$ | 1000 | J kg$^{-1}$ K$^{-1}$ |",
        "| $D$ | $1.0\\times10^5$ | m |",
        "| 時間グリッド | 0–2 年 (6 時間刻み) | - |",
        "| 距離グリッド | $r/R_{\\mathrm{Mars}}=1.0–2.4$ (300 分割) | - |",
        "",
        "## 実行方法",
        "```",
        "python siO2_disk_cooling/siO2_cooling_map.py",
        "```",
        "",
        "## 出力物",
        "- PNG: 各初期温度ごとの到達時刻マップ (glass/liquidus)",
        "- CSV: `r_over_Rmars`, `t_to_Tglass_yr`, `t_to_Tliquidus_yr`",
        "",
        "## 注意事項",
        "- 光学的に薄い円盤を仮定し、太陽や粒子間の相互放射は無視しています。",
        "- 粒子半径は固定で熱容量の効果を無視し、準静的平衡温度を用いています。",
        "- 閾値は純粋な SiO₂ に対する代表値であり、混合物や圧力依存性は考慮していません。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# フォールバック描画ユーティリティ（matplotlib が無い環境向け）
# ---------------------------------------------------------------------------
FONT_5X7 = {
    " ": ["     "] * 7,
    "0": [
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "1": [
        "  #  ",
        " ##  ",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
        " ### ",
    ],
    "2": [
        " ### ",
        "#   #",
        "    #",
        "   # ",
        "  #  ",
        " #   ",
        "#####",
    ],
    "3": [
        " ### ",
        "#   #",
        "    #",
        " ### ",
        "    #",
        "#   #",
        " ### ",
    ],
    "4": [
        "#   #",
        "#   #",
        "#   #",
        "#####",
        "    #",
        "    #",
        "    #",
    ],
    "5": [
        "#####",
        "#    ",
        "#    ",
        "#### ",
        "    #",
        "#   #",
        " ### ",
    ],
    "6": [
        " ### ",
        "#   #",
        "#    ",
        "#### ",
        "#   #",
        "#   #",
        " ### ",
    ],
    "7": [
        "#####",
        "    #",
        "   # ",
        "  #  ",
        " #   ",
        "#    ",
        "#    ",
    ],
    "8": [
        " ### ",
        "#   #",
        "#   #",
        " ### ",
        "#   #",
        "#   #",
        " ### ",
    ],
    "9": [
        " ### ",
        "#   #",
        "#   #",
        " ####",
        "    #",
        "#   #",
        " ### ",
    ],
    "A": [
        " ### ",
        "#   #",
        "#   #",
        "#####",
        "#   #",
        "#   #",
        "#   #",
    ],
    "B": [
        "#### ",
        "#   #",
        "#   #",
        "#### ",
        "#   #",
        "#   #",
        "#### ",
    ],
    "C": [
        " ### ",
        "#   #",
        "#    ",
        "#    ",
        "#    ",
        "#   #",
        " ### ",
    ],
    "D": [
        "#### ",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#### ",
    ],
    "E": [
        "#####",
        "#    ",
        "#    ",
        "#### ",
        "#    ",
        "#    ",
        "#####",
    ],
    "F": [
        "#####",
        "#    ",
        "#    ",
        "#### ",
        "#    ",
        "#    ",
        "#    ",
    ],
    "G": [
        " ### ",
        "#   #",
        "#    ",
        "# ###",
        "#   #",
        "#   #",
        " ### ",
    ],
    "H": [
        "#   #",
        "#   #",
        "#   #",
        "#####",
        "#   #",
        "#   #",
        "#   #",
    ],
    "I": [
        " ### ",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
        " ### ",
    ],
    "J": [
        "  ###",
        "   # ",
        "   # ",
        "   # ",
        "#  # ",
        "#  # ",
        " ##  ",
    ],
    "K": [
        "#   #",
        "#  # ",
        "# #  ",
        "##   ",
        "# #  ",
        "#  # ",
        "#   #",
    ],
    "L": [
        "#    ",
        "#    ",
        "#    ",
        "#    ",
        "#    ",
        "#    ",
        "#####",
    ],
    "M": [
        "#   #",
        "## ##",
        "# # #",
        "# # #",
        "#   #",
        "#   #",
        "#   #",
    ],
    "N": [
        "#   #",
        "##  #",
        "# # #",
        "#  ##",
        "#   #",
        "#   #",
        "#   #",
    ],
    "O": [
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "P": [
        "#### ",
        "#   #",
        "#   #",
        "#### ",
        "#    ",
        "#    ",
        "#    ",
    ],
    "Q": [
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        "# # #",
        "#  # ",
        " ## #",
    ],
    "R": [
        "#### ",
        "#   #",
        "#   #",
        "#### ",
        "# #  ",
        "#  # ",
        "#   #",
    ],
    "S": [
        " ####",
        "#    ",
        "#    ",
        " ### ",
        "    #",
        "    #",
        "#### ",
    ],
    "T": [
        "#####",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
    ],
    "U": [
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "V": [
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " # # ",
        " # # ",
        "  #  ",
    ],
    "W": [
        "#   #",
        "#   #",
        "#   #",
        "# # #",
        "# # #",
        "## ##",
        "#   #",
    ],
    "X": [
        "#   #",
        "#   #",
        " # # ",
        "  #  ",
        " # # ",
        "#   #",
        "#   #",
    ],
    "Y": [
        "#   #",
        "#   #",
        " # # ",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
    ],
    "Z": [
        "#####",
        "    #",
        "   # ",
        "  #  ",
        " #   ",
        "#    ",
        "#####",
    ],
    "-": [
        "     ",
        "     ",
        "     ",
        " ### ",
        "     ",
        "     ",
        "     ",
    ],
    "=": [
        "     ",
        "     ",
        " ### ",
        "     ",
        " ### ",
        "     ",
        "     ",
    ],
    "<": [
        "   # ",
        "  #  ",
        " #   ",
        "#    ",
        " #   ",
        "  #  ",
        "   # ",
    ],
    ">": [
        "#    ",
        " #   ",
        "  #  ",
        "   # ",
        "  #  ",
        " #   ",
        "#    ",
    ],
    "[": [
        " ### ",
        " #   ",
        " #   ",
        " #   ",
        " #   ",
        " #   ",
        " ### ",
    ],
    "]": [
        " ### ",
        "   # ",
        "   # ",
        "   # ",
        "   # ",
        "   # ",
        " ### ",
    ],
    "_": [
        "     ",
        "     ",
        "     ",
        "     ",
        "     ",
        "     ",
        "#####",
    ],
    "/": [
        "    #",
        "   # ",
        "   # ",
        "  #  ",
        " #   ",
        "#    ",
        "#    ",
    ],
    ".": [
        "     ",
        "     ",
        "     ",
        "     ",
        "     ",
        " ##  ",
        " ##  ",
    ],
}

FONT_WIDTH = 5
FONT_HEIGHT = 7


def _uppercase_char(ch: str) -> str:
    return ch.upper() if "A" <= ch <= "Z" else ch


def draw_char(image: List[List[List[int]]], ch: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    pattern = FONT_5X7.get(_uppercase_char(ch), FONT_5X7.get(" "))
    if pattern is None:
        return
    height = len(image)
    width = len(image[0]) if height else 0
    for row, line in enumerate(pattern):
        for col, pixel in enumerate(line):
            if pixel == "#":
                yy = y + row
                xx = x + col
                if 0 <= yy < height and 0 <= xx < width:
                    image[yy][xx] = [color[0], color[1], color[2]]


def draw_text(
    image: List[List[List[int]]],
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    cursor = x
    for ch in text:
        if ch == "\n":
            y += FONT_HEIGHT + 2
            cursor = x
            continue
        draw_char(image, ch, cursor, y, color)
        cursor += FONT_WIDTH + 1


def draw_vertical_text(
    image: List[List[List[int]]],
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    cursor_y = y
    for ch in text:
        if ch == " ":
            cursor_y += FONT_HEIGHT + 2
            continue
        draw_char(image, ch, x, cursor_y, color)
        cursor_y += FONT_HEIGHT + 2


def draw_line(
    image: List[List[List[int]]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    height = len(image)
    width = len(image[0]) if height else 0
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    while True:
        for ty in range(-thickness // 2, thickness // 2 + 1):
            for tx in range(-thickness // 2, thickness // 2 + 1):
                xx = x0 + tx
                yy = y0 + ty
                if 0 <= xx < width and 0 <= yy < height:
                    image[yy][xx] = [color[0], color[1], color[2]]
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def draw_polyline(
    image: List[List[List[int]]],
    points: List[tuple[int, int]],
    color: tuple[int, int, int],
    thickness: int = 2,
) -> None:
    for start, end in zip(points[:-1], points[1:]):
        draw_line(image, start[0], start[1], end[0], end[1], color, thickness)


def viridis_like(value: float) -> tuple[int, int, int]:
    value = float(max(0.0, min(1.0, value)))
    base = [
        (68, 1, 84),
        (59, 82, 139),
        (33, 145, 140),
        (94, 201, 98),
        (253, 231, 37),
    ]
    segments = len(base) - 1
    pos = value * segments
    idx = min(int(pos), segments - 1)
    frac = pos - idx
    c0 = base[idx]
    c1 = base[min(idx + 1, segments)]
    return tuple(int(round(c0[i] + (c1[i] - c0[i]) * frac)) for i in range(3))


def render_heatmap_array(field: List[List[float]], width: int, height: int) -> List[List[List[int]]]:
    image = [[[255, 255, 255] for _ in range(width)] for _ in range(height)]
    rows = len(field)
    cols = len(field[0]) if rows else 0
    row_max = max(rows - 1, 1)
    col_max = max(cols - 1, 1)
    denom_y = max(height - 1, 1)
    denom_x = max(width - 1, 1)
    for yy in range(height):
        r_pos = row_max * (1 - yy / denom_y)
        r_idx = int(round(max(0.0, min(r_pos, float(row_max)))))
        row_values = field[r_idx]
        for xx in range(width):
            c_pos = col_max * (xx / denom_x)
            c_idx = int(round(max(0.0, min(c_pos, float(col_max)))))
            value = row_values[c_idx]
            if math.isnan(value):
                color = (200, 200, 200)
            else:
                color = viridis_like(value / YEARS)
            image[yy][xx] = [color[0], color[1], color[2]]
    return image


def save_png(image: List[List[List[int]]], path: Path) -> None:
    height = len(image)
    width = len(image[0]) if height else 0
    raw = bytearray()
    for row in image:
        raw.append(0)
        for pixel in row:
            raw.extend(bytes(pixel))
    header = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,
        2,
        0,
        0,
        0,
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    with path.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", header))
        handle.write(chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
        handle.write(chunk(b"IEND", b""))


def render_manual_map(
    time_years: List[float],
    r_ratios: List[float],
    glass_field: List[List[float]],
    liquidus_field: List[List[float]],
    iso_map: Dict[float, List[float]],
    png_path: Path,
    t0: float,
) -> None:
    width, height = 1200, 1000
    canvas = [[[255, 255, 255] for _ in range(width)] for _ in range(height)]

    axis_color = (0, 0, 0)
    panel_left = 160
    panel_right = 930
    panel_width = panel_right - panel_left
    panel_height = 320
    top_top = 120
    top_bottom = top_top + panel_height
    bottom_top = 520
    bottom_bottom = bottom_top + panel_height
    colorbar_left = 980
    colorbar_right = colorbar_left + 40
    colorbar_top = top_top
    colorbar_bottom = bottom_bottom

    time_min, time_max = float(min(time_years)), float(max(time_years))
    r_min, r_max = float(min(r_ratios)), float(max(r_ratios))

    glass_img = render_heatmap_array(glass_field, panel_width, panel_height)
    for yy in range(panel_height):
        for xx in range(panel_width):
            canvas[top_top + yy][panel_left + xx] = glass_img[yy][xx]
    liquidus_img = render_heatmap_array(liquidus_field, panel_width, panel_height)
    for yy in range(panel_height):
        for xx in range(panel_width):
            canvas[bottom_top + yy][panel_left + xx] = liquidus_img[yy][xx]

    draw_line(canvas, panel_left, top_bottom, panel_right - 1, top_bottom, axis_color)
    draw_line(canvas, panel_left, top_top, panel_left, top_bottom, axis_color)
    draw_line(canvas, panel_left, bottom_bottom, panel_right - 1, bottom_bottom, axis_color)
    draw_line(canvas, panel_left, bottom_top, panel_left, bottom_bottom, axis_color)

    time_ticks = [0.0, 0.5, 1.0, 1.5, 2.0]
    radius_ticks = [1.0, 1.4, 1.8, 2.2, 2.4]

    def clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    def map_time_to_x(value: float) -> int:
        frac = clamp((value - time_min) / (time_max - time_min), 0.0, 1.0)
        return panel_left + int(round(frac * (panel_width - 1)))

    def map_radius_to_y(value: float, bottom: int) -> int:
        frac = clamp((value - r_min) / (r_max - r_min), 0.0, 1.0)
        return bottom - int(round(frac * (panel_height - 1)))

    for tick in radius_ticks:
        y_pos = map_radius_to_y(tick, top_bottom)
        draw_line(canvas, panel_left - 6, y_pos, panel_left, y_pos, axis_color)
        draw_text(canvas, f"{tick:.1f}", panel_left - 70, y_pos - FONT_HEIGHT // 2, axis_color)

    for tick in radius_ticks:
        y_pos = map_radius_to_y(tick, bottom_bottom)
        draw_line(canvas, panel_left - 6, y_pos, panel_left, y_pos, axis_color)
        draw_text(canvas, f"{tick:.1f}", panel_left - 70, y_pos - FONT_HEIGHT // 2, axis_color)

    for tick in time_ticks:
        x_pos = map_time_to_x(tick)
        draw_line(canvas, x_pos, bottom_bottom, x_pos, bottom_bottom + 6, axis_color)
        draw_text(canvas, f"{tick:.1f}", x_pos - 12, bottom_bottom + 10, axis_color)

    draw_text(canvas, "TIME [YR]", panel_left + panel_width // 2 - 40, bottom_bottom + 30, axis_color)
    draw_vertical_text(canvas, "RADIUS [R_MARS]", panel_left - 100, top_top + 20, axis_color)

    iso_colors = {
        2000.0: (214, 39, 40),
        1700.0: (31, 119, 180),
        1500.0: (44, 160, 44),
    }

    def plot_iso_lines(panel_bottom: int) -> None:
        for iso, color in iso_colors.items():
            iso_times = iso_map.get(iso)
            if iso_times is None:
                continue
            points: List[tuple[int, int]] = []
            for r_val, t_val in zip(r_ratios, iso_times):
                if math.isnan(t_val):
                    continue
                x_coord = map_time_to_x(float(t_val))
                frac = clamp((r_val - r_min) / (r_max - r_min), 0.0, 1.0)
                y_coord = panel_bottom - int(round(frac * (panel_height - 1)))
                points.append((x_coord, y_coord))
            if len(points) >= 2:
                draw_polyline(canvas, points, color, thickness=2)

    plot_iso_lines(top_bottom)
    plot_iso_lines(bottom_bottom)

    def draw_legend(x: int, y: int) -> None:
        offset = 0
        for iso, color in iso_colors.items():
            draw_line(canvas, x, y + offset, x + 25, y + offset, color, thickness=3)
            draw_text(canvas, f" {int(iso)} K", x + 30, y + offset - FONT_HEIGHT // 2, axis_color)
            offset += 20

    draw_legend(panel_left + 20, top_top + 20)
    draw_legend(panel_left + 20, bottom_top + 20)

    title = f"T0={int(t0)}K COOLING MAP"
    draw_text(canvas, title, panel_left, 60, axis_color)
    draw_text(canvas, "TP<=TGLASS", panel_left + 10, top_top - 30, axis_color)
    draw_text(canvas, "TP<=TLIQUIDUS", panel_left + 10, bottom_top - 30, axis_color)

    cbar_height = colorbar_bottom - colorbar_top
    for idx in range(cbar_height):
        frac = 1 - idx / max(cbar_height - 1, 1)
        color = viridis_like(frac)
        for xx in range(colorbar_left, colorbar_right):
            canvas[colorbar_top + idx][xx] = [color[0], color[1], color[2]]
    draw_line(canvas, colorbar_left, colorbar_top, colorbar_right - 1, colorbar_top, axis_color)
    draw_line(
        canvas,
        colorbar_left,
        colorbar_bottom - 1,
        colorbar_right - 1,
        colorbar_bottom - 1,
        axis_color,
    )
    draw_line(canvas, colorbar_left, colorbar_top, colorbar_left, colorbar_bottom - 1, axis_color)
    draw_line(
        canvas,
        colorbar_right - 1,
        colorbar_top,
        colorbar_right - 1,
        colorbar_bottom - 1,
        axis_color,
    )

    for tick in time_ticks:
        frac = tick / (time_max - time_min)
        y_pos = colorbar_bottom - 1 - int(round(frac * (cbar_height - 1)))
        draw_line(canvas, colorbar_right, y_pos, colorbar_right + 6, y_pos, axis_color)
        draw_text(canvas, f"{tick:.1f}", colorbar_right + 10, y_pos - FONT_HEIGHT // 2, axis_color)

    draw_text(canvas, "ARRIVAL TIME [YR]", colorbar_left - 20, colorbar_top - 30, axis_color)

    save_png(canvas, png_path)

# ---------------------------------------------------------------------------
# ケース実行
# ---------------------------------------------------------------------------
def run_case(
    t0: float,
    radii_m: List[float],
    time_s: List[float],
    r_ratios: List[float],
    outputs_dir: Path,
) -> Dict[str, object]:
    """Execute the cooling analysis for a single initial temperature."""

    temp_matrix = tp_of_rt(radii_m, time_s, t0)

    # 検算: t=0 で距離とともに単調減少
    initial_profile = [row[0] for row in temp_matrix]
    for earlier, later in zip(initial_profile, initial_profile[1:]):
        if later > earlier + 1e-9:
            raise ValueError("粒子温度が距離に対して単調減少になっていません。")

    glass_times = compute_crossing_times(temp_matrix, T_GLASS, time_s)
    liquidus_times = compute_crossing_times(temp_matrix, T_LIQUIDUS, time_s)
    time_years = [t / YEAR_SECONDS for t in time_s]
    glass_field = build_arrival_field(glass_times, time_years)
    liquidus_field = build_arrival_field(liquidus_times, time_years)
    iso_map = {level: compute_crossing_times(temp_matrix, level, time_s) for level in ISOTHERM_LEVELS}

    csv_path = outputs_dir / OUTPUT_FILES[t0][1]
    def _format_csv_value(value: float) -> str:
        return "nan" if math.isnan(value) else f"{value:.6f}"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["r_over_Rmars", "t_to_Tglass_yr", "t_to_Tliquidus_yr"])
        for ratio, glass, liquidus in zip(r_ratios, glass_times, liquidus_times):
            writer.writerow([f"{ratio:.6f}", _format_csv_value(glass), _format_csv_value(liquidus)])

    png_path = outputs_dir / OUTPUT_FILES[t0][0]
    if HAS_MATPLOTLIB:
        try:
            import numpy as np  # type: ignore
        except ImportError:  # pragma: no cover - fallback to manual renderer
            np = None  # type: ignore
        if np is not None:
            fig, axes = plt.subplots(2, 1, figsize=(8, 8), sharex=True, sharey=True)
            cmap = plt.get_cmap("viridis").copy()
            cmap.set_bad("lightgray")
            extent = [min(time_years), max(time_years), min(r_ratios), max(r_ratios)]

            for ax, label, field in [
                (axes[0], "T_p \\le T_{glass}", glass_field),
                (axes[1], "T_p \\le T_{liquidus}", liquidus_field),
            ]:
                field_array = np.array(field, dtype=float)
                mesh = ax.imshow(
                    field_array,
                    aspect="auto",
                    origin="lower",
                    extent=extent,
                    cmap=cmap,
                    interpolation="nearest",
                )
                mesh.set_clim(0, YEARS)
                ax.set_ylabel("r / R_Mars")
                ax.set_title(f"到達時刻 ({label})")

                for isotherm in ISOTHERM_LEVELS:
                    iso_times = np.array(iso_map[isotherm], dtype=float)
                    valid = np.isfinite(iso_times)
                    if not valid.any():
                        continue
                    ax.plot(
                        iso_times[valid],
                        np.array(r_ratios, dtype=float)[valid],
                        linestyle="--",
                        label=f"{int(isotherm)} K",
                    )
                ax.legend(loc="upper right", fontsize=8)

            axes[1].set_xlabel("時間 [年]")
            fig.tight_layout()
            cbar = fig.colorbar(mesh, ax=axes, location="right", fraction=0.05, pad=0.02)
            cbar.set_label("初回到達時刻 [年]")
            fig.savefig(png_path, dpi=200)
            plt.close(fig)
        else:
            render_manual_map(time_years, r_ratios, glass_field, liquidus_field, iso_map, png_path, t0)
    else:
        render_manual_map(time_years, r_ratios, glass_field, liquidus_field, iso_map, png_path, t0)

    summary = {
        "t0": t0,
        "glass_range": format_range(r_ratios, glass_times),
        "glass_representative": representative_time(glass_times),
        "liquidus_range": format_range(r_ratios, liquidus_times),
        "liquidus_representative": representative_time(liquidus_times),
        "csv": csv_path,
        "png": png_path,
    }
    return summary


# ---------------------------------------------------------------------------
# ドキュメント更新
# ---------------------------------------------------------------------------
def update_root_readme(root_path: Path, summaries: List[Dict[str, object]]) -> None:
    """Update the repository README with a summary section."""

    lines = [
        "### SiO₂ disk cooling（距離×時間マップ）",
        "SiO₂ 粒子の温度がガラス転移・液相終端に到達する時刻を距離と時間のマップとして評価するシミュレーションです。",
        "- モデル: $T_{\\mathrm{Mars}}(t)=(T_0^{-3}+3\\sigma t/(D\\rho c_p))^{-1/3}$, $T_p(r,t)=T_{\\mathrm{Mars}}(t)\\sqrt{R_{\\mathrm{Mars}}/(2r)}$",
        "- 実行方法: `python siO2_disk_cooling/siO2_cooling_map.py`",
        "- 生成物: `siO2_disk_cooling/outputs/*.png`, `siO2_disk_cooling/outputs/*.csv`",
        "",
        "| T0 [K] | T_p \\le T_{glass} 到達範囲 | 代表時刻 | T_p \\le T_{liquidus} 到達範囲 | 代表時刻 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in summaries:
        lines.append(
            f"| {int(item['t0'])} | {item['glass_range']} | {item['glass_representative']} | {item['liquidus_range']} | {item['liquidus_representative']} |"
        )

    body = "\n".join(lines)
    upsert_marked_block(
        root_path,
        "@-- BEGIN:SIO2_DISK_COOLING_README --",
        "@-- END:SIO2_DISK_COOLING_README --",
        body,
    )


def update_root_agents(root_path: Path) -> None:
    """Insert the execution note into AGENTS.md."""

    body = "\n".join(
        [
            "## SiO₂ Disk Cooling シミュレーション（自動生成）",
            "- 目的：火星放射冷却に基づく SiO₂ 凝固優勢の距離×時間マップの作成",
            "- 実行: `python siO2_disk_cooling/siO2_cooling_map.py`",
            "- 出力: `siO2_disk_cooling/outputs/` 配下の PNG/CSV",
        ]
    )
    upsert_marked_block(
        root_path,
        "@-- BEGIN:SIO2_DISK_COOLING_AGENTS --",
        "@-- END:SIO2_DISK_COOLING_AGENTS --",
        body,
    )


def update_analysis_document(analysis_path: Path, summaries: List[Dict[str, object]]) -> None:
    """Append the simulation summary inside the analysis overview."""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"## SiO₂ 凝固優勢（距離×時間マップ）サマリ（{timestamp}）",
    ]
    for item in summaries:
        lines.append(
            (
                f"- T0={int(item['t0'])}K: r範囲={item['glass_range']} (glass), "
                f"代表到達={item['glass_representative']}; 液相到達範囲={item['liquidus_range']}, "
                f"代表到達={item['liquidus_representative']}"
            )
        )
    lines.append("出力: siO2_disk_cooling/outputs/ 以下を参照")

    body = "\n".join(lines)
    upsert_marked_block(
        analysis_path,
        "@-- BEGIN:SIO2_DISK_COOLING_ANALYSIS --",
        "@-- END:SIO2_DISK_COOLING_ANALYSIS --",
        body,
    )


# ---------------------------------------------------------------------------
# メインルーチン
# ---------------------------------------------------------------------------
def main() -> None:
    """Run the SiO₂ cooling simulation and update documentation."""

    sim_dir = Path(__file__).resolve().parent
    project_dir = sim_dir.parent
    # detect repo root (prefer local project dir when analysis/ exists)
    repo_root = project_dir
    if not (repo_root / "analysis").exists():
        repo_root = project_dir.parent
    outputs_dir = sim_dir / "outputs"
    logs_dir = sim_dir / "logs"

    ensure_directory(outputs_dir)
    ensure_directory(logs_dir)

    # 時間・距離グリッド
    time_s: List[float] = []
    current = 0.0
    end_time = YEARS * YEAR_SECONDS
    while current < end_time - 1e-6:
        time_s.append(current)
        current += DT_SECONDS
    time_s.append(end_time)

    if N_R == 1:
        radii_ratios = [R_RATIO_MIN]
    else:
        step = (R_RATIO_MAX - R_RATIO_MIN) / (N_R - 1)
        radii_ratios = [R_RATIO_MIN + i * step for i in range(N_R)]
    radii_m = [ratio * R_MARS for ratio in radii_ratios]

    # 基準: 高温ほど到達が早いか確認するための格納
    benchmark_times: Dict[float, Dict[str, float]] = {}

    summaries: List[Dict[str, object]] = []

    for t0 in T0_LIST:
        summary = run_case(t0, radii_m, time_s, radii_ratios, outputs_dir)
        summaries.append(summary)

        representative_r = [1.5, 2.0, 2.4]
        benchmark_times[t0] = {}
        for r_ratio in representative_r:
            radius_m = r_ratio * R_MARS
            time_s_cross = first_crossing_time(radius_m, t0, T_GLASS, time_s)
            benchmark_times[t0][f"r={r_ratio:.1f}"] = (
                math.nan if math.isnan(time_s_cross) else time_s_cross / YEAR_SECONDS
            )

        print("=" * 60)
        print(f"初期温度 T0={int(t0)} K の結果")
        print(f"ガラス転移到達範囲: {summary['glass_range']}")
        print(f"代表時刻: {summary['glass_representative']}")
        print(f"液相終端到達範囲: {summary['liquidus_range']}")
        print(f"代表時刻: {summary['liquidus_representative']}")
        print(f"CSV: {summary['csv'].relative_to(repo_root)}")
        print(f"PNG: {summary['png'].relative_to(repo_root)}")

    # 高温ケースほど早いことの簡易チェック
    radii_keys = ["r=1.5", "r=2.0", "r=2.4"]
    for key in radii_keys:
        times = [benchmark_times[t0][key] for t0 in T0_LIST]
        if not all(math.isnan(t) for t in times):
            previous_time = None
            monotonic = True
            for time_val in times:
                if math.isnan(time_val):
                    continue
                if previous_time is not None and time_val < previous_time - 1e-6:
                    monotonic = False
                    break
                previous_time = time_val
            if not monotonic:
                print(f"代表半径 {key} における到達順: {times} (高温優位性に逸脱あり)")
                continue
        print(f"代表半径 {key} におけるガラス転移到達時刻 (年): {times}")

    # ドキュメント更新
    update_root_readme(repo_root / "README.md", summaries)
    update_root_agents(repo_root / "AGENTS.md")
    update_analysis_document(repo_root / "analysis" / "overview.md", summaries)
    create_simulation_readme(sim_dir / "README.md")

    # ログ出力
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"run_{timestamp}.txt"
    lines = ["SiO₂ Disk Cooling 実行ログ", f"UTC: {timestamp}"]
    for summary in summaries:
        lines.append("")
        lines.append(f"T0={int(summary['t0'])} K")
        lines.append(f"  ガラス転移: {summary['glass_range']} ({summary['glass_representative']})")
        lines.append(f"  液相終端: {summary['liquidus_range']} ({summary['liquidus_representative']})")
        lines.append(f"  CSV: {summary['csv']}")
        lines.append(f"  PNG: {summary['png']}")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
