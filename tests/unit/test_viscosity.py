import numpy as np

from marsdisk.grid import RadialGrid
from marsdisk.physics.viscosity import step_viscous_diffusion_C5


def _run(N: int, dt: float):
    grid = RadialGrid.linear(1.0, 2.0, N)
    r = grid.r
    sigma0 = np.exp(-((r - 1.5) ** 2) / 0.01)
    nu = np.ones_like(r)
    sigma1 = step_viscous_diffusion_C5(sigma0, nu, grid, dt)
    mass0 = float(np.sum(sigma0 * grid.areas))
    mass1 = float(np.sum(sigma1 * grid.areas))
    return sigma1, grid, (mass1 - mass0) / mass0


def test_viscous_diffusion_converges_and_conserves_mass():
    dt = 1.0e-4
    sigma_ref, grid_ref, _ = _run(400, dt)

    results = []
    for N in (50, 100):
        sigma, grid, mass_err = _run(N, dt)
        interp = np.interp(grid.r, grid_ref.r, sigma_ref)
        err = np.mean(np.abs(sigma - interp))
        results.append((err, mass_err))

    # Convergence with resolution
    assert results[1][0] < results[0][0]
    # Mass conservation within tight tolerance
    for _, mass_err in results:
        assert abs(mass_err) < 1e-10
