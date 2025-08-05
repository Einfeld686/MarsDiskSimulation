"""Timescale utility functions.

秒と年の変換および t_col, t_PR のラッパーを提供する。
"""

from static_map import SECONDS_PER_YEAR, t_collision, t_PR, t_PR_mars


def convert_sec_to_year(x):
    """秒を年に換算する."""
    return x / SECONDS_PER_YEAR


def collision_timescale(s, Sigma, rho, r_disk):
    """衝突時スケールを年で返す."""
    return convert_sec_to_year(t_collision(s, Sigma, rho, r_disk))


def pr_timescale_total(s, rho, beta_sun_val, include_mars, T_mars, qpr, r_disk):
    """太陽および火星起源 P-R ドラッグの合成時スケール [yr]."""
    t_sun = t_PR(s, rho, beta_sun_val)
    if include_mars:
        t_mars = t_PR_mars(s, rho, T_mars, qpr, r_disk)
        return 1.0 / (1.0 / t_sun + 1.0 / t_mars)
    return t_sun
