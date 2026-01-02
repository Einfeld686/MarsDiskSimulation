import pytest

from marsdisk import schema


def test_inner_disk_mass_alias_warns() -> None:
    with pytest.warns(DeprecationWarning, match="M_over_Mmars"):
        mass = schema.InnerDiskMass(M_over_Mmars=1.0e-5)
    assert mass.M_in_ratio == 1.0e-5


def test_supply_reservoir_smooth_fraction_warns() -> None:
    with pytest.warns(DeprecationWarning, match="smooth_fraction"):
        reservoir = schema.SupplyReservoir.model_validate({"smooth_fraction": 0.2})
    assert reservoir.taper_fraction == 0.2


def test_supply_reservoir_smooth_mode_warns() -> None:
    with pytest.warns(DeprecationWarning, match="depletion_mode.*smooth"):
        reservoir = schema.SupplyReservoir.model_validate({"depletion_mode": "smooth"})
    assert reservoir.depletion_mode == "taper"


def test_supply_transport_alias_warns() -> None:
    payload = {
        "transport": {"mode": "deep_mixing"},
        "injection": {"deep_reservoir_tmix_orbits": 5.0},
    }
    with pytest.warns(DeprecationWarning, match="deep_reservoir_tmix_orbits"):
        supply = schema.Supply.model_validate(payload)
    assert supply.transport.t_mix_orbits == 5.0


def test_shielding_table_mode_warns() -> None:
    with pytest.warns(DeprecationWarning, match="shielding.mode"):
        shielding = schema.Shielding(mode="table")
    assert shielding.mode_resolved == "psitau"


def test_io_columnar_records_warns() -> None:
    with pytest.warns(DeprecationWarning, match="columnar_records"):
        io_cfg = schema.IO(columnar_records=True)
    assert io_cfg.record_storage_mode == "columnar"
