"""
diagnostic_engine.py — Phase 4: Deterministic Diagnostic Rule Engine

Pipeline position:
  Semantic Events + Metrics → [THIS MODULE] → Diagnostics → Correlation JSON

This module applies expert GNSS diagnostic rules to the evidence collected
by all previous phases. It produces named diagnoses — each with:

  - diagnostic_id   : machine-readable name (e.g. ACTIVE_JAMMING_ATTACK)
  - title           : short human-readable title
  - conclusion      : one-sentence finding
  - confidence      : 0.0–1.0 (computed from evidence strength)
  - severity        : critical / high / medium / low
  - root_cause      : structured root cause chain
  - contributing_factors : list of supporting evidence items
  - recommended_actions  : deterministic recommendations (not LLM-generated)
  - evidence_refs   : which tools and events support this diagnosis
  - rule_id         : the rule that fired (auditable)

ARCHITECTURE PRINCIPLE:
  Diagnostics are the bridge between raw evidence and the LLM explanation.
  The LLM receives NAMED DIAGNOSES — not raw numbers.
  This removes the LLM's need to "discover" problems from data.
  It only has to explain already-identified diagnoses.

RULE DESIGN:
  Each rule is a pure function: (events, metrics, evidence) → Diagnostic | None
  Rules are independent — any combination can fire simultaneously.
  Rules are registered in _DIAGNOSTIC_RULES list and run in order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable

from src.semantic_event_engine import Thresholds


# ═══════════════════════════════════════════════════════════════════
# DIAGNOSTIC DATA STRUCTURE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Diagnostic:
    diagnostic_id: str
    title: str
    conclusion: str
    confidence: float           # 0.0 – 1.0
    severity: str               # critical / high / medium / low
    root_cause: str             # one-line root cause statement
    contributing_factors: list[str]
    recommended_actions: list[str]
    evidence_refs: list[str]
    rule_id: str
    metrics_snapshot: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "diagnostic_id":        self.diagnostic_id,
            "title":                self.title,
            "conclusion":           self.conclusion,
            "confidence":           round(self.confidence, 2),
            "severity":             self.severity,
            "root_cause":           self.root_cause,
            "contributing_factors": self.contributing_factors,
            "recommended_actions":  self.recommended_actions,
            "evidence_refs":        self.evidence_refs,
            "rule_id":              self.rule_id,
            "metrics_snapshot":     self.metrics_snapshot,
        }


# ═══════════════════════════════════════════════════════════════════
# HELPER — event lookup
# ═══════════════════════════════════════════════════════════════════

def _has_event(events: list[dict], event_type: str) -> bool:
    return any(e.get("event") == event_type for e in events)


def _get_event(events: list[dict], event_type: str) -> Optional[dict]:
    return next((e for e in events if e.get("event") == event_type), None)


def _events_of_category(events: list[dict], category: str) -> list[dict]:
    return [e for e in events if e.get("category") == category]


def _max_confidence(events: list[dict], event_types: list[str]) -> float:
    return max(
        (e.get("confidence", 0) for e in events if e.get("event") in event_types),
        default=0.0,
    )


# ═══════════════════════════════════════════════════════════════════
# DIAGNOSTIC RULES
# Each rule: (events, metrics, raw_evidence) → Optional[Diagnostic]
# Return None if the rule does not fire.
# ═══════════════════════════════════════════════════════════════════

def _rule_active_jamming(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: Active jamming attack identified.
    Fires when: jamming confirmed by firmware (RXSTATUS bit 15).
    Confidence boosted by corroborating C/No degradation and satellite loss.
    """
    if not _has_event(events, "JAMMING_DETECTED"):
        return None

    jam_ev    = _get_event(events, "JAMMING_DETECTED")
    cn0_ev    = _get_event(events, "CRITICALLY_LOW_SIGNAL_QUALITY") \
                or _get_event(events, "DEGRADED_SIGNAL_QUALITY")
    compound  = _get_event(events, "COMPOUND_INTERFERENCE_SIGNATURE")
    corrobor  = _get_event(events, "INTERFERENCE_CORROBORATED")
    sat_ev    = _get_event(events, "SATELLITE_DROP_EVENT") \
                or _get_event(events, "INSUFFICIENT_SATELLITES_FOR_RTK")

    # Base confidence from firmware bit
    confidence = 1.0   # Firmware-confirmed — always 1.0

    factors = [
        f"RXSTATUS bit 15 set in {jam_ev.get('count', '?')} records — firmware-confirmed jamming"
    ]
    refs = ["rxstatus_analyzer", "RXSTATUS.bit15"]

    if cn0_ev:
        avg_cn0 = cn0_ev.get("metrics", {}).get("avg_cn0") or metrics.get("avg_cn0")
        if avg_cn0:
            factors.append(f"C/No degraded to {avg_cn0:.1f} dB-Hz (threshold: {Thresholds.CN0_WARNING} dB-Hz)")
            refs.append("cn0_analyzer")

    if sat_ev:
        min_sats = sat_ev.get("metrics", {}).get("min_satellites") or metrics.get("min_num_svs")
        if min_sats:
            factors.append(f"Satellite count dropped to minimum {min_sats} (RTK requires ≥{Thresholds.SAT_MIN_RTK})")
            refs.append("bestpos_analyzer")

    if compound:
        factors.append("Multi-source corroboration: RXSTATUS + C/No + satellite loss all consistent with jamming")
        refs.append("semantic_event_engine.compound_correlation")

    rf_ev = _get_event(events, "RF_INTERFERENCE_DETECTED")
    if rf_ev:
        max_pwr = rf_ev.get("metrics", {}).get("max_power_dbm")
        freq    = rf_ev.get("metrics", {}).get("center_freq_mhz")
        detail  = "ITDETECTSTATUS spectrum analysis confirms RF interference"
        if max_pwr: detail += f" (peak {max_pwr:.1f} dBm)"
        if freq:    detail += f" at {freq:.2f} MHz"
        factors.append(detail)
        refs.append("itdetect_analyzer")

    actions = [
        "Check surroundings for transmitting devices near the antenna",
        "Move antenna to higher elevation or different location to escape interference",
        "Enable HDR (High Dynamic Range) mode if receiver supports it",
        "Review ITDETECTSTATUS logs for frequency and power characteristics of the jammer",
        "If persistent, consult spectrum management authority",
    ]

    return Diagnostic(
        diagnostic_id        = "ACTIVE_JAMMING_ATTACK",
        title                = "Active Jamming Attack Detected",
        conclusion           = f"The receiver is experiencing active RF jamming confirmed by firmware in {jam_ev.get('count', '?')} records.",
        confidence           = confidence,
        severity             = "critical",
        root_cause           = "External RF jamming signal overwhelming GNSS signal bands",
        contributing_factors = factors,
        recommended_actions  = actions,
        evidence_refs        = list(dict.fromkeys(refs)),  # deduplicate, preserve order
        rule_id              = "RULE_JAMMING_001",
        metrics_snapshot     = {
            "jamming_event_count": jam_ev.get("count"),
            "avg_cn0":   metrics.get("avg_cn0"),
            "min_num_svs": metrics.get("min_num_svs"),
        },
    )


