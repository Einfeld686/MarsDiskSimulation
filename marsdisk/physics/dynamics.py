"""Self-regulated velocity dispersion utilities (D1--D2).

This module implements helper functions to evaluate the relative speed
between particles and to solve for the equilibrium velocity dispersion of
ring particles by balancing shear heating and collisional cooling.
"""
from __future__ import annotations

from typing import Callable
import logging
import numpy as np

from ..errors import MarsDiskError

logger = logging.getLogger(__name__)


def v_ij(e: float, i: float, v_k: float = 1.0) -> float:
    """Return the mutual relative velocity ``v_ij``.

    The expression follows the low-eccentricity, low-inclination
    approximation of Ohtsuki et al. and reads
    ``v_ij = v_K sqrt(1.25 e^2 + i^2)``.  The function is written in a
    manner that can be JIT-compiled by :mod:`numba` for performance critical
    applications.

    Parameters
    ----------
    e:
        Relative eccentricity.
    i:
        Relative inclination.
    v_k:
        Local Keplerian speed.  Defaults to unity for dimensionless use.

    Returns
    -------
    float
        Relative speed ``v_ij``.
    """
    if v_k < 0.0:
        raise MarsDiskError("v_k must be non-negative")
    v_rel = np.sqrt(1.25 * e * e + i * i) * v_k
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("v_ij: e=%f i=%f v_k=%f -> v_rel=%f", e, i, v_k, v_rel)
    return float(v_rel)


def v_rel_pericenter(e: float, v_k: float) -> float:
    """Return periapsis Kepler speed ``v_K(a)/sqrt(1-e)`` for encounters near periapsis."""

    if v_k < 0.0:
        raise MarsDiskError("v_k must be non-negative")
    if e >= 1.0:
        raise MarsDiskError("eccentricity must be < 1 for pericenter velocity")
    v_rel = v_k / max((1.0 - e) ** 0.5, 1.0e-8)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("v_rel_pericenter: e=%f v_k=%f -> v_rel=%f", e, v_k, v_rel)
    return float(v_rel)


def solve_c_eq(
    tau: float,
    e: float,
    eps_model: Callable[[float], float],
    *,
    f_wake: float = 1.0,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> float:
    """Return the equilibrium velocity dispersion ``c_eq``.

    The solution is obtained via fixed-point iteration of the balance between
    shear heating and inelastic collisional cooling.  The coefficient of
    restitution is provided by ``eps_model`` and may depend on the current
    value of ``c``.

    Parameters
    ----------
    tau:
        Normal optical depth of the ring.
    e:
        Initial guess based on the eccentricity.
    eps_model:
        Callable returning the restitution coefficient ``ε`` for a given
        impact speed.
    f_wake:
        Multiplicative enhancement factor to mimic self-gravity wakes.
    max_iter:
        Maximum number of iterations.
    tol:
        Relative convergence tolerance.

    Returns
    -------
    float
        Equilibrium velocity dispersion ``c_eq``.

    Raises
    ------
    MarsDiskError
        If the iteration fails to converge or invalid parameters are
        supplied.
    """
    if tau < 0.0:
        raise MarsDiskError("tau must be non-negative")
    if f_wake < 1.0:
        raise MarsDiskError("f_wake must be >= 1")

    c = max(e, 1e-6)
    for n in range(max_iter):
        eps = float(eps_model(c))
        eps = min(max(eps, 0.0), 1.0 - 1e-6)
        c_new = (f_wake * tau / max(1.0 - eps**2, 1e-12)) ** 0.5
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("solve_c_eq iter=%d c=%.6e eps=%.3f c_new=%.6e", n, c, eps, c_new)
        if abs(c_new - c) <= tol * max(c_new, 1.0):
            return float(c_new)
        c = 0.5 * (c + c_new)

    raise MarsDiskError("solve_c_eq failed to converge")


def update_e(e: float, e_eq: float, t_damp: float, dt: float) -> float:
    """Relax ``e`` towards ``e_eq`` over the damping time scale.

    Parameters
    ----------
    e:
        Current eccentricity.
    e_eq:
        Target equilibrium eccentricity.
    t_damp:
        Damping time scale (must be positive).
    dt:
        Integration time step.

    Returns
    -------
    float
        Updated eccentricity after one time step.
    """
    if t_damp <= 0.0:
        raise MarsDiskError("t_damp must be positive")
    fac = np.exp(-dt / t_damp)
    new_e = float(e_eq + (e - e_eq) * fac)
    logger.info(
        "update_e: e=%f e_eq=%f dt=%f t_damp=%f -> e_new=%f",
        e,
        e_eq,
        dt,
        t_damp,
        new_e,
    )
    return new_e


__all__ = ["v_ij", "v_rel_pericenter", "solve_c_eq", "update_e"]
