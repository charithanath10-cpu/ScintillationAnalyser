"""
scintillation_detector.py — Ionospheric scintillation detection engine.

Works on the long-form range_df produced by log_decoders.py.

Public API
----------
enrich_range_df(range_df)
    Adds per-signal diff and flag columns to the range DataFrame.
    Called once after parsing — single vectorised pass, O(n).

epoch_health(enriched_df)
    Rolls up per-signal flags to a per-epoch health verdict.
    Returns a separate summary DataFrame (one row per epoch).

Flag definitions
----------------
cno_flag   (per signal)
    NONE   — drop < 5 dB from previous epoch
    WARN   — drop ≥ 5 dB
    STRONG — drop ≥ 8 dB

adr_flag   (per signal, raw threshold on adr_std value)
    NONE   — adr_std ≤ 0.02
    EARLY  — adr_std > 0.02   (early anomaly)
    STRONG — adr_std > 0.05   (strong scintillation)
    SEVERE — adr_std > 0.10   (cycle slips likely)

lock_flag  (per signal)
    False  — locktime stable or increasing
    True   — locktime decreased → tracking discontinuity

combined_flag (per signal)
    NONE   — neither cno nor adr triggered
    TRUE   — cno_flag ≥ WARN  AND  adr_flag ≥ EARLY
    STRONG — cno_flag = STRONG AND  adr_flag ≥ STRONG

Epoch-level verdicts
--------------------
cno_epoch_flag
    BAD     — ALL signals at this epoch have cno_flag WARN or STRONG
    WARNING — SOME (but not all) signals are WARN or STRONG
    GOOD    — no signal is WARN or STRONG

adr_epoch_flag
    BAD     — ALL signals are EARLY, STRONG, or SEVERE
    WARNING — SOME (but not all) signals are EARLY, STRONG, or SEVERE
    GOOD    — no signal exceeds threshold

lock_epoch_flag
    BAD     — ALL signals show a lock discontinuity
    WARNING — SOME (but not all) signals show a lock discontinuity
    GOOD    — no signal flagged
"""

import numpy as np
import pandas as pd

# ── ordered categoricals so comparisons like flag >= "WARN" work correctly ──
_CNO_CAT   = pd.CategoricalDtype(["NONE", "WARN", "STRONG"],               ordered=True)
_ADR_CAT   = pd.CategoricalDtype(["NONE", "EARLY", "STRONG", "SEVERE"],    ordered=True)
_COMB_CAT  = pd.CategoricalDtype(["NONE", "TRUE", "STRONG"],               ordered=True)
_EPOCH_CAT = pd.CategoricalDtype(["GOOD", "WARNING", "BAD"],               ordered=True)


# ═══════════════════════════════════════════════════════════════════
# STEP 1 — per-signal enrichment
# ═══════════════════════════════════════════════════════════════════

