from __future__ import annotations

"""Initial field mappings for surface density.

This module converts a total inner-disk mass into a radial surface density
profile and applies the configured initial surface policy to obtain the
starting surface-layer density.
"""

from typing import Callable, Optional
import math


_DEF_EPS = 1.0e-12


def sigma_from_Minner(
    M_in: float,
    r_in: float,
    r_out: float,
    p_index: float,
) -> Callable[[float], float]:
    """Return ``Σ(r)`` for an inner disk of total mass ``M_in``.

    The surface density is assumed either uniform or to follow a power-law
    ``Σ = C r^{-p}``.  The normalisation ``C`` is chosen such that
    ``\int_{r_in}^{r_out} 2π r Σ(r) dr = M_in``.
    """

    if r_out <= r_in:
        raise ValueError("r_out must be greater than r_in")

    if abs(p_index) < _DEF_EPS:
        sigma_const = M_in / (math.pi * (r_out**2 - r_in**2))
        return lambda r: float(sigma_const)

    if abs(p_index - 2.0) < _DEF_EPS:
        C = M_in / (2.0 * math.pi * math.log(r_out / r_in))
    else:
        C = (
            M_in * (2.0 - p_index)
            / (2.0 * math.pi * (r_out ** (2.0 - p_index) - r_in ** (2.0 - p_index)))
        )
    return lambda r: float(C * r ** (-p_index))


def surf_sigma_init(
    sigma: float,
    kappa_eff: Optional[float],
    policy: str,
    f_surf: float | None = None,
    sigma_override: float | None = None,
) -> float:
    """Map mid-plane ``Σ`` to the initial surface density ``Σ_surf``.

    Parameters
    ----------
    sigma:
        Mid-plane surface density at the evaluation radius.
    kappa_eff:
        Effective opacity used to compute ``Σ_{τ=1} = 1/κ``.
    policy:
        Initialisation policy.  When set to ``"clip_by_tau1"`` the surface
        layer is clipped to the optical-depth unity limit.
    f_surf:
        Optional scaling factor applied to the mid-plane density before
        clipping.
    sigma_override:
        Explicit surface density that bypasses the policy logic when provided.
    """

    if sigma_override is not None:
        return sigma_override

    sigma_local = sigma * (f_surf if f_surf is not None else 1.0)

    if policy == "clip_by_tau1" and kappa_eff is not None and kappa_eff > 0.0:
        return float(min(sigma_local, 1.0 / kappa_eff))
    return float(sigma_local)


__all__ = ["sigma_from_Minner", "surf_sigma_init"]