def _rule_spoofing_attack(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: GNSS spoofing attack identified.
    Fires when: spoofing confirmed by firmware (RXSTATUS bit 9).
    """
    if not _has_event(events, "SPOOFING_DETECTED"):
        return None

    sp_ev     = _get_event(events, "SPOOFING_DETECTED")
    corrobor  = _get_event(events, "SPOOFING_CORROBORATED")
    cn0_ev    = _get_event(events, "CRITICALLY_LOW_SIGNAL_QUALITY") \
                or _get_event(events, "DEGRADED_SIGNAL_QUALITY")

    confidence = 1.0
    factors = [
        f"RXSTATUS bit 9 set in {sp_ev.get('count', '?')} records — firmware-confirmed spoofing"
    ]
    refs = ["rxstatus_analyzer", "RXSTATUS.bit9"]

    if corrobor:
        avg_cn0 = corrobor.get("metrics", {}).get("avg_cn0")
        if avg_cn0 and avg_cn0 > 45:
            factors.append(
                f"Unusually high C/No ({avg_cn0:.1f} dB-Hz) consistent with artificially strong spoofing signal"
            )
        refs.append("cn0_analyzer")

    return Diagnostic(
        diagnostic_id        = "GNSS_SPOOFING_ATTACK",
        title                = "GNSS Spoofing Attack Detected",
        conclusion           = f"The receiver detected GNSS spoofing signals (firmware-confirmed) in {sp_ev.get('count', '?')} records.",
        confidence           = confidence,
        severity             = "critical",
        root_cause           = "Counterfeit GNSS signals being broadcast to deceive receiver position/time",
        contributing_factors = factors,
        recommended_actions  = [
            "Do not trust reported position until spoofing ceases",
            "Cross-check position with independent sensor (IMU, odometer, visual landmarks)",
            "Enable anti-spoofing features if available (NovAtel OSNMA, authentication)",
            "Log INSPVAX for INS-aided position as backup",
            "Report incident to relevant security authority if in sensitive context",
        ],
        evidence_refs        = list(dict.fromkeys(refs)),
        rule_id              = "RULE_SPOOF_001",
        metrics_snapshot     = {"spoofing_event_count": sp_ev.get("count")},
    )


def _rule_antenna_hardware_fault(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: Antenna hardware fault.
    Fires when: antenna open or shorted circuit detected.
    """
    open_ev    = _get_event(events, "ANTENNA_OPEN_CIRCUIT")
    shorted_ev = _get_event(events, "ANTENNA_SHORT_CIRCUIT")

    if not open_ev and not shorted_ev:
        return None

    fault_type = "open circuit" if open_ev else "short circuit"
    fault_count = (open_ev or shorted_ev).get("count", "?")
    confidence = 1.0
    factors = []
    refs = ["rxstatus_analyzer"]

    if open_ev:
        factors.append(f"RXSTATUS bit 5 set in {open_ev.get('count')} records — antenna open circuit (disconnected or faulty cable)")
        refs.append("RXSTATUS.bit5")
    if shorted_ev:
        factors.append(f"RXSTATUS bit 6 set in {shorted_ev.get('count')} records — antenna short circuit (damaged cable or connector)")
        refs.append("RXSTATUS.bit6")

    cn0_ev = _get_event(events, "CRITICALLY_LOW_SIGNAL_QUALITY") or _get_event(events, "DEGRADED_SIGNAL_QUALITY")
    if cn0_ev:
        avg_cn0 = cn0_ev.get("metrics", {}).get("avg_cn0") or metrics.get("avg_cn0")
        factors.append(f"Signal quality severely degraded (avg C/No {avg_cn0:.1f} dB-Hz) consistent with antenna fault")
        refs.append("cn0_analyzer")

    return Diagnostic(
        diagnostic_id        = "ANTENNA_HARDWARE_FAULT",
        title                = f"Antenna Hardware Fault ({fault_type.title()})",
        conclusion           = f"Antenna {fault_type} detected in {fault_count} records — physical antenna fault confirmed.",
        confidence           = confidence,
        severity             = "high",
        root_cause           = f"Antenna {fault_type} — likely disconnected, damaged cable, or faulty connector",
        contributing_factors = factors,
        recommended_actions  = [
            "Inspect antenna connector and cable for physical damage",
            "Check antenna cable continuity with a multimeter",
            "Verify antenna supply voltage at ANTENNAPOWER log",
            "Replace antenna cable if damaged",
            "Test with a known-good antenna to isolate fault",
        ],
        evidence_refs        = list(dict.fromkeys(refs)),
        rule_id              = "RULE_ANTENNA_001",
        metrics_snapshot     = {
            "antenna_open_count": open_ev.get("count") if open_ev else 0,
            "antenna_shorted_count": shorted_ev.get("count") if shorted_ev else 0,
        },
    )


def _rule_rtk_instability(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: RTK position instability — cannot maintain fixed solution.
    Fires when: RTK float dominant or position degraded to single.
    Root cause is determined by examining correlated factors.
    """
    float_ev  = _get_event(events, "RTK_FLOAT_DOMINANT")
    single_ev = _get_event(events, "POSITION_DEGRADED_TO_SINGLE")
    diagnosed = _get_event(events, "RTK_INSTABILITY_DIAGNOSED")
    corr_loss = _get_event(events, "CORRECTION_LOSS_CAUSED_RTK_FLOAT")
    corr_av   = _get_event(events, "CORRECTION_AVAILABILITY_POOR")
    sat_drop  = _get_event(events, "SATELLITE_DROP_EVENT")
    low_sat   = _get_event(events, "INSUFFICIENT_SATELLITES_FOR_RTK")
    jam_ev    = _get_event(events, "JAMMING_DETECTED")

    if not float_ev and not single_ev and not diagnosed:
        return None

    # Determine confidence and root cause from evidence chain
    factors = []
    refs = ["bestpos_analyzer"]
    root_causes = []

    if float_ev:
        float_pct = float_ev.get("metrics", {}).get("float_pct", "?")
        factors.append(f"RTK float solution in {float_pct}% of records — ambiguities not resolved")

    if single_ev:
        single_pct = single_ev.get("metrics", {}).get("single_pct", "?")
        factors.append(f"Position degraded to single-point in {single_pct}% of records")

    # Root cause diagnosis chain
    if corr_loss:
        max_age = corr_loss.get("metrics", {}).get("max_correction_age", "?")
        root_causes.append(f"correction loss (max age {max_age}s)")
        factors.append(f"Differential corrections lost — max age {max_age}s exceeds {Thresholds.CORR_AGE_LOSS}s threshold")
        refs.append("correction_age_analyzer")

    elif corr_av:
        loss_pct = corr_av.get("metrics", {}).get("correction_loss_pct", "?")
        root_causes.append(f"poor correction availability ({loss_pct}% outage)")
        factors.append(f"Corrections stale/unavailable in {loss_pct}% of records")
        refs.append("correction_age_analyzer")

    if sat_drop:
        drop_count = sat_drop.get("metrics", {}).get("drop_event_count", "?")
        root_causes.append(f"satellite drops ({drop_count} events)")
        factors.append(f"{drop_count} satellite drop event(s) destabilised ambiguity resolution")
        refs.append("bestpos_analyzer.satellite_count")

    if low_sat:
        min_sats = low_sat.get("metrics", {}).get("min_satellites", "?")
        root_causes.append(f"insufficient satellites (min {min_sats})")
        factors.append(f"Satellite count fell to {min_sats} — below RTK minimum of {Thresholds.SAT_MIN_RTK}")
        refs.append("cn0_analyzer")

    if jam_ev:
        root_causes.append("RF jamming")
        factors.append("Active jamming degraded signal quality causing ambiguity loss")
        refs.append("rxstatus_analyzer")

    if not root_causes:
        root_causes = ["unknown — additional log types (TRACKSTAT, ITDETECTSTATUS) needed for full diagnosis"]

    # Confidence: higher when we can identify the root cause
    base_confidence = 0.90
    confidence = min(base_confidence + len(root_causes) * 0.03, 0.98)

    root_cause_str = "RTK instability caused by: " + "; ".join(root_causes)
    severity = "high" if single_ev else "medium"

    actions = [
        "Verify RTK base station is active and transmitting corrections",
        "Check NTRIP/radio link for correction delivery interruptions",
        "Review BESTPOS diff_age field for correction age history",
    ]
    if jam_ev:
        actions.insert(0, "Address jamming interference first — it is the primary cause of RTK instability")
    if sat_drop or low_sat:
        actions.append("Check for obstructions blocking satellite view (buildings, trees, vehicle bodywork)")
    if corr_loss or corr_av:
        actions.append("Check base station connectivity and NTRIP mount point availability")

    return Diagnostic(
        diagnostic_id        = "RTK_POSITION_INSTABILITY",
        title                = "RTK Position Instability",
        conclusion           = f"RTK cannot maintain a fixed solution. {root_cause_str}.",
        confidence           = confidence,
        severity             = severity,
        root_cause           = root_cause_str,
        contributing_factors = factors,
        recommended_actions  = list(dict.fromkeys(actions)),
        evidence_refs        = list(dict.fromkeys(refs)),
        rule_id              = "RULE_RTK_001",
        metrics_snapshot     = {
            "float_pct":           float_ev.get("metrics", {}).get("float_pct") if float_ev else None,
            "single_pct":          single_ev.get("metrics", {}).get("single_pct") if single_ev else None,
            "avg_correction_age":  metrics.get("avg_correction_age"),
            "max_correction_age":  metrics.get("max_correction_age"),
            "min_num_svs":         metrics.get("min_num_svs"),
        },
    )


def _rule_signal_degradation(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: Signal quality degradation.
    Fires when: C/No is critically low or consistently below threshold.
    Distinguishes between interference, multipath, and ionospheric causes.
    """
    critical_ev = _get_event(events, "CRITICALLY_LOW_SIGNAL_QUALITY")
    degraded_ev = _get_event(events, "DEGRADED_SIGNAL_QUALITY")
    scint_ev    = _get_event(events, "IONOSPHERIC_SCINTILLATION_SUSPECTED")
    jam_ev      = _get_event(events, "JAMMING_DETECTED")
    rf_ev       = _get_event(events, "RF_INTERFERENCE_DETECTED")
    compound_ev = _get_event(events, "COMPOUND_INTERFERENCE_SIGNATURE")

    if not critical_ev and not degraded_ev:
        return None

    # If jamming is confirmed, let _rule_active_jamming be the primary diagnosis
    # This rule focuses on non-jamming signal degradation causes
    if jam_ev and compound_ev:
        return None   # Covered by jamming diagnosis

    base_ev = critical_ev or degraded_ev
    avg_cn0 = base_ev.get("metrics", {}).get("avg_cn0") or metrics.get("avg_cn0", 0)
    low_pct = base_ev.get("metrics", {}).get("low_cn0_epoch_pct") or metrics.get("low_cn0_epoch_pct", 0)
    std_dev = evidence.get("cn0_analyzer", {}).get("cn0_std_dev", 0)

    severity = "critical" if critical_ev else "high"
    confidence = 0.90

    factors = [f"Average C/No {avg_cn0:.1f} dB-Hz ({low_pct:.0f}% of epochs below {Thresholds.CN0_WARNING} dB-Hz threshold)"]
    refs = ["cn0_analyzer", "TRACKSTAT"]

    # Determine likely cause
    cause_candidates = []

    if jam_ev or rf_ev:
        cause_candidates.append("RF interference / jamming")
        refs.append("rxstatus_analyzer")

    if scint_ev:
        scint_conf = scint_ev.get("confidence", 0)
        cause_candidates.append(f"ionospheric scintillation (confidence {scint_conf:.0%})")
        factors.append(f"C/No std_dev {std_dev:.1f} dB-Hz indicates amplitude scintillation")
        refs.append("cn0_analyzer.cn0_std_dev")

    if not cause_candidates:
        # Check for multipath indicators (high std_dev without scintillation)
        if std_dev > Thresholds.CN0_MULTIPATH:
            cause_candidates.append("multipath reflections")
            factors.append(f"C/No std_dev {std_dev:.1f} dB-Hz suggests signal reflections (multipath)")
        else:
            cause_candidates.append("environmental obstruction or atmospheric effects")

    root_cause = "Signal degradation from: " + "; ".join(cause_candidates)

    actions = [
        "Inspect antenna placement for nearby obstructions (buildings, vehicles, structures)",
        "Review TRACKSTAT for which satellites/signals are most affected",
        "Check for nearby RF transmitters that may cause interference",
    ]
    if scint_ev:
        actions.append("Monitor over time — ionospheric scintillation is typically temporary")
        actions.append("Consider logging IONUTC for ionospheric conditions")
    if jam_ev or rf_ev:
        actions.append("Review ITDETECTSTATUS for interference frequency and power characteristics")

    return Diagnostic(
        diagnostic_id        = "SIGNAL_QUALITY_DEGRADATION",
        title                = "Signal Quality Degradation",
        conclusion           = f"Signal quality is degraded — avg C/No {avg_cn0:.1f} dB-Hz. {root_cause}.",
        confidence           = confidence,
        severity             = severity,
        root_cause           = root_cause,
        contributing_factors = factors,
        recommended_actions  = actions,
        evidence_refs        = list(dict.fromkeys(refs)),
        rule_id              = "RULE_SIGNAL_001",
        metrics_snapshot     = {
            "avg_cn0":              avg_cn0,
            "low_cn0_epoch_pct":    low_pct,
            "cn0_std_dev":          std_dev,
        },
    )


def _rule_scintillation(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: Ionospheric scintillation affecting signal quality.
    Fires when: C/No std_dev exceeds scintillation threshold without jamming.
    """
    scint_ev = _get_event(events, "IONOSPHERIC_SCINTILLATION_SUSPECTED")
    if not scint_ev:
        return None

    # Don't fire if jamming is the more likely cause
    jam_ev = _get_event(events, "JAMMING_DETECTED")
    if jam_ev:
        return None

    std_dev = scint_ev.get("metrics", {}).get("cn0_std_dev") or \
              evidence.get("cn0_analyzer", {}).get("cn0_std_dev", 0)
    confidence = scint_ev.get("confidence", 0.65)

    factors = [
        f"C/No std_dev {std_dev:.1f} dB-Hz exceeds scintillation threshold ({Thresholds.CN0_SCINTILLATION} dB-Hz)",
        "Rapid amplitude fluctuations consistent with ionospheric signal path disturbances",
    ]

    min_cn0 = evidence.get("cn0_analyzer", {}).get("min_cn0")
    if min_cn0 and min_cn0 < Thresholds.CN0_CRITICAL:
        factors.append(f"Signal fades to {min_cn0:.1f} dB-Hz during worst periods")

    return Diagnostic(
        diagnostic_id        = "IONOSPHERIC_SCINTILLATION",
        title                = "Ionospheric Scintillation Suspected",
        conclusion           = f"C/No variation (std_dev {std_dev:.1f} dB-Hz) is consistent with ionospheric scintillation.",
        confidence           = confidence,
        severity             = "medium",
        root_cause           = "Ionospheric plasma irregularities causing rapid signal amplitude and phase fluctuations",
        contributing_factors = factors,
        recommended_actions  = [
            "Monitor scintillation over time — correlate with local time of day and solar activity",
            "Check Space Weather data for geomagnetic storm activity",
            "Consider dual-frequency receiver to mitigate ionospheric effects",
            "Log IONUTC and RANGE logs if available for deeper analysis",
            "If operating at high latitudes, polar scintillation is more likely",
        ],
        evidence_refs        = ["cn0_analyzer.cn0_std_dev", "TRACKSTAT"],
        rule_id              = "RULE_SCINT_001",
        metrics_snapshot     = {
            "cn0_std_dev":  std_dev,
            "min_cn0":      min_cn0,
            "confidence":   confidence,
        },
    )


def _rule_correction_outage(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: Differential correction service outage or link failure.
    Fires when: correction age is high or corrections are unavailable.
    Not fired if already covered by RTK instability diagnosis.
    """
    corr_outage = _get_event(events, "CORRECTION_OUTAGE_DETECTED")
    corr_avail  = _get_event(events, "CORRECTION_AVAILABILITY_POOR")
    high_age    = _get_event(events, "HIGH_CORRECTION_AGE")

    if not corr_outage and not corr_avail:
        return None

    # Skip if covered by RTK instability — avoid duplicate
    rtk_diag = _get_event(events, "RTK_INSTABILITY_DIAGNOSED")
    corr_rtk  = _get_event(events, "CORRECTION_LOSS_CAUSED_RTK_FLOAT")
    if rtk_diag and corr_rtk:
        return None   # Already captured in RTK diagnosis

    ev = corr_outage or corr_avail
    avg_age  = ev.get("metrics", {}).get("avg_correction_age") or metrics.get("avg_correction_age", 0)
    max_age  = ev.get("metrics", {}).get("max_correction_age") or metrics.get("max_correction_age", 0)
    loss_pct = ev.get("metrics", {}).get("correction_loss_pct") or metrics.get("correction_loss_pct", 0)

    severity = "high" if max_age and max_age > Thresholds.CORR_AGE_LOSS else "medium"
    confidence = 0.93

    return Diagnostic(
        diagnostic_id        = "CORRECTION_SERVICE_OUTAGE",
        title                = "Differential Correction Service Outage",
        conclusion           = f"Differential corrections were unavailable or stale for {loss_pct:.0f}% of the session (max age {max_age:.1f}s).",
        confidence           = confidence,
        severity             = severity,
        root_cause           = "RTK/DGNSS correction link failure — base station unreachable or NTRIP disconnected",
        contributing_factors = [
            f"Average correction age: {avg_age:.1f}s (threshold: {Thresholds.CORR_AGE_WARNING}s)",
            f"Maximum correction age: {max_age:.1f}s (loss threshold: {Thresholds.CORR_AGE_LOSS}s)",
            f"Correction outage affected {loss_pct:.0f}% of records",
        ],
        recommended_actions  = [
            "Verify NTRIP server connectivity and mount point availability",
            "Check radio link signal strength (if using radio corrections)",
            "Review PORTSTATS log for communication errors",
            "Verify base station is logging and transmitting in the correct format (RTCM3, CMR+)",
            "Consider fallback to SBAS (satellite-based augmentation) when terrestrial corrections fail",
        ],
        evidence_refs        = ["correction_age_analyzer", "bestpos_analyzer.correction_age"],
        rule_id              = "RULE_CORR_001",
        metrics_snapshot     = {
            "avg_correction_age":  avg_age,
            "max_correction_age":  max_age,
            "correction_loss_pct": loss_pct,
        },
    )


def _rule_ins_alignment_failure(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: INS alignment or convergence failure.
    Fires when: INS solution is in a bad/aligning state.
    """
    ins_ev = _get_event(events, "INS_NOT_CONVERGED")
    int_ev = _get_event(events, "INS_INTERMITTENT_ISSUES")

    if not ins_ev and not int_ev:
        return None

    ev = ins_ev or int_ev
    dominant = ev.get("metrics", {}).get("dominant_status", "UNKNOWN")
    bad_pct  = ev.get("metrics", {}).get("bad_status_pct", 0)

    is_aligning = dominant in {"INS_ALIGNING", "INS_INACTIVE"}
    severity = "high" if ins_ev else "medium"
    confidence = 0.92 if ins_ev else 0.78

    cause = "INS has not completed alignment" if is_aligning else "INS solution quality degraded"
    factors = [
        f"Dominant INS status: {dominant} — {cause}",
        f"INS in degraded state for {bad_pct:.0f}% of records",
    ]

    actions = [
        "Allow vehicle to perform dynamic manoeuvres (figure-8, S-curves) to aid IMU alignment",
        "Ensure GNSS signal quality is sufficient during alignment phase",
        "Check IMU mounting parameters (SETINSTRANSLATION, SETINSROTATION)",
        "Review INSPVAX for detailed INS status flags",
        "Verify IMU is not in error state (check RXSTATUS IMU fault bits)",
    ]

    if dominant == "INS_HIGHVARIANCE":
        factors.append("High variance indicates poor observability — vehicle may be stationary or on straight road")
        actions.insert(0, "Introduce angular motion (turning) to improve IMU observability")

    return Diagnostic(
        diagnostic_id        = "INS_ALIGNMENT_FAILURE",
        title                = "INS Alignment / Convergence Issue",
        conclusion           = f"INS solution is in '{dominant}' state for {bad_pct:.0f}% of records — {cause}.",
        confidence           = confidence,
        severity             = severity,
        root_cause           = cause,
        contributing_factors = factors,
        recommended_actions  = actions,
        evidence_refs        = ["ins_analyzer", "INSPVA"],
        rule_id              = "RULE_INS_001",
        metrics_snapshot     = {"dominant_ins_status": dominant, "bad_status_pct": bad_pct},
    )


def _rule_data_completeness(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: Data completeness issue — gaps in the log.
    Fires when: significant data gaps detected.
    """
    gap_ev = _get_event(events, "DATA_GAPS_DETECTED")
    if not gap_ev or gap_ev.get("severity") == "info":
        return None

    gap_count   = gap_ev.get("metrics", {}).get("gap_count", 0) or metrics.get("gap_count", 0)
    missing_sec = gap_ev.get("metrics", {}).get("total_missing_seconds", 0)
    continuity  = gap_ev.get("metrics", {}).get("data_continuity_pct", 100)

    severity = "high" if gap_count >= Thresholds.GAP_CRITICAL else "medium"
    confidence = 1.0  # Deterministic — gap count is a fact

    factors = [
        f"{gap_count} data gap(s) totalling {missing_sec:.1f}s of missing data",
        f"Data continuity: {continuity:.1f}% (below {Thresholds.CONTINUITY_WARNING}% threshold)"
        if continuity < Thresholds.CONTINUITY_WARNING
        else f"Data continuity: {continuity:.1f}%",
    ]

    return Diagnostic(
        diagnostic_id        = "DATA_COMPLETENESS_ISSUE",
        title                = "Data Completeness Issue",
        conclusion           = f"{gap_count} data gap(s) detected — {missing_sec:.1f}s of data missing ({100-continuity:.1f}% data loss).",
        confidence           = confidence,
        severity             = severity,
        root_cause           = "Log file has missing records — power interruption, storage failure, or logging configuration issue",
        contributing_factors = factors,
        recommended_actions  = [
            "Verify logging configuration is set to correct rates and log types",
            "Check receiver storage availability (FILESYSTEMCAPACITY log)",
            "Verify power supply is stable during logging session",
            "Review LOGLIST to confirm all required logs are enabled",
        ],
        evidence_refs        = ["data_gap_analyzer"],
        rule_id              = "RULE_DATA_001",
        metrics_snapshot     = {
            "gap_count":             gap_count,
            "total_missing_seconds": missing_sec,
            "data_continuity_pct":   continuity,
        },
    )


def _rule_healthy_operation(
    events: list[dict], metrics: dict, evidence: dict
) -> Optional[Diagnostic]:
    """
    RULE: System operating nominally.
    Fires only when NO critical or high-severity events are present.
    This prevents the LLM from inventing problems when there are none.
    """
    critical_or_high = [
        e for e in events
        if e.get("severity") in ("critical", "high")
        and e.get("event") not in ("FILE_TIME_COVERAGE",)
    ]
    if critical_or_high:
        return None

    # Need at least some tools to have run successfully
    ok_tools = [t for t, v in evidence.items() if v.get("status") == "ok"]
    if not ok_tools:
        return None

    dominant_fix = metrics.get("dominant_fix_type", "")
    avg_cn0 = metrics.get("avg_cn0")
    duration = metrics.get("duration_minutes")

    summary_parts = []
    if dominant_fix:
        summary_parts.append(f"dominant fix type: {dominant_fix}")
    if avg_cn0:
        summary_parts.append(f"avg C/No: {avg_cn0:.1f} dB-Hz")
    if duration:
        summary_parts.append(f"session duration: {duration:.1f} min")

    summary = "; ".join(summary_parts) if summary_parts else "all monitored parameters within normal range"

    return Diagnostic(
        diagnostic_id        = "NOMINAL_OPERATION",
        title                = "System Operating Normally",
        conclusion           = f"No significant anomalies detected. {summary.capitalize()}.",
        confidence           = 0.85,
        severity             = "low",
        root_cause           = "N/A — no anomalies detected",
        contributing_factors = [
            "No jamming or spoofing events",
            "No critical signal quality degradation",
            "No significant position solution issues",
        ],
        recommended_actions  = ["Continue nominal operation", "Maintain regular log monitoring"],
        evidence_refs        = ok_tools,
        rule_id              = "RULE_NOMINAL_001",
        metrics_snapshot     = {
            "dominant_fix_type": dominant_fix,
            "avg_cn0":           avg_cn0,
            "duration_minutes":  duration,
        },
    )


# ═══════════════════════════════════════════════════════════════════
# RULE REGISTRY
# Ordered by importance — higher priority rules first.
# ═══════════════════════════════════════════════════════════════════

_DIAGNOSTIC_RULES: list[Callable] = [
    _rule_active_jamming,
    _rule_spoofing_attack,
    _rule_antenna_hardware_fault,
    _rule_rtk_instability,
    _rule_signal_degradation,
    _rule_scintillation,
    _rule_correction_outage,
    _rule_ins_alignment_failure,
    _rule_data_completeness,
    _rule_healthy_operation,     # Must be last — fires only if nothing else fires
]


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_diagnostics(
    events: list[dict],
    metrics: dict,
    evidence: dict,
) -> list[dict]:
    """
    Run all diagnostic rules against the current evidence set.

    Args:
        events:   Semantic events from semantic_event_engine.generate_semantic_events()
        metrics:  Flat metrics dict from correlation_orchestrator._extract_metrics()
        evidence: Raw tool results dict from correlation_orchestrator.execute_plan()

    Returns:
        List of Diagnostic dicts, sorted by severity (critical first).
        Empty list if no evidence is available.
    """
    if not evidence:
        return []

    diagnostics: list[Diagnostic] = []

    for rule_fn in _DIAGNOSTIC_RULES:
        try:
            result = rule_fn(events, metrics, evidence)
            if result is not None:
                diagnostics.append(result)
        except Exception as e:
            print(f"[DIAGNOSTIC] Rule {rule_fn.__name__} error: {e}")

    # Sort by severity
    _SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    diagnostics.sort(key=lambda d: _SEV_ORDER.get(d.severity, 99))

    print(f"[DIAGNOSTIC] {len(diagnostics)} diagnostic(s) from {len(_DIAGNOSTIC_RULES)} rules")
    for d in diagnostics:
        print(f"  [{d.severity.upper():8s}] {d.diagnostic_id} (conf={d.confidence:.2f}) — {d.rule_id}")

    return [d.to_dict() for d in diagnostics]