def enrich_range_df(range_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add diff-based and threshold-based flag columns to range_df.

    Input columns required : gps_week, gps_seconds, constellation, signal,
                             prn, cn0, adr_std, locktime
    Added columns          : cno_drop, lock_drop,
                             cno_flag, adr_flag, lock_flag, combined_flag

    Returns a new DataFrame (does not modify the input).
    The rows are sorted by satellite track then time — callers should
    re-sort by gps_seconds if they need chronological order afterwards.
    """
    if range_df.empty:
        return range_df.copy()

    df = range_df.copy()

    # ── sort so every (constellation, signal, prn) track is contiguous ──
    df = df.sort_values(
        ["constellation", "signal", "prn", "gps_week", "gps_seconds"],
        ignore_index=True,
    )

    # ── vectorised diff within each satellite track — single C-level pass ──
    track = df.groupby(["constellation", "signal", "prn"], sort=False)

    # positive cno_drop  = signal got weaker  (we flip sign so drop is positive)
    df["cno_drop"]  = track["cn0"].diff().mul(-1)

    # positive lock_drop = locktime decreased = tracking reset / discontinuity
    df["lock_drop"] = track["locktime"].diff().mul(-1)

    # ── cno_flag ─────────────────────────────────────────────────────────────
    # bins are right-open on the left: (-inf, 5) → NONE, [5, 8) → WARN, [8, ∞) → STRONG
    df["cno_flag"] = pd.cut(
        df["cno_drop"],
        bins=[-np.inf, 5.0, 8.0, np.inf],
        labels=["NONE", "WARN", "STRONG"],
        right=False,          # left-closed intervals: [5,8) not (5,8]
    ).astype(_CNO_CAT)

    # first epoch of each track has NaN cno_drop → flag as NONE
    df["cno_flag"] = df["cno_flag"].cat.add_categories([]) \
        if False else df["cno_flag"]   # no-op; fillna below handles it
    df["cno_flag"] = df["cno_flag"].fillna("NONE").astype(_CNO_CAT)

    # ── adr_flag ─────────────────────────────────────────────────────────────
    # thresholds are on the raw adr_std value (no diff needed)
    df["adr_flag"] = pd.cut(
        df["adr_std"],
        bins=[-np.inf, 0.02, 0.05, 0.10, np.inf],
        labels=["NONE", "EARLY", "STRONG", "SEVERE"],
        right=True,           # (0.02, 0.05] → EARLY etc.  matches "> threshold"
    ).astype(_ADR_CAT)
    df["adr_flag"] = df["adr_flag"].fillna("NONE").astype(_ADR_CAT)

    # ── lock_flag ─────────────────────────────────────────────────────────────
    # True when locktime dropped (positive lock_drop); NaN on first epoch → False
    df["lock_flag"] = df["lock_drop"].gt(0).where(df["lock_drop"].notna(), False)

    # ── combined_flag ─────────────────────────────────────────────────────────
    cno_warn   = df["cno_flag"] >= "WARN"
    cno_strong = df["cno_flag"] == "STRONG"
    adr_early  = df["adr_flag"] >= "EARLY"
    adr_strong = df["adr_flag"] >= "STRONG"

    conditions = [
        cno_strong & adr_strong,   # STRONG combined
        cno_warn   & adr_early,    # TRUE combined
    ]
    choices = ["STRONG", "TRUE"]
    df["combined_flag"] = np.select(conditions, choices, default="NONE")
    df["combined_flag"] = df["combined_flag"].astype(_COMB_CAT)

    return df


# ═══════════════════════════════════════════════════════════════════
# STEP 3 — region & local-time flags  (from BESTPOS)
# ═══════════════════════════════════════════════════════════════════

def _gps_to_local_hour(gps_week: int, gps_seconds: float, longitude: float) -> float:
    """Convert GPS week + seconds to local solar hour (0–24)."""
    utc_seconds = gps_week * 604800.0 + gps_seconds - 18  # 18 leap seconds offset
    utc_hour    = (utc_seconds % 86400) / 3600.0
    local_hour  = (utc_hour + longitude / 15.0) % 24.0
    return local_hour


def enrich_bestpos_df(bestpos_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add region_flag, local_hour and time_flag columns to bestpos_df.

    region_flag : True if location is in auroral (60°–75° lat) or
                  equatorial (±20° lat) scintillation-prone zones.

    local_hour  : local solar hour derived from GPS time + longitude.

    time_flag   : True if equatorial region AND after sunset
                  (local hour 18:00–06:00).

    Returns a new DataFrame — input is not modified.
    """
    if bestpos_df.empty:
        return bestpos_df.copy()

    df = bestpos_df.copy()

    # Step 1 — region
    df["region_flag"] = (
        df["latitude"].abs().between(60, 75)      # auroral
        | (df["latitude"].abs() <= 20)             # equatorial
    )

    # Step 2 — local solar hour
    df["local_hour"] = df.apply(
        lambda r: _gps_to_local_hour(r["gps_week"], r["gps_seconds"], r["longitude"]),
        axis=1,
    )

    # Step 2 — time flag: equatorial + after sunset (18:00–06:00 local)
    df["time_flag"] = (
        (df["latitude"].abs() <= 20)
        & ((df["local_hour"] >= 18) | (df["local_hour"] < 6))
    )

    return df


def enrich_range_with_elevation(
    range_df: pd.DataFrame,
    satvis2_df: pd.DataFrame,
    environment_type: str = "OPEN_SKY",
) -> pd.DataFrame:
    """
    Join elevation/azimuth from satvis2_df onto range_df using a nearest-time
    merge per (constellation, prn), then compute high_elev_lock_flag.

    Join strategy
    ─────────────
    SATVIS2 and RANGE may log at different rates (e.g. RANGE @ 1 Hz,
    SATVIS2 @ 0.1 Hz).  For each (constellation, prn) track we find the
    satvis2 epoch whose gps_seconds is closest to the range epoch's
    gps_seconds, within the same gps_week, and attach its elevation and
    azimuth.  If no satvis2 record exists for that satellite at all,
    elevation/azimuth remain NaN and the flag stays False.

    high_elev_lock_flag
    ───────────────────
    True when ALL three conditions hold:
        1. lock_flag is True         (tracking discontinuity detected)
        2. elevation > 50°           (satellite is high in the sky)
        3. environment_type == "OPEN_SKY"   (no obstructions expected)

    When environment_type != "OPEN_SKY" the flag is always False —
    low-elevation or obstructed-sky lock loss is not a strong scintillation
    indicator. Pass environment_type from the frontend when known.

    Returns a new DataFrame with added columns:
        elevation, azimuth, high_elev_lock_flag
    """
    if range_df.empty:
        return range_df.copy()

    df = range_df.copy()

    # ── default columns in case satvis2 is empty or has no matches ───────────
    df["elevation"]            = float("nan")
    df["azimuth"]              = float("nan")
    df["high_elev_lock_flag"]  = False

    if satvis2_df.empty:
        return df

    # ── build a numeric timestamp for nearest-match ───────────────────────────
    sv = satvis2_df[["gps_week", "gps_seconds", "constellation", "prn",
                     "elevation", "azimuth"]].copy()
    sv["_sv_ts"] = sv["gps_week"] * 604800.0 + sv["gps_seconds"]
    df["_rng_ts"] = df["gps_week"] * 604800.0 + df["gps_seconds"]

    # ── nearest-match merge per (constellation, prn) ──────────────────────────
    # Strategy: sort both sides, use merge_asof per group.
    # merge_asof requires both sides sorted by the key column.
    sv_sorted  = sv.sort_values("_sv_ts")
    df_sorted  = df.sort_values("_rng_ts")

    # pandas merge_asof: for each row in df find the nearest row in sv
    # with the same (constellation, prn) — direction="nearest" picks
    # the closest timestamp whether before or after.
    merged = pd.merge_asof(
        df_sorted,
        sv_sorted[["_sv_ts", "constellation", "prn", "elevation", "azimuth"]],
        left_on="_rng_ts",
        right_on="_sv_ts",
        by=["constellation", "prn"],
        direction="nearest",
        suffixes=("", "_sv"),
    )

    # merge_asof column naming: since range_df already has elevation/azimuth
    # set to NaN above, the merge overwrites them correctly via suffixes.
    # Restore original index order.
    merged = merged.sort_index()

    # ── high_elev_lock_flag ───────────────────────────────────────────────────
    merged["high_elev_lock_flag"] = (
        merged["lock_flag"].astype(bool)
        & (merged["elevation"] > 50.0)
        & (environment_type == "OPEN_SKY")
    )

    # ── clean up helper columns ───────────────────────────────────────────────
    merged = merged.drop(columns=["_rng_ts", "_sv_ts"], errors="ignore")

    return merged


# ═══════════════════════════════════════════════════════════════════
# STEP 2 — epoch-level health rollup
# ═══════════════════════════════════════════════════════════════════

def epoch_health(enriched_df: pd.DataFrame) -> pd.DataFrame:
    """
    Roll up per-signal flags to one health verdict per epoch (timestamp).

    Input  : output of enrich_range_df() + enrich_range_with_elevation()
    Output : one row per (gps_week, gps_seconds) with columns:
               n_signals            — total satellite signals observed
               n_cno_flagged        — signals with cno_flag WARN or STRONG
               n_adr_flagged        — signals with adr_flag EARLY/STRONG/SEVERE
               n_lock_flagged       — signals with lock_flag True
               n_high_elev_lock     — signals with high_elev_lock_flag True
               cno_epoch_flag       — GOOD / WARNING / BAD
               adr_epoch_flag       — GOOD / WARNING / BAD
               lock_epoch_flag      — GOOD / WARNING / BAD
               high_elev_lock_flag  — True if any signal triggered at this epoch
    """
    if enriched_df.empty:
        return pd.DataFrame()

    def _verdict(n_flagged: pd.Series, n_total: pd.Series) -> pd.Series:
        result = pd.Series("GOOD", index=n_flagged.index, dtype=object)
        result[n_flagged > 0]              = "WARNING"
        result[n_flagged == n_total]       = "BAD"
        return result.astype(_EPOCH_CAT)

    df = enriched_df.copy()
    df["_cno_any"]     = df["cno_flag"]  >= "WARN"
    df["_adr_any"]     = df["adr_flag"]  >= "EARLY"
    df["_lock_any"]    = df["lock_flag"].astype(bool)
    df["_hi_elev_any"] = df["high_elev_lock_flag"].astype(bool) \
                         if "high_elev_lock_flag" in df.columns else False

    # per-signal severity booleans needed for final decision
    df["_cno_true"]      = df["cno_flag"]  >= "WARN"      # cno_flag TRUE in spec
    df["_adr_strong"]    = df["adr_flag"]  >= "STRONG"    # adr_flag STRONG
    df["_adr_severe"]    = df["adr_flag"]  == "SEVERE"    # adr_flag SEVERE
    df["_combined_true"] = df["combined_flag"] >= "TRUE"  if "combined_flag" in df.columns else False
    df["_combined_strong"]= df["combined_flag"] == "STRONG" if "combined_flag" in df.columns else False
    df["_lock_true"]     = df["lock_flag"].astype(bool)

    grp = df.groupby(["gps_week", "gps_seconds"], sort=True)

    summary = grp.agg(
        n_signals            = ("prn",              "count"),
        n_cno_flagged        = ("_cno_any",          "sum"),
        n_adr_flagged        = ("_adr_any",          "sum"),
        n_lock_flagged       = ("_lock_any",         "sum"),
        n_high_elev_lock     = ("_hi_elev_any",      "sum"),
        # severity counts for final decision
        any_cno_true         = ("_cno_true",         "any"),
        any_adr_strong       = ("_adr_strong",       "any"),
        any_adr_severe       = ("_adr_severe",       "any"),
        any_combined_true    = ("_combined_true",    "any"),
        any_combined_strong  = ("_combined_strong",  "any"),
        any_lock_true        = ("_lock_true",        "any"),
    ).reset_index()

    summary["cno_epoch_flag"]       = _verdict(summary["n_cno_flagged"],  summary["n_signals"])
    summary["adr_epoch_flag"]       = _verdict(summary["n_adr_flagged"],  summary["n_signals"])
    summary["lock_epoch_flag"]      = _verdict(summary["n_lock_flagged"], summary["n_signals"])
    summary["high_elev_lock_flag"]  = summary["n_high_elev_lock"] > 0

    return summary


# ═══════════════════════════════════════════════════════════════════
# STEP 4 — final scintillation decision  (one row per epoch)
# ═══════════════════════════════════════════════════════════════════

# Thresholds: fraction of total epochs that must be flagged
# before a condition is considered sustained (not a spike)
_WARN_THRESHOLD   = 0.30   # 30% of epochs → condition is real
_STRONG_THRESHOLD = 0.50   # 50% of epochs → condition is persistent

# Confidence level order
_CONF_CAT = pd.CategoricalDtype(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"], ordered=True)

# Scintillation flag order
_SCINT_CAT = pd.CategoricalDtype(
    ["FALSE", "POSSIBLE_INTERFERENCE", "TRUE", "STRONG", "VERY_HIGH"], ordered=True
)

_CONF_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}
_CONF_UP   = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]   # index = current rank


