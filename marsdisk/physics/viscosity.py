from __future__ import annotations

"""Radial viscous diffusion step (C5)."""

import logging
from typing import Iterable

import numpy as np

from ..errors import MarsDiskError
from ..grid import RadialGrid

__all__ = ["step_viscous_diffusion_C5"]

logger = logging.getLogger(__name__)


def _solve_tridiagonal(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Solve a tridiagonal system using the Thomas algorithm.

    The system has lower diagonal ``a`` (length ``n-1``), main diagonal ``b``
    (length ``n``) and upper diagonal ``c`` (length ``n-1``).  ``d`` is the
    right-hand side of length ``n``.

    Args:
        a: Sub-diagonal coefficients.
        b: Main diagonal coefficients.
        c: Super-diagonal coefficients.
        d: Right-hand side vector.

    Returns:
        Solution vector ``x``.
    """

    n = b.size
    ac = a.copy()
    bc = b.copy()
    cc = c.copy()
    dc = d.copy()
    for i in range(1, n):
        w = ac[i - 1] / bc[i - 1]
        bc[i] -= w * cc[i - 1]
        dc[i] -= w * dc[i - 1]
    x = np.empty(n, dtype=float)
    x[-1] = dc[-1] / bc[-1]
    for i in range(n - 2, -1, -1):
        x[i] = (dc[i] - cc[i] * x[i + 1]) / bc[i]
    return x


def step_viscous_diffusion_C5(
    sigma: Iterable[float],
    nu: Iterable[float],
    grid: RadialGrid,
    dt: float,
    *,
    theta: float = 0.5,
) -> np.ndarray:
    """Advance ``sigma`` by radial viscous diffusion. [@CridaCharnoz2012_Science338_1196]

    A theta-method with ``theta=0.5`` corresponds to the Crank–Nicolson
    scheme.  Zero-flux (Neumann) boundary conditions are imposed at the inner
    and outer edges of ``grid``.

    Args:
        sigma: Surface density at cell centres.
        nu: Kinematic viscosity at cell centres.
        grid: Radial grid describing the cell geometry.
        dt: Time step.
        theta: Implicitness parameter, ``0`` ≤ ``theta`` ≤ ``1``.

    Returns:
        Updated surface density array.

    Raises:
        MarsDiskError: If input shapes are inconsistent or parameters invalid.
    """

    sigma_arr = np.asarray(sigma, dtype=float)
    nu_arr = np.asarray(nu, dtype=float)
    if sigma_arr.ndim != 1 or nu_arr.ndim != 1:
        raise MarsDiskError("sigma and nu must be one-dimensional")
    if sigma_arr.size != nu_arr.size:
        raise MarsDiskError("sigma and nu must have the same length")
    if dt <= 0.0:
        raise MarsDiskError("dt must be positive")
    if not 0.0 <= theta <= 1.0:
        raise MarsDiskError("theta must lie in [0, 1]")

    r = grid.r
    edges = grid.edges
    if r.size != sigma_arr.size:
        raise MarsDiskError("grid and sigma size mismatch")

    dr_cell = np.diff(edges)  # Δr for each cell
    dr_plus = np.diff(r)      # r_{i+1} - r_i
    r_edge = edges[1:-1]      # r_{i+1/2} for internal edges
    nu_edge = 0.5 * (nu_arr[:-1] + nu_arr[1:])

    n = sigma_arr.size
    A = np.zeros(n)
    B = np.zeros(n)
    C = np.zeros(n)

    # Interior cells
    for i in range(1, n - 1):
        coeff_left = r_edge[i - 1] * nu_edge[i - 1] / (r[i] * dr_cell[i] * dr_plus[i - 1])
        coeff_right = r_edge[i] * nu_edge[i] / (r[i] * dr_cell[i] * dr_plus[i])
        A[i] = coeff_left
        C[i] = coeff_right
        B[i] = -(coeff_left + coeff_right)

    # Inner boundary (zero flux)
    coeff_right = r_edge[0] * nu_edge[0] / (r[0] * dr_cell[0] * dr_plus[0])
    C[0] = coeff_right
    B[0] = -coeff_right

    # Outer boundary (zero flux)
    coeff_left = r_edge[-1] * nu_edge[-1] / (r[-1] * dr_cell[-1] * dr_plus[-1])
    A[-1] = coeff_left
    B[-1] = -coeff_left

    # Left-hand side matrix diagonals for (I - θΔt L)
    lower = -theta * dt * A[1:]
    diag = 1.0 - theta * dt * B
    upper = -theta * dt * C[:-1]

    # Right-hand side vector (I + (1-θ)Δt L) σ^n
    L_sigma = A * np.concatenate(([0.0], sigma_arr[:-1])) + B * sigma_arr + C * np.concatenate((sigma_arr[1:], [0.0]))
    rhs = sigma_arr + (1.0 - theta) * dt * L_sigma

    sigma_new = _solve_tridiagonal(lower, diag, upper, rhs)
    logger.info("step_viscous_diffusion_C5: dt=%e theta=%f", dt, theta)
    return sigma_new
