# Forsterite material data bundle (simulation-ready)

This bundle contains machine-readable material-property data for forsterite (Mg2SiO4) as currently assembled:
- Optical constants n,k: FOR2285 (Jena) dataset for crystalline forsterite, axes a/b/c, temperatures 50–295 K, wavelength 0.08–1000 µm.
- Vapor pressure / HKL parameters:
  - Solid: van Lieshout et al. (2014) Eq. (13) with A,B for crystalline forsterite; HKL mass-flux form Eq. (12).
  - Liquid: Fegley & Schaefer (2012) Eq. (5) for molten forsterite total vapor pressure (bar).

## Files
- `forsterite_material_properties.json`
  - Main structured parameters (including converted coefficients for log10 P(Pa) form).
- `FOR2285_forsterite_nk_manifest.json`
  - List of all FOR2285 n,k files included (axis, temperature, wavelength range, columns).
- `FOR2285_forsterite_nk_long.csv`
  - Stacked table: `temperature_K, axis, wavelength_um, n, k` (38,448 rows).
- `nk_FOR2285/`
  - Original ASCII `.dat` files and CSV copies for each axis/temperature.
- `candidates.csv`
  - Metadata for temperature-dependent n,k candidates beyond FOR2285 (source, temperature, wavelength range, availability).
- `nk_data.csv`
  - Aggregated n,k rows for high-temperature candidates (see `candidates.csv` for source metadata).
- `directional-database/aerosol_directional_database.hdf5`
  - POSEIDON directional database (HDF5). Contains Mg2SiO4_* groups with effective cross sections (eff_*); no n,k tables.
- `poseidon_mg2sio4_index.csv`
  - Index of Mg2SiO4_* groups in the POSEIDON HDF5 (temperature/axis/dataset list and grid sizes).

## Notes / caveats
- The base of the `log` in Fegley & Schaefer (2012) Eq. (5) is not explicitly stated in the extracted text; the JSON preserves this as `log_base=UNKNOWN` and provides a converted form assuming log10.
- Solid vapor pressure parameters are valid only over the temperature range listed in van Lieshout et al. Table 3; outside-range use is extrapolation.
- High-temperature n,k candidates include non-forsterite proxies (e.g., low-Fe olivine) and amorphous Mg2SiO4; they are **not integrated** into the Phase 1 Q_pr table.
- Pure forsterite high-temperature n,k (Eckes 2013, POSEIDON optional) is listed in `candidates.csv` but the raw files are not included in this bundle.
