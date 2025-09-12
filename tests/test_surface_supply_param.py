import pandas as pd
import pytest

from marsdisk.physics import supply
from marsdisk.schema import (
    Supply,
    SupplyConst,
    SupplyPowerLaw,
    SupplyTable,
    SupplyMixing,
)


def test_const_mode():
    cfg = Supply(
        mode="const",
        const=SupplyConst(prod_area_rate_kg_m2_s=5.0),
        mixing=SupplyMixing(epsilon_mix=0.5),
    )
    rate = supply.get_prod_area_rate(0.0, 1.0, cfg)
    assert rate == 2.5


def test_powerlaw_mode():
    cfg = Supply(
        mode="powerlaw",
        powerlaw=SupplyPowerLaw(A_kg_m2_s=2.0, t0_s=1.0, index=-1.0),
    )
    rate = supply.get_prod_area_rate(2.0, 1.0, cfg)
    assert rate == pytest.approx(2.0 * ((2.0 - 1.0) + 1.0e-12) ** -1.0)


def test_table_mode(tmp_path):
    path = tmp_path / "rate.csv"
    pd.DataFrame({"t": [0.0, 10.0], "rate": [1.0, 3.0]}).to_csv(path, index=False)
    cfg = Supply(mode="table", table=SupplyTable(path=path))
    rate = supply.get_prod_area_rate(5.0, 1.0, cfg)
    assert rate == pytest.approx(2.0)