def _bump_conf(current: str, steps: int = 1) -> str:
    """Raise confidence by `steps` levels, capped at VERY_HIGH."""
    return _CONF_UP[min(_CONF_RANK[current] + steps, 3)]


def compute_file_level_rates(epoch_health_df: pd.DataFrame) -> dict:
    """
    Compute what fraction of all epochs in the file are flagged for each
    condition.  These rates gate the final decision so that isolated spikes
    do not trigger a scintillation detection.

    Returns a dict:
    {
      "total_epochs": int,
      "cno_rate":           float,   # fraction of epochs where any signal had cno_flag≥WARN
      "adr_early_rate":     float,   # fraction where any adr_flag≥EARLY
      "adr_strong_rate":    float,   # fraction where any adr_flag≥STRONG
      "adr_severe_rate":    float,   # fraction where any adr_flag=SEVERE
      "combined_true_rate": float,
      "combined_strong_rate": float,
      "lock_rate":          float,   # fraction where any lock_flag=True
      "high_elev_lock_rate":float,
    }
    """
    if epoch_health_df.empty:
        return {k: 0.0 for k in [
            "total_epochs", "cno_rate", "adr_early_rate", "adr_strong_rate",
            "adr_severe_rate", "combined_true_rate", "combined_strong_rate",
            "lock_rate", "high_elev_lock_rate"
        ]}

    n = len(epoch_health_df)

    def _rate(col: str) -> float:
        if col not in epoch_health_df.columns:
            return 0.0
        return float(epoch_health_df[col].astype(bool).sum()) / n

    return {
        "total_epochs":         n,
        "cno_rate":             _rate("any_cno_true"),
        "adr_early_rate":       float((epoch_health_df["n_adr_flagged"] > 0).sum()) / n
                                if "n_adr_flagged" in epoch_health_df.columns else 0.0,
        "adr_strong_rate":      _rate("any_adr_strong"),
        "adr_severe_rate":      _rate("any_adr_severe"),
        "combined_true_rate":   _rate("any_combined_true"),
        "combined_strong_rate": _rate("any_combined_strong"),
        "lock_rate":            _rate("any_lock_true"),
        "high_elev_lock_rate":  _rate("high_elev_lock_flag"),
    }



