# Documentation Coverage

- Function reference rate: 43.3% (26/60)

## Module Coverage

- `marsdisk/constants.py`: 100.0% (0/0)
- `marsdisk/errors.py`: 100.0% (0/0)
- `marsdisk/grid.py`: 100.0% (4/4)
- `marsdisk/io/tables.py`: 75.0% (3/4)
- `marsdisk/io/writer.py`: 25.0% (1/4)
- `marsdisk/physics/collide.py`: 0.0% (0/2)
- `marsdisk/physics/dynamics.py`: 0.0% (0/3)
- `marsdisk/physics/fragments.py`: 25.0% (1/4)
- `marsdisk/physics/initfields.py`: 0.0% (0/2)
- `marsdisk/physics/psd.py`: 66.7% (2/3)
- `marsdisk/physics/qstar.py`: 0.0% (0/1)
- `marsdisk/physics/radiation.py`: 20.0% (1/5)
- `marsdisk/physics/shielding.py`: 20.0% (1/5)
- `marsdisk/physics/sinks.py`: 50.0% (1/2)
- `marsdisk/physics/sizes.py`: 100.0% (1/1)
- `marsdisk/physics/smol.py`: 50.0% (1/2)
- `marsdisk/physics/sublimation.py`: 57.1% (4/7)
- `marsdisk/physics/supply.py`: 0.0% (0/1)
- `marsdisk/physics/surface.py`: 50.0% (2/4)
- `marsdisk/physics/viscosity.py`: 100.0% (1/1)
- `marsdisk/run.py`: 60.0% (3/5)
- `marsdisk/schema.py`: 100.0% (0/0)

## Top Coverage Gaps

- `marsdisk/io/tables.py`:287 `load_phi_table` (lines 287–342)
- `marsdisk/io/writer.py`:109 `write_summary` (lines 109–117)
- `marsdisk/io/writer.py`:120 `write_run_config` (lines 120–125)
- `marsdisk/io/writer.py`:128 `write_mass_budget` (lines 128–132)
- `marsdisk/physics/collide.py`:18 `compute_collision_kernel_C1` (lines 18–77)
- `marsdisk/physics/collide.py`:80 `compute_prod_subblow_area_rate_C2` (lines 80–108)
- `marsdisk/physics/dynamics.py`:18 `v_ij` (lines 18–45)
- `marsdisk/physics/dynamics.py`:48 `solve_c_eq` (lines 48–106)
- `marsdisk/physics/dynamics.py`:109 `update_e` (lines 109–140)
- `marsdisk/physics/fragments.py`:31 `compute_q_r_F2` (lines 31–62)