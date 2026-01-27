<!--
document_type: reference
title: 主要物理過程のコード
-->

<!--
実装(.py): marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/collide.py, marsdisk/physics/smol.py, marsdisk/physics/surface.py
-->

## 付録 B. 主要物理過程のコード

本文で用いた主要物理過程の実装を，代表的な関数単位で掲載する．可読性のため，import 文や周辺の補助関数は省略し，該当部分のみを抜粋して示す．

### B.1 放射圧とブローアウト（R2–R3）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/radiation.py

def beta(
    s: float,
    rho: Optional[float],
    T_M: Optional[float],
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Compute the ratio ``β`` of radiation pressure to gravity (R2). [@StrubbeChiang2006_ApJ648_652]

    The expression follows directly from conservation of momentum using the
    luminosity of Mars ``L_M = 4π R_M^2 σ T_M^4`` and reads

    ``β = 3 L_M ⟨Q_pr⟩ / (16 π c G M_M ρ s)``.
    """
    s_val = _validate_size(s)
    rho_val = _validate_density(rho)
    T_val = _validate_temperature(T_M)
    qpr = _resolve_qpr(s_val, T_val, Q_pr, table, interp)
    numerator = 3.0 * constants.SIGMA_SB * (T_val**4) * (constants.R_MARS**2) * qpr
    denominator = 4.0 * constants.G * constants.M_MARS * constants.C * rho_val * s_val
    return float(numerator / denominator)


def blowout_radius(
    rho: Optional[float],
    T_M: Optional[float],
    Q_pr: Optional[float] = None,
    table: type_QPr | None = None,
    interp: type_QPr | None = None,
) -> float:
    """Return the blow-out grain size ``s_blow`` for ``β = 0.5`` (R3). [@StrubbeChiang2006_ApJ648_652]"""

    global _NUMBA_FAILED
    rho_val = _validate_density(rho)
    T_val = _validate_temperature(T_M)
    if Q_pr is not None:
        qpr = _resolve_qpr(1.0, T_val, Q_pr, table, interp)
        if _USE_NUMBA_RADIATION and not _NUMBA_FAILED:
            try:
                return float(blowout_radius_numba(rho_val, T_val, qpr))
            except Exception as exc:
                _NUMBA_FAILED = True
                warnings.warn(
                    f"blowout radius numba kernel failed ({exc!r}); falling back to NumPy.",
                    NumericalWarning,
                )
        numerator = 3.0 * constants.SIGMA_SB * (T_val**4) * (constants.R_MARS**2) * qpr
        denominator = 2.0 * constants.G * constants.M_MARS * constants.C * rho_val
        return float(numerator / denominator)

    coef = (
        3.0
        * constants.SIGMA_SB
        * (T_val**4)
        * (constants.R_MARS**2)
        / (2.0 * constants.G * constants.M_MARS * constants.C * rho_val)
    )
    s_val = coef * _resolve_qpr(1.0, T_val, None, table, interp)
    for _ in range(8):
        qpr_val = _resolve_qpr(s_val, T_val, None, table, interp)
        s_new = coef * qpr_val
        if not np.isfinite(s_new) or s_new <= 0.0:
            break
        if abs(s_new - s_val) <= 1.0e-6 * max(s_new, 1.0e-30):
            s_val = s_new
            break
        s_val = s_new
    return float(s_val)
\end{Verbatim}

### B.2 自遮蔽と光学的厚さ（S0）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/shielding.py

def sigma_tau1(kappa_eff: float) -> float:
    """Return Σ_{τ=1} derived from κ_eff. Self-shielding Φ."""

    if not isinstance(kappa_eff, Real):
        raise TypeError("effective opacity 'kappa_eff' must be a real number for Σ_{τ=1}")
    if not np.isfinite(kappa_eff) or kappa_eff <= 0.0:
        return float(np.inf)
    return float(1.0 / float(kappa_eff))


def apply_shielding(
    kappa_surf: float,
    tau: float,
    w0: float,
    g: float,
    interp: type_Phi | None = None,
) -> Tuple[float, float]:
    """Return effective opacity and ``Σ_{τ=1}`` for given conditions. Self-shielding Φ."""

    if not isinstance(kappa_surf, Real):
        raise TypeError("surface opacity 'kappa_surf' must be a real number for Φ lookup")
    if not np.isfinite(kappa_surf):
        raise PhysicsError("surface opacity 'kappa_surf' must be finite for Φ lookup")
    if kappa_surf < 0.0:
        raise PhysicsError("surface opacity 'kappa_surf' must be greater or equal to 0 for Φ lookup")
    if not isinstance(tau, Real):
        raise TypeError("optical depth 'tau' must be a real number for Φ lookup")
    if not np.isfinite(tau):
        raise PhysicsError("optical depth 'tau' must be finite for Φ lookup")
    if not isinstance(w0, Real):
        raise TypeError("single-scattering albedo 'w0' must be a real number for Φ lookup")
    if not np.isfinite(w0):
        raise PhysicsError("single-scattering albedo 'w0' must be finite for Φ lookup")
    if not isinstance(g, Real):
        raise TypeError("asymmetry parameter 'g' must be a real number for Φ lookup")
    if not np.isfinite(g):
        raise PhysicsError("asymmetry parameter 'g' must be finite for Φ lookup")
    if interp is not None and not callable(interp):
        raise TypeError("Φ interpolator 'interp' must be callable")

    func = tables.interp_phi if interp is None else interp
    if not callable(func):
        raise TypeError("Φ interpolator must be callable")

    tau_val = float(tau)
    w0_val = float(w0)
    g_val = float(g)

    phi_table = _infer_phi_table(func)
    clamp_msgs: list[str] = []
    tau_min = tau_max = None
    if phi_table is not None:
        tau_vals = np.asarray(getattr(phi_table, "tau_vals"), dtype=float)
        w0_vals = np.asarray(getattr(phi_table, "w0_vals"), dtype=float)
        g_vals = np.asarray(getattr(phi_table, "g_vals"), dtype=float)
        if tau_vals.size:
            tau_min = float(np.min(tau_vals))
            tau_max = float(np.max(tau_vals))
            if tau_val < tau_min or tau_val > tau_max:
                clamped = float(np.clip(tau_val, tau_min, tau_max))
                clamp_msgs.append(
                    f"tau={tau_val:.6e}->{clamped:.6e} (range {tau_min:.6e}–{tau_max:.6e})"
                )
                tau_val = clamped
        if w0_vals.size:
            w0_min = float(np.min(w0_vals))
            w0_max = float(np.max(w0_vals))
            if w0_val < w0_min or w0_val > w0_max:
                clamped = float(np.clip(w0_val, w0_min, w0_max))
                clamp_msgs.append(
                    f"w0={w0_val:.6e}->{clamped:.6e} (range {w0_min:.6e}–{w0_max:.6e})"
                )
                w0_val = clamped
        if g_vals.size:
            g_min = float(np.min(g_vals))
            g_max = float(np.max(g_vals))
            if g_val < g_min or g_val > g_max:
                clamped = float(np.clip(g_val, g_min, g_max))
                clamp_msgs.append(
                    f"g={g_val:.6e}->{clamped:.6e} (range {g_min:.6e}–{g_max:.6e})"
                )
                g_val = clamped
    if clamp_msgs:
        logger.info("Φ lookup clamped: %s", ", ".join(clamp_msgs))

    def phi_wrapper(val_tau: float) -> float:
        tau_arg = float(val_tau)
        if phi_table is not None and tau_min is not None and tau_max is not None:
            tau_arg = float(np.clip(tau_arg, tau_min, tau_max))
        return float(func(tau_arg, w0_val, g_val))

    kappa_eff = effective_kappa(float(kappa_surf), tau_val, phi_wrapper)
    sigma_tau1_limit = sigma_tau1(kappa_eff)
    return kappa_eff, sigma_tau1_limit


def clip_to_tau1(sigma_surf: float, kappa_eff: float) -> float:
    """Clip ``Σ_surf`` so that it does not exceed ``Σ_{τ=1}``. Self-shielding Φ."""

    if not isinstance(sigma_surf, Real):
        raise TypeError("surface density 'sigma_surf' must be a real number for τ=1 clipping")
    if not np.isfinite(sigma_surf):
        raise PhysicsError("surface density 'sigma_surf' must be finite for τ=1 clipping")
    if not isinstance(kappa_eff, Real):
        raise TypeError("effective opacity 'kappa_eff' must be a real number for τ=1 clipping")
    if not np.isfinite(kappa_eff):
        raise PhysicsError("effective opacity 'kappa_eff' must be finite for τ=1 clipping")

    sigma_val = float(sigma_surf)
    kappa_val = float(kappa_eff)

    if kappa_val <= 0.0:
        if sigma_val < 0.0:
            logger.info(
                "Clamped Σ_surf from %e to 0 due to non-positive κ_eff=%e",
                sigma_val,
                kappa_val,
            )
        return max(0.0, sigma_val)

    if sigma_val < 0.0:
        logger.info(
            "Clamped Σ_surf from %e to 0 with κ_eff=%e",
            sigma_val,
            kappa_val,
        )
        return 0.0

    sigma_tau1_limit = sigma_tau1(kappa_val)
    if sigma_val > sigma_tau1_limit:
        logger.info(
            "Clamped Σ_surf from %e to τ=1 limit %e with κ_eff=%e",
            sigma_val,
            sigma_tau1_limit,
            kappa_val,
        )
        return float(sigma_tau1_limit)

    return sigma_val
\end{Verbatim}

### B.3 衝突カーネルとサブブローアウト生成（C1–C2）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/collide.py

def compute_collision_kernel_C1(
    N: Iterable[float],
    s: Iterable[float],
    H: Iterable[float],
    v_rel: float | np.ndarray,
    workspace: CollisionKernelWorkspace | None = None,
    *,
    use_numba: bool | None = None,
) -> np.ndarray:
    """Return the symmetric collision kernel :math:`C_{ij}`.

    Parameters
    ----------
    N:
        Number surface densities for each size bin.
    s:
        Characteristic sizes of the bins in metres.
    H:
        Vertical scale height of each bin in metres.
    v_rel:
        Mutual relative velocity between bins.  A scalar applies the same
        velocity to all pairs while a matrix of shape ``(n, n)`` provides
        pair-specific values.
    workspace:
        Optional size-only precomputations from
        :func:`prepare_collision_kernel_workspace`. When provided, ``s_sum``
        and the identity matrix reuse these buffers across calls.

    Returns
    -------
    numpy.ndarray
        Collision kernel matrix with shape ``(n, n)``.
    """

    global _NUMBA_FAILED

    N_arr = np.asarray(N, dtype=np.float64)
    s_arr = np.asarray(s, dtype=np.float64)
    H_arr = np.asarray(H, dtype=np.float64)
    if N_arr.ndim != 1 or s_arr.ndim != 1 or H_arr.ndim != 1:
        raise MarsDiskError("inputs must be one-dimensional")
    if not (len(N_arr) == len(s_arr) == len(H_arr)):
        raise MarsDiskError("array lengths must match")
    if np.any(N_arr < 0.0) or np.any(s_arr <= 0.0) or np.any(H_arr <= 0.0):
        raise MarsDiskError("invalid values in N, s or H")

    n = N_arr.size
    if workspace is not None:
        if workspace.s_sum_sq.shape != (n, n) or workspace.delta.shape != (n, n):
            raise MarsDiskError("workspace has incompatible shape for collision kernel")
        workspace_s_sum_sq = workspace.s_sum_sq
        workspace_delta = workspace.delta
        if workspace.v_mat_full is None or workspace.v_mat_full.shape != (n, n):
            workspace.v_mat_full = np.zeros((n, n), dtype=np.float64)
        if workspace.N_outer is None or workspace.N_outer.shape != (n, n):
            workspace.N_outer = np.zeros((n, n), dtype=np.float64)
        if workspace.H_sq is None or workspace.H_sq.shape != (n, n):
            workspace.H_sq = np.zeros((n, n), dtype=np.float64)
        if workspace.H_ij is None or workspace.H_ij.shape != (n, n):
            workspace.H_ij = np.zeros((n, n), dtype=np.float64)
        if workspace.kernel is None or workspace.kernel.shape != (n, n):
            workspace.kernel = np.zeros((n, n), dtype=np.float64)
    else:
        workspace_s_sum_sq = None
        workspace_delta = None
    use_matrix_velocity = False
    if np.isscalar(v_rel):
        v_scalar = float(v_rel)
        if not np.isfinite(v_scalar) or v_scalar < 0.0:
            raise MarsDiskError("v_rel must be finite and non-negative")
        v_mat = np.zeros((n, n), dtype=np.float64)
    else:
        v_mat = np.asarray(v_rel, dtype=np.float64)
        if v_mat.shape != (n, n):
            raise MarsDiskError("v_rel has wrong shape")
        if not np.all(np.isfinite(v_mat)) or np.any(v_mat < 0.0):
            raise MarsDiskError("v_rel matrix must be finite and non-negative")
        use_matrix_velocity = True
        v_scalar = 0.0

    use_jit = _USE_NUMBA and not _NUMBA_FAILED if use_numba is None else bool(use_numba)
    kernel: np.ndarray | None = None
    if use_jit:
        try:
            kernel = collision_kernel_numba(
                N_arr, s_arr, H_arr, float(v_scalar), v_mat, bool(use_matrix_velocity)
            )
        except Exception as exc:  # pragma: no cover - fallback path
            _NUMBA_FAILED = True
            kernel = None
            warnings.warn(
                f"compute_collision_kernel_C1: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )

    if kernel is None:
        if workspace is not None:
            v_mat_full = workspace.v_mat_full
            if not use_matrix_velocity:
                v_mat_full.fill(float(v_scalar))
            else:
                v_mat_full[:] = v_mat
            N_outer = workspace.N_outer
            np.multiply(N_arr[:, None], N_arr[None, :], out=N_outer)
            s_sum_sq = workspace_s_sum_sq
            delta = workspace_delta
            H_sq = workspace.H_sq
            H2 = H_arr * H_arr
            np.add(H2[:, None], H2[None, :], out=H_sq)
            H_ij = workspace.H_ij
            np.sqrt(H_sq, out=H_ij)
            kernel = workspace.kernel
            kernel[:] = N_outer / (1.0 + delta)
            kernel *= np.pi
            kernel *= s_sum_sq
            kernel *= v_mat_full
            kernel /= (np.sqrt(2.0 * np.pi) * H_ij)
        else:
            v_mat_full = (
                np.full((n, n), float(v_scalar), dtype=np.float64)
                if not use_matrix_velocity
                else v_mat
            )
            N_outer = np.outer(N_arr, N_arr)
            s_sum_sq = np.add.outer(s_arr, s_arr) ** 2
            delta = np.eye(n)
            H_sq = np.add.outer(H_arr * H_arr, H_arr * H_arr)
            H_ij = np.sqrt(H_sq)
            kernel = (
                N_outer / (1.0 + delta)
                * np.pi
                * s_sum_sq
                * v_mat_full
                / (np.sqrt(2.0 * np.pi) * H_ij)
            )
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("compute_collision_kernel_C1: n_bins=%d use_numba=%s", n, use_jit)
    return kernel


def compute_prod_subblow_area_rate_C2(
    C: np.ndarray, m_subblow: np.ndarray
) -> float:
    """Return the production rate of sub-blowout material.

    The rate is defined as ``sum_{i<=j} C_ij * m_subblow_ij``.

    Parameters
    ----------
    C:
        Collision kernel matrix with shape ``(n, n)``.
    m_subblow:
        Matrix of sub-blowout mass generated per collision pair.

    Returns
    -------
    float
        Production rate of sub-blowout mass.
    """

    global _NUMBA_FAILED
    if C.shape != m_subblow.shape:
        raise MarsDiskError("shape mismatch between C and m_subblow")
    if C.ndim != 2 or C.shape[0] != C.shape[1]:
        raise MarsDiskError("C must be a square matrix")
    n = C.shape[0]
    use_jit = _USE_NUMBA and not _NUMBA_FAILED
    if use_jit:
        try:
            rate = float(compute_prod_subblow_area_rate_C2_numba(np.asarray(C, dtype=np.float64), np.asarray(m_subblow, dtype=np.float64)))
        except Exception:  # pragma: no cover - exercised by fallback
            use_jit = False
            _NUMBA_FAILED = True
            warnings.warn("compute_prod_subblow_area_rate_C2: numba kernel failed; falling back to NumPy.", NumericalWarning)
    if not use_jit:
        idx = np.triu_indices(n)
        rate = float(np.sum(C[idx] * m_subblow[idx]))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("compute_prod_subblow_area_rate_C2: rate=%e", rate)
    return rate
\end{Verbatim}

### B.4 Smoluchowski の IMEX-BDF(1) 更新（C3–C4）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/smol.py

def step_imex_bdf1_C3(
    N: Iterable[float],
    C: np.ndarray,
    Y: np.ndarray,
    S: Iterable[float] | None,
    m: Iterable[float],
    prod_subblow_mass_rate: float | None,
    dt: float,
    *,
    source_k: Iterable[float] | None = None,
    S_external_k: Iterable[float] | None = None,
    S_sublimation_k: Iterable[float] | None = None,
    extra_mass_loss_rate: float = 0.0,
    mass_tol: float = 5e-3,
    safety: float = 0.1,
    diag_out: MutableMapping[str, float] | None = None,
    workspace: ImexWorkspace | None = None,
) -> tuple[np.ndarray, float, float]:
    """Advance the Smoluchowski system by one time step.

    The integration employs an IMEX-BDF(1) scheme: loss terms are treated
    implicitly while the gain terms and sink ``S`` are explicit.  In the
    sublimation-only configuration used by :func:`marsdisk.run.run_zero_d`,
    this reduces to a pure sink update with ``C=0``, ``Y=0`` and non-zero
    ``S_sublimation_k``.

    Parameters
    ----------
    N:
        Array of number surface densities for each size bin.
    C:
        Collision kernel matrix ``C_{ij}``.
    Y:
        Fragment distribution where ``Y[k, i, j]`` is the fraction of mass
        from a collision ``(i, j)`` placed into bin ``k``.
    S:
        Explicit sink term ``S_k`` for each bin.  ``None`` disables the
        legacy sink input.
    S_external_k:
        Optional additional sink term combined with ``S`` (1/s).
    S_sublimation_k:
        Optional sublimation sink (1/s) summed with ``S``.  This is the
        preferred entrypoint for the pure-sink mode.
    m:
        Particle mass associated with each bin.
    prod_subblow_mass_rate:
        Nominal mass source rate (kg/m^2/s) associated with external supply.
        When ``source_k`` is provided the per-bin source is mapped back to a
        mass rate via ``sum(m_k * source_k)`` for the mass budget check.  A
        ``None`` value defers entirely to that computed rate.
    source_k:
        Optional explicit source vector ``F_k`` (1/s) that injects particles
        into the Smol system.  A zero vector preserves the legacy behaviour.
    extra_mass_loss_rate:
        Additional mass flux leaving the system (kg m^-2 s^-1) that should be
        included in the mass budget check (e.g. sublimation sinks handled
        outside the explicit ``S`` vector).  This feeds directly into
        :func:`compute_mass_budget_error_C4`.
    dt:
        Initial time step.
    mass_tol:
        Tolerance on the relative mass conservation error.
    safety:
        Safety factor controlling the maximum allowed step size relative to
        the minimum collision time.
    diag_out:
        Optional dictionary populated with diagnostic mass rates (gain, loss,
        sink, source) after the step is accepted.
    workspace:
        Optional reusable buffers for ``gain`` and ``loss`` vectors to reduce
        allocations when calling the solver repeatedly.

    Returns
    -------
    tuple of ``(N_new, dt_eff, mass_error)``
        Updated number densities, the actual time step used and the relative
        mass conservation error as defined in (C4).
    """

    global _NUMBA_FAILED
    N_arr = np.asarray(N, dtype=float)
    S_base = np.zeros_like(N_arr) if S is None else np.asarray(S, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if N_arr.ndim != 1 or S_base.ndim != 1 or m_arr.ndim != 1:
        raise MarsDiskError("N, S and m must be one-dimensional")
    if not (len(N_arr) == len(S_base) == len(m_arr)):
        raise MarsDiskError("array lengths must match")
    if C.shape != (N_arr.size, N_arr.size):
        raise MarsDiskError("C has incompatible shape")
    if Y.shape != (N_arr.size, N_arr.size, N_arr.size):
        raise MarsDiskError("Y has incompatible shape")
    if dt <= 0.0:
        raise MarsDiskError("dt must be positive")

    def _optional_sink(arr: Iterable[float] | None, name: str) -> np.ndarray:
        if arr is None:
            return np.zeros_like(N_arr)
        arr_np = np.asarray(arr, dtype=float)
        if arr_np.shape != N_arr.shape:
            raise MarsDiskError(f"{name} has incompatible shape")
        return arr_np

    source_arr = _optional_sink(source_k, "source_k")
    S_external_arr = _optional_sink(S_external_k, "S_external_k")
    S_sub_arr = _optional_sink(S_sublimation_k, "S_sublimation_k")
    S_arr = S_base + S_external_arr + S_sub_arr

    gain_out = None
    loss_out = None
    if workspace is not None:
        gain_buf = getattr(workspace, "gain", None)
        loss_buf = getattr(workspace, "loss", None)
        if isinstance(gain_buf, np.ndarray) and gain_buf.shape == N_arr.shape:
            gain_out = gain_buf
        if isinstance(loss_buf, np.ndarray) and loss_buf.shape == N_arr.shape:
            loss_out = loss_buf

    try_use_numba = _USE_NUMBA and not _NUMBA_FAILED
    if try_use_numba:
        try:
            loss = loss_sum_numba(np.asarray(C, dtype=np.float64))
        except Exception as exc:  # pragma: no cover - fallback
            try_use_numba = False
            _NUMBA_FAILED = True
            warnings.warn(f"loss_sum_numba failed ({exc!r}); falling back to NumPy.", NumericalWarning)
    if not try_use_numba:
        if loss_out is not None:
            np.sum(C, axis=1, out=loss_out)
            loss = loss_out
        else:
            loss = np.sum(C, axis=1)
    # C_ij already halves the diagonal, so add it back for the loss coefficient.
    if C.size:
        loss = loss + np.diagonal(C)
    # Convert summed collision rate (includes N_i) to the loss coefficient.
    safe_N = np.where(N_arr > 0.0, N_arr, 1.0)
    loss = np.where(N_arr > 0.0, loss / safe_N, 0.0)
    t_coll = 1.0 / np.maximum(loss, 1e-30)
    dt_max = safety * float(np.min(t_coll))
    dt_eff = min(float(dt), dt_max)

    source_mass_rate = float(np.sum(m_arr * source_arr))
    if prod_subblow_mass_rate is None:
        prod_mass_rate_budget = source_mass_rate
    else:
        prod_mass_rate_budget = float(prod_subblow_mass_rate)

    gain = _gain_tensor(C, Y, m_arr, out=gain_out, workspace=workspace)

    while True:
        N_new = (N_arr + dt_eff * (gain + source_arr - S_arr * N_arr)) / (1.0 + dt_eff * loss)
        if np.any(N_new < 0.0):
            dt_eff *= 0.5
            continue
        mass_err = compute_mass_budget_error_C4(
            N_arr,
            N_new,
            m_arr,
            prod_mass_rate_budget,
            dt_eff,
            extra_mass_loss_rate=float(extra_mass_loss_rate),
        )
        if not np.isfinite(mass_err):
            raise MarsDiskError("mass budget error is non-finite; check PSD or kernel inputs")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("step_imex_bdf1_C3: dt=%e mass_err=%e", dt_eff, mass_err)
        if mass_err <= mass_tol:
            break
        dt_eff *= 0.5

    if diag_out is not None:
        diag_out["gain_mass_rate"] = float(np.sum(m_arr * gain))
        diag_out["loss_mass_rate"] = float(np.sum(m_arr * loss * N_new))
        diag_out["sink_mass_rate"] = float(np.sum(m_arr * S_arr * N_arr))
        diag_out["source_mass_rate"] = float(np.sum(m_arr * source_arr))

    return N_new, dt_eff, mass_err


def compute_mass_budget_error_C4(
    N_old: Iterable[float],
    N_new: Iterable[float],
    m: Iterable[float],
    prod_subblow_mass_rate: float,
    dt: float,
    *,
    extra_mass_loss_rate: float = 0.0,
) -> float:
    """Return the relative mass budget error according to (C4).

    The budget compares the initial mass to the combination of retained mass
    and explicit source/sink fluxes:

    ``M_old + dt * prod_subblow_mass_rate = M_new + dt * extra_mass_loss_rate``.
    """

    global _NUMBA_FAILED
    N_old_arr = np.asarray(N_old, dtype=float)
    N_new_arr = np.asarray(N_new, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if not (N_old_arr.shape == N_new_arr.shape == m_arr.shape):
        raise MarsDiskError("array shapes must match")

    if _USE_NUMBA and not _NUMBA_FAILED:
        try:
            err = float(
                mass_budget_error_numba(
                    m_arr * 0.0 + N_old_arr,  # ensure contiguous copies
                    m_arr * 0.0 + N_new_arr,
                    m_arr,
                    float(prod_subblow_mass_rate),
                    float(dt),
                    float(extra_mass_loss_rate),
                )
            )
        except Exception as exc:  # pragma: no cover - fallback
            _NUMBA_FAILED = True
            warnings.warn(
                f"compute_mass_budget_error_C4: numba kernel failed ({exc!r}); falling back to NumPy.",
                NumericalWarning,
            )
            err = None
    else:
        err = None

    if err is None:
        M_before = float(np.sum(m_arr * N_old_arr))
        M_after = float(np.sum(m_arr * N_new_arr))
        prod_term = dt * float(prod_subblow_mass_rate)
        sink_term = dt * float(extra_mass_loss_rate)
        if M_before > 0.0:
            err = abs((M_after + sink_term) - (M_before + prod_term)) / M_before
        else:
            err = float("inf")
    return float(err)
\end{Verbatim}

### B.5 表層密度の更新と流出（S1）

\begin{Verbatim}[breaklines=true, breakanywhere=true, fontsize=\small]
# marsdisk/physics/surface.py

def step_surface_density_S1(
    sigma_surf: float,
    prod_subblow_area_rate: float,
    dt: float,
    Omega: float,
    *,
    t_blow: float | None = None,
    t_coll: float | None = None,
    t_sink: float | None = None,
    sigma_tau1: float | None = None,
    enable_blowout: bool = True,
) -> SurfaceStepResult:
    """Advance the surface density by one implicit Euler step (S1).

    Parameters
    ----------
    sigma_surf:
        Current surface mass density ``Σ_surf``.
        prod_subblow_area_rate:
        Production rate of sub--blow-out material per unit area after mixing.
    dt:
        Time step.
    Omega:
        Keplerian angular frequency; sets ``t_blow = 1/Ω``.
    t_blow:
        Optional blow-out time-scale. When provided this overrides ``1/Ω``.
    t_coll:
        Optional collisional time-scale ``t_coll``.  When provided the
        loss term ``Σ_surf/t_coll`` is treated implicitly.
    t_sink:
        Optional additional sink time-scale representing sublimation or
        gas drag.  ``None`` disables the term.
    sigma_tau1:
        Diagnostic Σ_{τ=1} value passed through for logging; no clipping
        is applied in the surface ODE.
    enable_blowout:
        Toggle for the radiation-pressure loss term.  Disable to remove the
        ``1/t_blow`` contribution and force the returned outflux to zero.

    Returns
    -------
    SurfaceStepResult
        dataclass holding the updated density and associated fluxes.
    """

    global _SURFACE_ODE_WARNED
    if not _SURFACE_ODE_WARNED:
        warnings.warn(SURFACE_ODE_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
        _SURFACE_ODE_WARNED = True

    if dt <= 0.0 or Omega <= 0.0:
        raise MarsDiskError("dt and Omega must be positive")

    if t_blow is None:
        t_blow = 1.0 / Omega
    elif t_blow <= 0.0 or not np.isfinite(t_blow):
        raise MarsDiskError("t_blow must be positive and finite")
    loss = 0.0
    if enable_blowout:
        loss += 1.0 / t_blow
    if t_coll is not None and t_coll > 0.0:
        loss += 1.0 / t_coll
    if t_sink is not None and t_sink > 0.0:
        loss += 1.0 / t_sink

    numerator = sigma_surf + dt * prod_subblow_area_rate
    sigma_new = numerator / (1.0 + dt * loss)

    outflux = sigma_new / t_blow if enable_blowout else 0.0
    sink_flux = sigma_new / t_sink if (t_sink is not None and t_sink > 0.0) else 0.0
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "step_surface_density_S1: dt=%e sigma=%e sigma_tau1=%e t_blow=%e t_coll=%e t_sink=%e outflux=%e blowout=%s",
            dt,
            sigma_new,
            sigma_tau1 if sigma_tau1 is not None else float("nan"),
            t_blow,
            t_coll if t_coll is not None else float("nan"),
            t_sink if t_sink is not None else float("nan"),
            outflux,
            enable_blowout,
        )
    return SurfaceStepResult(sigma_new, outflux, sink_flux)
\end{Verbatim}
