from __future__ import annotations

import numpy as np
import pytest

from marsdisk.physics import collisions_smol


def test_powerlaw_injection_matches_number_slope() -> None:
    s_min = 1.0e-6
    s_max = 1.0e-4
    n_bins = 12
    edges = np.geomspace(s_min, s_max, n_bins + 1)
    sizes = np.sqrt(edges[:-1] * edges[1:])
    widths = edges[1:] - edges[:-1]
    rho = 3000.0
    m_bin = (4.0 / 3.0) * np.pi * rho * sizes**3

    prod_rate = 1.0e-9
    q = 3.5

    source = collisions_smol.supply_mass_rate_to_number_source(
        prod_rate,
        sizes,
        m_bin,
        s_min_eff=s_min,
        widths=widths,
        mode="powerlaw_bins",
        s_inj_min=s_min,
        s_inj_max=s_max,
        q=q,
    )

    assert np.isclose(np.sum(source * m_bin), prod_rate)
    dnds = np.where(widths > 0.0, source / widths, 0.0)
    mask = dnds > 0.0
    assert mask.sum() >= 3
    slope, _ = np.polyfit(np.log(sizes[mask]), np.log(dnds[mask]), 1)
    assert slope == pytest.approx(-q, abs=0.1)