def detect_scintillation(
    epoch_health_df:  pd.DataFrame,
    bestpos_df:       pd.DataFrame,
    environment_type: str = "OPEN_SKY",
) -> pd.DataFrame:
    """
    Final per-epoch scintillation decision using all computed flags.

    Inputs
    ──────
    epoch_health_df  : output of epoch_health()
                       must contain: gps_week, gps_seconds,
                         cno_epoch_flag, adr_epoch_flag, lock_epoch_flag,
                         high_elev_lock_flag,
                         n_cno_flagged, n_adr_flagged, n_lock_flagged
    bestpos_df       : output of enrich_bestpos_df()
                       must contain: gps_week, gps_seconds,
                         region_flag, time_flag
                       Optional — if empty, region/time flags default False.
    environment_type : "OPEN_SKY" or "OBSTRUCTED" — passed from frontend.

    Output
    ──────
    One row per epoch with columns:
        gps_week, gps_seconds,
        region_flag, time_flag,           ← from bestpos (NaN-safe)
        cno_epoch_flag, adr_epoch_flag,
        lock_epoch_flag, high_elev_lock_flag,
        scintillation_flag,               ← FALSE/TRUE/STRONG/VERY_HIGH/POSSIBLE_INTERFERENCE
        confidence_level                  ← LOW/MEDIUM/HIGH/VERY_HIGH

    Decision logic (matches the pseudocode spec)
    ─────────────────────────────────────────────
    Start: scintillation_flag=FALSE, confidence=LOW

    MEDIUM  (requires region context):
        region_flag AND (combined_flag=TRUE OR adr_flag=STRONG OR cno_flag=TRUE)
        → scintillation_flag=TRUE, confidence=MEDIUM
        Note: freq_flag and rf_flag from spec treated as True (not yet computed)

    HIGH  (no region needed — pure signal evidence):
        combined_flag=STRONG OR adr_flag=SEVERE OR lock_flag=TRUE
        → scintillation_flag=STRONG, confidence=HIGH

    VERY_HIGH:
        high_elevation_lock_loss_flag=True AND OPEN_SKY
        → scintillation_flag=VERY_HIGH, confidence=VERY_HIGH

    Confidence booster:
        time_flag=True (post-sunset equatorial) → confidence +1 level
        space_weather_flag → TODO (future input)

    Interference override:
        freq_flag=False OR rf_flag=False → POSSIBLE_INTERFERENCE
        DISABLED until freq_flag (Step 8) and rf_flag (Step 10) are implemented.

    Steps not yet implemented:
        Step 8  : freq_flag  — requires multi-frequency signal comparison
        Step 9  : azimuth_flag — future
        Step 10 : rf_flag / AGC — requires ITDETECTSTATUS AGC data
        Step 11 : space_weather_flag — requires KP index feed
    """
    if epoch_health_df.empty:
        return pd.DataFrame()

    df = epoch_health_df.copy()

    # ── join region / time flags from bestpos ─────────────────────────────────
    if not bestpos_df.empty and {"region_flag", "time_flag"}.issubset(bestpos_df.columns):
        # nearest-time join: bestpos may be at a different rate
        bp = bestpos_df[["gps_week", "gps_seconds", "region_flag", "time_flag"]].copy()
        bp["_bp_ts"]  = bp["gps_week"]  * 604800.0 + bp["gps_seconds"]
        df["_ep_ts"]  = df["gps_week"]  * 604800.0 + df["gps_seconds"]

        bp_sorted = bp.sort_values("_bp_ts")
        df_sorted = df.sort_values("_ep_ts")

        df = pd.merge_asof(
            df_sorted,
            bp_sorted[["_bp_ts", "region_flag", "time_flag"]],
            left_on="_ep_ts",
            right_on="_bp_ts",
            direction="nearest",
        ).sort_index().drop(columns=["_ep_ts", "_bp_ts"], errors="ignore")
    else:
        df["region_flag"] = False
        df["time_flag"]   = False

    # ── convenience booleans — gated by file-level rates ─────────────────────
    # A condition only counts if it appears in enough epochs across the file,
    # not just a single spike.
    # WARN_THRESHOLD  (30%): enough to be a real pattern → medium/high trigger
    # STRONG_THRESHOLD (50%): majority of file affected  → stronger trigger
    rates = compute_file_level_rates(df)

    region   = df["region_flag"].astype(bool)
    time_f   = df["time_flag"].astype(bool)
    open_sky = environment_type == "OPEN_SKY"
    hi_elev  = df["high_elev_lock_flag"].astype(bool)

    # File-level boolean gates (scalar — same value applied to all epochs)
    cno_sustained         = rates["cno_rate"]             >= _WARN_THRESHOLD
    adr_strong_sustained  = rates["adr_strong_rate"]      >= _WARN_THRESHOLD
    adr_severe_sustained  = rates["adr_severe_rate"]      >= _WARN_THRESHOLD
    combined_true_sust    = rates["combined_true_rate"]   >= _WARN_THRESHOLD
    combined_strong_sust  = rates["combined_strong_rate"] >= _WARN_THRESHOLD
    lock_sustained        = rates["lock_rate"]            >= _WARN_THRESHOLD

    # For per-epoch columns, also gate by the file-level rate
    # so the epoch-level flag only propagates if the file-level rate is met
    cno_true        = df["any_cno_true"].astype(bool)        & cno_sustained
    adr_strong      = df["any_adr_strong"].astype(bool)      & adr_strong_sustained
    adr_severe      = df["any_adr_severe"].astype(bool)      & adr_severe_sustained
    combined_true   = df["any_combined_true"].astype(bool)   & combined_true_sust
    combined_strong = df["any_combined_strong"].astype(bool) & combined_strong_sust
    lock_true       = df["any_lock_true"].astype(bool)       & lock_sustained

    # ── Final Decision Logic — exact spec order ───────────────────────────────

    # MEDIUM: region AND (combined=TRUE OR adr=STRONG OR cno=TRUE)
    # freq_flag and rf_flag omitted (not yet computed) — treated as True for now
    medium = region & (combined_true | adr_strong | cno_true)

    # HIGH: combined=STRONG OR adr=SEVERE OR lock=TRUE  (no region needed)
    high   = combined_strong | adr_severe | lock_true

    # VERY_HIGH: high_elevation_lock_loss_flag
    very_high = hi_elev & open_sky

    # Priority: highest wins
    scint_conditions = [very_high, high, medium]
    scint_choices    = ["VERY_HIGH", "STRONG", "TRUE"]
    df["scintillation_flag"] = np.select(
        scint_conditions, scint_choices, default="FALSE"
    ).astype(object)

    # ── Interference override ─────────────────────────────────────────────────
    # Spec: IF freq_flag==FALSE OR rf_flag==FALSE → POSSIBLE_INTERFERENCE
    # freq_flag (Step 8) and rf_flag (Step 10 / AGC) are not yet implemented.
    # Override is DISABLED until those inputs are available — do not approximate
    # with a heuristic that would produce wrong results.
    # TODO: wire freq_flag and rf_flag when ITDETECTSTATUS / AGC data is added.

    # ── Base confidence from scintillation level ──────────────────────────────
    conf_map = {
        "FALSE":                 "LOW",
        "POSSIBLE_INTERFERENCE": "LOW",
        "TRUE":                  "MEDIUM",
        "STRONG":                "HIGH",
        "VERY_HIGH":             "VERY_HIGH",
    }
    df["confidence_level"] = df["scintillation_flag"].map(conf_map)

    # ── Confidence boosters ───────────────────────────────────────────────────
    # time_flag (post-sunset equatorial) or space_weather (future) → +1 level
    boost_mask = time_f & (df["scintillation_flag"] != "FALSE")
    df.loc[boost_mask, "confidence_level"] = df.loc[boost_mask, "confidence_level"].apply(
        lambda c: _bump_conf(c, 1)
    )

    # ── attach file-level rates as constant columns for transparency ─────────
    df["file_cno_rate"]             = round(rates["cno_rate"],             4)
    df["file_adr_strong_rate"]      = round(rates["adr_strong_rate"],      4)
    df["file_adr_severe_rate"]      = round(rates["adr_severe_rate"],      4)
    df["file_combined_strong_rate"] = round(rates["combined_strong_rate"], 4)
    df["file_lock_rate"]            = round(rates["lock_rate"],            4)

    # ── apply ordered categoricals ────────────────────────────────────────────
    df["scintillation_flag"] = df["scintillation_flag"].astype(_SCINT_CAT)
    df["confidence_level"]   = df["confidence_level"].astype(_CONF_CAT)

    # ── select and order output columns ──────────────────────────────────────
    out_cols = [
        "gps_week", "gps_seconds",
        "region_flag", "time_flag",
        "cno_epoch_flag", "adr_epoch_flag", "lock_epoch_flag",
        "high_elev_lock_flag",
        "any_cno_true", "any_adr_strong", "any_adr_severe",
        "any_combined_true", "any_combined_strong", "any_lock_true",
        "n_signals", "n_cno_flagged", "n_adr_flagged",
        "n_lock_flagged", "n_high_elev_lock",
        "file_cno_rate", "file_adr_strong_rate", "file_adr_severe_rate",
        "file_combined_strong_rate", "file_lock_rate",
        "scintillation_flag", "confidence_level",
    ]
    out_cols = [c for c in out_cols if c in df.columns]
    return df[out_cols].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════
# SUMMARY — human-readable JSON report
# ═══════════════════════════════════════════════════════════════════

def summarise_results(
    scintillation_df: pd.DataFrame,
    epoch_health_df:  pd.DataFrame,
    bestpos_df:       pd.DataFrame,
    range_df:         pd.DataFrame,
) -> dict:
    """
    Produce a concise JSON-serialisable summary of the scintillation analysis.

    Structure
    ─────────
    {
      "scintillation_detected": true/false,
      "answer": "Yes — scintillation detected at HIGH confidence",
      "reason": "...",
      "confidence_level": "HIGH",
      "worst_flag": "STRONG",
      "total_epochs": 1200,
      "flagged_epochs": {
          "scintillation_TRUE":  12,
          "scintillation_STRONG": 4,
          "scintillation_VERY_HIGH": 0
      },
      "epoch_flags": {
          "cno_BAD":   8,
          "cno_WARNING": 40,
          "adr_BAD":   3,
          "adr_WARNING": 21,
          "lock_BAD":  2,
          "lock_WARNING": 15,
          "high_elev_lock": 1
      },
      "per_signal_flags": {
          "any_cno_drop_5dB":   true,
          "any_cno_drop_8dB":   false,
          "any_adr_early":      true,
          "any_adr_strong":     false,
          "any_adr_severe":     false,
          "any_combined_true":  true,
          "any_combined_strong":false,
          "any_lock_loss":      true
      },
      "location_flags": {
          "region_flag":  false,
          "time_flag":    false,
          "zone":         "MID-LATITUDE",
          "mean_latitude": 43.21,
          "mean_longitude": -79.45
      },
      "steps_not_evaluated": ["freq_flag (Step 8)", "rf_flag (Step 10)", "space_weather (Step 11)"]
    }
    """
    import json

    out = {}

    # ── scintillation verdict ─────────────────────────────────────────────────
    if scintillation_df.empty:
        out["scintillation_detected"] = False
        out["answer"]          = "No — insufficient data to evaluate scintillation."
        out["reason"]          = "scintillation_df is empty (no RANGEA records parsed)."
        out["confidence_level"]= "LOW"
        out["worst_flag"]      = "FALSE"
    else:
        scint_col  = scintillation_df["scintillation_flag"].astype(str)
        conf_col   = scintillation_df["confidence_level"].astype(str)

        # worst flag seen across all epochs
        _order = {"FALSE": 0, "POSSIBLE_INTERFERENCE": 1,
                  "TRUE": 2, "STRONG": 3, "VERY_HIGH": 4}
        worst  = max(scint_col.unique(), key=lambda x: _order.get(x, 0))
        # best (highest) confidence seen
        _cord  = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}
        best_conf = max(conf_col.unique(), key=lambda x: _cord.get(x, 0))

        detected = worst not in ("FALSE", "POSSIBLE_INTERFERENCE")

        # counts per level
        n_true     = int((scint_col == "TRUE").sum())
        n_strong   = int((scint_col == "STRONG").sum())
        n_vhigh    = int((scint_col == "VERY_HIGH").sum())
        n_interf   = int((scint_col == "POSSIBLE_INTERFERENCE").sum())
        n_total    = len(scintillation_df)

        out["scintillation_detected"] = detected
        out["worst_flag"]       = worst
        out["confidence_level"] = best_conf
        out["total_epochs"]     = n_total

        out["flagged_epochs"] = {
            "scintillation_TRUE":       n_true,
            "scintillation_STRONG":     n_strong,
            "scintillation_VERY_HIGH":  n_vhigh,
            "possible_interference":    n_interf,
        }

        # ── build answer + reason ─────────────────────────────────────────────
        if worst == "VERY_HIGH":
            out["answer"] = "Yes — scintillation detected at VERY HIGH confidence."
            out["reason"] = (
                f"High-elevation loss of lock in open sky detected at {n_vhigh} epoch(s). "
                "This is a strong ionospheric scintillation indicator (Step 7 triggered)."
            )
        elif worst == "STRONG":
            out["answer"] = "Yes — scintillation detected at HIGH confidence."
            parts = []
            if not epoch_health_df.empty:
                if "any_adr_severe" in epoch_health_df.columns:
                    n = int(epoch_health_df["any_adr_severe"].sum())
                    if n: parts.append(f"ADR_STD > 0.10 (SEVERE) at {n} epoch(s)")
                if "any_combined_strong" in epoch_health_df.columns:
                    n = int(epoch_health_df["any_combined_strong"].sum())
                    if n: parts.append(f"combined CNo+ADR STRONG at {n} epoch(s)")
                if "any_lock_true" in epoch_health_df.columns:
                    n = int(epoch_health_df["any_lock_true"].sum())
                    if n: parts.append(f"lock loss at {n} epoch(s)")
            out["reason"] = (
                "Strong signal-level evidence (Step 5/6 triggered): "
                + ("; ".join(parts) if parts else "combined_flag=STRONG or adr_flag=SEVERE or lock_flag=True.")
            )
        elif worst == "TRUE":
            out["answer"] = "Yes — scintillation detected at MEDIUM confidence."
            parts = []
            if not epoch_health_df.empty:
                if "any_cno_true" in epoch_health_df.columns:
                    n = int(epoch_health_df["any_cno_true"].sum())
                    if n: parts.append(f"CNo drop ≥ 5 dB at {n} epoch(s)")
                if "any_adr_strong" in epoch_health_df.columns:
                    n = int(epoch_health_df["any_adr_strong"].sum())
                    if n: parts.append(f"ADR_STD > 0.05 at {n} epoch(s)")
                if "any_combined_true" in epoch_health_df.columns:
                    n = int(epoch_health_df["any_combined_true"].sum())
                    if n: parts.append(f"combined CNo+ADR triggered at {n} epoch(s)")
            region_note = " Location is in a scintillation-prone region." if (
                not bestpos_df.empty and "region_flag" in bestpos_df.columns
                and bestpos_df["region_flag"].any()
            ) else ""
            out["reason"] = (
                "Region-gated signal anomaly (Step 3/4/5 triggered): "
                + ("; ".join(parts) if parts else "cno or adr thresholds exceeded.")
                + region_note
            )
        elif worst == "POSSIBLE_INTERFERENCE":
            out["answer"] = "Inconclusive — possible RF interference (not scintillation)."
            out["reason"] = (
                "CNo drop detected but no corroborating phase (ADR) or lock-loss evidence. "
                "freq_flag and rf_flag not yet evaluated — could be interference."
            )
        else:
            out["answer"] = "No — no scintillation detected."
            out["reason"] = (
                "No signal anomalies exceeded the detection thresholds "
                "(cno_flag, adr_flag, lock_flag all NONE/GOOD across all epochs)."
            )

    # ── epoch-level flag counts ───────────────────────────────────────────────
    if not epoch_health_df.empty:
        def _count(col, val):
            return int((epoch_health_df[col].astype(str) == val).sum()) \
                   if col in epoch_health_df.columns else 0

        out["epoch_flags"] = {
            "cno_BAD":          _count("cno_epoch_flag",  "BAD"),
            "cno_WARNING":      _count("cno_epoch_flag",  "WARNING"),
            "adr_BAD":          _count("adr_epoch_flag",  "BAD"),
            "adr_WARNING":      _count("adr_epoch_flag",  "WARNING"),
            "lock_BAD":         _count("lock_epoch_flag", "BAD"),
            "lock_WARNING":     _count("lock_epoch_flag", "WARNING"),
            "high_elev_lock":   int(epoch_health_df["high_elev_lock_flag"].sum())
                                if "high_elev_lock_flag" in epoch_health_df.columns else 0,
        }

        # per-signal severity — any True across all epochs
        # ── per-signal severity — percentage-gated ───────────────────────────
        rates = compute_file_level_rates(epoch_health_df)
        out["file_level_rates"] = {
            k: f"{v*100:.1f}%" if isinstance(v, float) else v
            for k, v in rates.items()
        }
        out["thresholds_used"] = {
            "warn_threshold":   f"{_WARN_THRESHOLD*100:.0f}% of epochs",
            "strong_threshold": f"{_STRONG_THRESHOLD*100:.0f}% of epochs",
        }

        def _any(col):
            return bool(epoch_health_df[col].any()) \
                   if col in epoch_health_df.columns else False

        out["per_signal_flags"] = {
            "any_cno_drop_5dB":    _any("any_cno_true"),
            "any_cno_drop_8dB":    _any("any_combined_strong"),
            "any_adr_early":       bool(epoch_health_df["n_adr_flagged"].gt(0).any())
                                   if "n_adr_flagged" in epoch_health_df.columns else False,
            "any_adr_strong":      _any("any_adr_strong"),
            "any_adr_severe":      _any("any_adr_severe"),
            "any_combined_true":   _any("any_combined_true"),
            "any_combined_strong": _any("any_combined_strong"),
            "any_lock_loss":       _any("any_lock_true"),
        }
    else:
        out["epoch_flags"]      = {}
        out["per_signal_flags"] = {}

    # ── location flags ────────────────────────────────────────────────────────
    if not bestpos_df.empty and "region_flag" in bestpos_df.columns:
        lat_mean = float(bestpos_df["latitude"].mean())
        lon_mean = float(bestpos_df["longitude"].mean())
        zone = ("EQUATORIAL" if abs(lat_mean) <= 20
                else "AURORAL" if 60 <= abs(lat_mean) <= 75
                else "MID-LATITUDE")
        out["location_flags"] = {
            "region_flag":   bool(bestpos_df["region_flag"].any()),
            "time_flag":     bool(bestpos_df["time_flag"].any())
                             if "time_flag" in bestpos_df.columns else False,
            "zone":          zone,
            "mean_latitude":  round(lat_mean, 4),
            "mean_longitude": round(lon_mean, 4),
        }
    else:
        out["location_flags"] = {
            "region_flag": False, "time_flag": False,
            "zone": "UNKNOWN", "mean_latitude": None, "mean_longitude": None,
        }

    out["steps_not_evaluated"] = [
        "freq_flag (Step 8) — requires multi-frequency comparison",
        "rf_flag / AGC (Step 10) — requires ITDETECTSTATUS AGC data",
        "space_weather / KP index (Step 11) — requires external feed",
    ]

    return out
