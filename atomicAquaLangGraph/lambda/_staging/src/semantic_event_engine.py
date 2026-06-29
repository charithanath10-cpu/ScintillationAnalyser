"""
semantic_event_engine.py — Phase 3: Semantic Event Generation

Pipeline position:
  Tool Outputs (raw evidence) → [THIS MODULE] → Semantic Events → Correlation JSON

This module translates raw structured metrics from tools into rich semantic
events that carry:
  - event_type    : machine-readable event name (e.g. JAMMING_DETECTED)
  - category      : domain category (interference / positioning / signal / etc.)
  - severity      : critical / high / medium / low / info
  - confidence    : 0.0 – 1.0 (how certain we are this is a real event)
  - description   : one-line human readable summary
  - evidence_refs : which tools and fields support this event
  - timestamp_first / timestamp_last : UTC timestamps if available
  - metrics       : relevant numeric values for this event

ARCHITECTURE PRINCIPLE:
  Events are FACTS derived from deterministic rules.
  The LLM only receives these events — it never identifies them.
  Every event has a traceable source.

GNSS EXPERT RULES:
  All thresholds are based on NovAtel OEM7 field experience and GNSS standards:
  - C/No < 35 dB-Hz     → signal degradation warning
  - C/No < 30 dB-Hz     → critical signal degradation
  - C/No std_dev > 5    → possible scintillation
  - Correction age > 10s → correction latency warning
  - Correction age > 30s → correction loss
  - Satellite drop > 30% → significant satellite loss
  - RTK float > 30%     → RTK instability
  - Position invalid > 0 → position outage
  - Jamming bit set      → jamming (confirmed by receiver firmware)
  - Spoofing bit set     → spoofing (confirmed by receiver firmware)
  - Antenna open/short   → hardware fault
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any


# ═══════════════════════════════════════════════════════════════════
# EVENT DATA STRUCTURE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SemanticEvent:
    event_type: str
    category: str
    severity: str          # critical / high / medium / low / info
    confidence: float      # 0.0 – 1.0
    description: str
    evidence_refs: list[str]
    metrics: dict = field(default_factory=dict)
    timestamp_first: str = ""
    timestamp_last: str = ""
    count: int = 0

    def to_dict(self) -> dict:
        d = {
            "event":          self.event_type,
            "category":       self.category,
            "severity":       self.severity,
            "confidence":     round(self.confidence, 2),
            "description":    self.description,
            "evidence_refs":  self.evidence_refs,
            "metrics":        self.metrics,
        }
        if self.count:
            d["count"] = self.count
        if self.timestamp_first:
            d["timestamp_first"] = self.timestamp_first
        if self.timestamp_last:
            d["timestamp_last"] = self.timestamp_last
        return d


# ═══════════════════════════════════════════════════════════════════
# GNSS THRESHOLDS (expert-defined, not LLM-inferred)
# ═══════════════════════════════════════════════════════════════════

class Thresholds:
    # Signal quality
    CN0_WARNING         = 35.0   # dB-Hz — industry standard warning level
    CN0_CRITICAL        = 30.0   # dB-Hz — critical degradation
    CN0_SCINTILLATION   = 5.0    # dB-Hz std_dev — scintillation indicator
    CN0_MULTIPATH       = 4.0    # dB-Hz std_dev range — multipath indicator
    CN0_EPOCH_PCT       = 20.0   # % of epochs below threshold to call an event

    # Corrections
    CORR_AGE_WARNING    = 10.0   # seconds — RTCM/RTK correction latency warning
    CORR_AGE_LOSS       = 30.0   # seconds — correction likely lost
    CORR_LOSS_PCT       = 10.0   # % of records with high age to call outage

    # Satellite tracking
    SAT_DROP_PCT        = 0.30   # 30% drop in satellite count = significant
    SAT_MIN_RTK         = 5      # Minimum satellites for RTK operation
    SAT_MIN_SINGLE      = 4      # Minimum for single-point position

    # Positioning
    RTK_FLOAT_PCT       = 30.0   # % float records = RTK instability
    RTK_SINGLE_PCT      = 20.0   # % single records = position degradation
    HTG_STD_WARNING     = 0.10   # m — vertical accuracy warning (RTK context)
    HTG_STD_DEGRADED    = 0.50   # m — degraded vertical accuracy

    # INS
    INS_BAD_STATUSES    = {"INS_INACTIVE", "INS_ALIGNING", "INS_BAD",
                           "INS_HIGHVARIANCE"}

    # Data integrity
    GAP_WARNING         = 1      # gaps = warning
    GAP_CRITICAL        = 5      # gaps = critical
    CONTINUITY_WARNING  = 95.0   # % below this = data continuity concern


# ═══════════════════════════════════════════════════════════════════
# EVENT GENERATORS
# One function per evidence domain — each returns list[SemanticEvent]
# ═══════════════════════════════════════════════════════════════════

def _events_from_rxstatus(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    # ── Jamming ───────────────────────────────────────────────────────
    if result.get("jamming_detected"):
        jam_evs = result.get("jamming_events", [])
        t_first = jam_evs[0].get("utc_time", "") if jam_evs else ""
        t_last  = jam_evs[-1].get("utc_time", "") if jam_evs else ""
        events.append(SemanticEvent(
            event_type      = "JAMMING_DETECTED",
            category        = "interference",
            severity        = "critical",
            confidence      = 1.0,   # Firmware-confirmed
            description     = f"Receiver firmware confirmed jamming in {result.get('jamming_event_count', 0)} RXSTATUS records",
            evidence_refs   = ["rxstatus_analyzer.jamming_events", "RXSTATUS.bit15"],
            metrics         = {"jamming_event_count": result.get("jamming_event_count", 0)},
            timestamp_first = t_first,
            timestamp_last  = t_last,
            count           = result.get("jamming_event_count", 0),
        ))

    # ── Spoofing ──────────────────────────────────────────────────────
    if result.get("spoofing_detected"):
        sp_evs = result.get("spoofing_events", [])
        t_first = sp_evs[0].get("utc_time", "") if sp_evs else ""
        t_last  = sp_evs[-1].get("utc_time", "") if sp_evs else ""
        events.append(SemanticEvent(
            event_type      = "SPOOFING_DETECTED",
            category        = "interference",
            severity        = "critical",
            confidence      = 1.0,
            description     = f"Receiver firmware confirmed spoofing in {result.get('spoofing_event_count', 0)} RXSTATUS records",
            evidence_refs   = ["rxstatus_analyzer.spoofing_events", "RXSTATUS.bit9"],
            metrics         = {"spoofing_event_count": result.get("spoofing_event_count", 0)},
            timestamp_first = t_first,
            timestamp_last  = t_last,
            count           = result.get("spoofing_event_count", 0),
        ))

    # ── Antenna faults ────────────────────────────────────────────────
    if result.get("antenna_open_count", 0) > 0:
        events.append(SemanticEvent(
            event_type    = "ANTENNA_OPEN_CIRCUIT",
            category      = "receiver_status",
            severity      = "high",
            confidence    = 1.0,
            description   = f"Antenna open-circuit detected in {result['antenna_open_count']} records (RXSTATUS bit 5)",
            evidence_refs = ["rxstatus_analyzer.antenna_open_count", "RXSTATUS.bit5"],
            metrics       = {"antenna_open_count": result["antenna_open_count"]},
            count         = result["antenna_open_count"],
        ))

    if result.get("antenna_shorted_count", 0) > 0:
        events.append(SemanticEvent(
            event_type    = "ANTENNA_SHORT_CIRCUIT",
            category      = "receiver_status",
            severity      = "high",
            confidence    = 1.0,
            description   = f"Antenna short-circuit detected in {result['antenna_shorted_count']} records (RXSTATUS bit 6)",
            evidence_refs = ["rxstatus_analyzer.antenna_shorted_count", "RXSTATUS.bit6"],
            metrics       = {"antenna_shorted_count": result["antenna_shorted_count"]},
            count         = result["antenna_shorted_count"],
        ))

    # ── Position invalid ──────────────────────────────────────────────
    if result.get("position_invalid_count", 0) > 0:
        events.append(SemanticEvent(
            event_type    = "POSITION_SOLUTION_INVALID",
            category      = "positioning",
            severity      = "high",
            confidence    = 1.0,
            description   = f"Position solution flagged invalid in {result['position_invalid_count']} records (RXSTATUS bit 19)",
            evidence_refs = ["rxstatus_analyzer.position_invalid_count", "RXSTATUS.bit19"],
            metrics       = {"position_invalid_count": result["position_invalid_count"]},
            count         = result["position_invalid_count"],
        ))

    # ── Tracking degraded ─────────────────────────────────────────────
    if result.get("tracking_degraded_count", 0) > 0:
        events.append(SemanticEvent(
            event_type    = "TRACKING_DEGRADED",
            category      = "satellite_tracking",
            severity      = "medium",
            confidence    = 1.0,
            description   = f"Satellite tracking degraded in {result['tracking_degraded_count']} records (RXSTATUS AUX4)",
            evidence_refs = ["rxstatus_analyzer.tracking_degraded_count", "RXSTATUS.aux4"],
            metrics       = {"tracking_degraded_count": result["tracking_degraded_count"]},
            count         = result["tracking_degraded_count"],
        ))

    return events


def _events_from_itdetect(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    if result.get("has_interference"):
        total = result.get("total_interference_events", 0)
        spectrum_count = result.get("spectrum_analysis_count", 0)
        rf_stats = result.get("rf_power_stats", {})
        max_pwr = rf_stats.get("max_dbm")

        # Severity based on power level
        if max_pwr is not None and max_pwr > -60:
            severity = "critical"
            confidence = 0.95
        elif max_pwr is not None and max_pwr > -80:
            severity = "high"
            confidence = 0.88
        else:
            severity = "high"
            confidence = 0.80

        desc = f"RF interference detected: {spectrum_count} spectrum analysis events"
        if max_pwr is not None:
            desc += f", peak power {max_pwr:.1f} dBm"

        # Check for GPS L1 band targeting
        first_event = result.get("interference_events", [{}])[0] if result.get("interference_events") else {}
        center_freq = first_event.get("center_freq_mhz")
        if center_freq and 1574.0 < center_freq < 1577.0:
            desc += " — targeting GPS L1 band (1575.42 MHz)"
            confidence = min(confidence + 0.05, 1.0)

        interference_events_raw = result.get("interference_events", [])
        t_first = interference_events_raw[0].get("utc_time", "") if interference_events_raw else ""
        t_last  = interference_events_raw[-1].get("utc_time", "") if interference_events_raw else ""

        events.append(SemanticEvent(
            event_type      = "RF_INTERFERENCE_DETECTED",
            category        = "interference",
            severity        = severity,
            confidence      = confidence,
            description     = desc,
            evidence_refs   = ["itdetect_analyzer.interference_events", "ITDETECTSTATUS"],
            metrics         = {
                "total_events":    total,
                "spectrum_count":  spectrum_count,
                "max_power_dbm":   max_pwr,
                "center_freq_mhz": center_freq,
            },
            timestamp_first = t_first,
            timestamp_last  = t_last,
            count           = total,
        ))

    return events


def _events_from_cn0(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    avg_cn0     = result.get("avg_cn0", 99.0)
    min_cn0     = result.get("min_cn0", 99.0)
    std_dev     = result.get("cn0_std_dev", 0.0)
    low_pct     = result.get("low_cn0_epoch_pct", 0.0)
    avg_sats    = result.get("avg_satellites_tracked", 0)
    min_sats    = result.get("min_satellites_tracked", 0)

    # ── Critical signal degradation ───────────────────────────────────
    if avg_cn0 < Thresholds.CN0_CRITICAL:
        events.append(SemanticEvent(
            event_type    = "CRITICALLY_LOW_SIGNAL_QUALITY",
            category      = "signal_quality",
            severity      = "critical",
            confidence    = 0.98,
            description   = f"Average C/No {avg_cn0:.1f} dB-Hz is critically below {Thresholds.CN0_CRITICAL} dB-Hz threshold",
            evidence_refs = ["cn0_analyzer.avg_cn0", "TRACKSTAT"],
            metrics       = {"avg_cn0": avg_cn0, "min_cn0": min_cn0, "threshold": Thresholds.CN0_CRITICAL},
        ))

    # ── Signal quality warning ────────────────────────────────────────
    elif avg_cn0 < Thresholds.CN0_WARNING and low_pct >= Thresholds.CN0_EPOCH_PCT:
        confidence = 0.85 + min((Thresholds.CN0_WARNING - avg_cn0) / 10, 0.10)
        events.append(SemanticEvent(
            event_type    = "DEGRADED_SIGNAL_QUALITY",
            category      = "signal_quality",
            severity      = "high",
            confidence    = round(confidence, 2),
            description   = f"Signal quality degraded: avg C/No {avg_cn0:.1f} dB-Hz, {low_pct:.0f}% of epochs below {Thresholds.CN0_WARNING} dB-Hz",
            evidence_refs = ["cn0_analyzer.avg_cn0", "cn0_analyzer.low_cn0_epoch_pct", "TRACKSTAT"],
            metrics       = {"avg_cn0": avg_cn0, "low_cn0_epoch_pct": low_pct, "threshold": Thresholds.CN0_WARNING},
        ))

    # ── Scintillation ─────────────────────────────────────────────────
    if std_dev >= Thresholds.CN0_SCINTILLATION:
        events.append(SemanticEvent(
            event_type    = "IONOSPHERIC_SCINTILLATION_SUSPECTED",
            category      = "signal_quality",
            severity      = "medium",
            confidence    = min(0.60 + (std_dev - Thresholds.CN0_SCINTILLATION) * 0.05, 0.90),
            description   = f"C/No std_dev {std_dev:.1f} dB-Hz exceeds scintillation threshold ({Thresholds.CN0_SCINTILLATION} dB-Hz) — possible ionospheric scintillation",
            evidence_refs = ["cn0_analyzer.cn0_std_dev", "TRACKSTAT"],
            metrics       = {"cn0_std_dev": std_dev, "threshold": Thresholds.CN0_SCINTILLATION},
        ))

    # ── Satellite loss ────────────────────────────────────────────────
    if avg_sats > 0 and min_sats < Thresholds.SAT_MIN_RTK:
        events.append(SemanticEvent(
            event_type    = "INSUFFICIENT_SATELLITES_FOR_RTK",
            category      = "satellite_tracking",
            severity      = "high",
            confidence    = 0.92,
            description   = f"Minimum satellites tracked ({min_sats}) fell below RTK minimum ({Thresholds.SAT_MIN_RTK})",
            evidence_refs = ["cn0_analyzer.min_satellites_tracked", "TRACKSTAT"],
            metrics       = {"min_satellites": min_sats, "avg_satellites": avg_sats, "rtk_minimum": Thresholds.SAT_MIN_RTK},
        ))

    return events


def _events_from_bestpos(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    fix_dist    = result.get("fix_type_distribution", {})
    total_recs  = result.get("total_records", 1) or 1
    corr_age    = result.get("correction_age", {})
    sat_count   = result.get("satellite_count", {})
    pos_acc     = result.get("position_accuracy", {})

    # ── RTK float dominant ────────────────────────────────────────────
    float_types = {"NARROW_FLOAT", "INS_RTKFLOAT", "WIDE_FLOAT", "FLOAT_CONV"}
    fixed_types = {"NARROW_INT", "INS_RTKFIXED", "WIDE_INT"}
    single_types = {"SINGLE", "INS_PSRDIFF", "PSRDIFF"}

    float_count  = sum(fix_dist.get(k, 0) for k in float_types)
    fixed_count  = sum(fix_dist.get(k, 0) for k in fixed_types)
    single_count = sum(fix_dist.get(k, 0) for k in single_types)

    float_pct  = float_count  / total_recs * 100
    single_pct = single_count / total_recs * 100
    fixed_pct  = fixed_count  / total_recs * 100

    if float_pct >= Thresholds.RTK_FLOAT_PCT:
        events.append(SemanticEvent(
            event_type    = "RTK_FLOAT_DOMINANT",
            category      = "positioning",
            severity      = "medium" if float_pct < 60 else "high",
            confidence    = 0.95,
            description   = f"RTK float solution dominant: {float_pct:.0f}% of records — RTK fix not achieved or unstable",
            evidence_refs = ["bestpos_analyzer.fix_type_distribution", "BESTPOS"],
            metrics       = {
                "float_pct": round(float_pct, 1),
                "fixed_pct": round(fixed_pct, 1),
                "single_pct": round(single_pct, 1),
                "float_count": float_count,
            },
        ))

    if single_pct >= Thresholds.RTK_SINGLE_PCT:
        events.append(SemanticEvent(
            event_type    = "POSITION_DEGRADED_TO_SINGLE",
            category      = "positioning",
            severity      = "high",
            confidence    = 0.97,
            description   = f"Position degraded to single-point in {single_pct:.0f}% of records — RTK/DGNSS unavailable",
            evidence_refs = ["bestpos_analyzer.fix_type_distribution", "BESTPOS"],
            metrics       = {"single_pct": round(single_pct, 1), "single_count": single_count},
        ))

    # ── High correction age ───────────────────────────────────────────
    avg_age = corr_age.get("avg")
    max_age = corr_age.get("max")
    high_age_count = corr_age.get("high_age_count", 0)

    if avg_age is not None and avg_age > Thresholds.CORR_AGE_WARNING:
        events.append(SemanticEvent(
            event_type    = "HIGH_CORRECTION_AGE",
            category      = "corrections",
            severity      = "medium" if avg_age < Thresholds.CORR_AGE_LOSS else "high",
            confidence    = 0.90,
            description   = f"Average correction age {avg_age:.1f}s exceeds {Thresholds.CORR_AGE_WARNING}s threshold — corrections may be stale",
            evidence_refs = ["bestpos_analyzer.correction_age", "BESTPOS.diff_age"],
            metrics       = {
                "avg_correction_age": avg_age,
                "max_correction_age": max_age,
                "high_age_count": high_age_count,
                "warning_threshold": Thresholds.CORR_AGE_WARNING,
            },
        ))

    if max_age is not None and max_age > Thresholds.CORR_AGE_LOSS:
        events.append(SemanticEvent(
            event_type    = "CORRECTION_OUTAGE_DETECTED",
            category      = "corrections",
            severity      = "high",
            confidence    = 0.93,
            description   = f"Correction age reached {max_age:.1f}s — corrections were likely lost for a period",
            evidence_refs = ["bestpos_analyzer.correction_age.max", "BESTPOS.diff_age"],
            metrics       = {"max_correction_age": max_age, "loss_threshold": Thresholds.CORR_AGE_LOSS},
        ))

    # ── Satellite drops ───────────────────────────────────────────────
    min_sats = sat_count.get("min")
    avg_sats = sat_count.get("avg")
    drop_events = sat_count.get("drop_events", [])

    if drop_events:
        max_drop_pct = max(d.get("drop_pct", 0) for d in drop_events)
        events.append(SemanticEvent(
            event_type    = "SATELLITE_DROP_EVENT",
            category      = "satellite_tracking",
            severity      = "high" if max_drop_pct > 50 else "medium",
            confidence    = 0.88,
            description   = f"{len(drop_events)} satellite drop event(s) detected, largest drop: {max_drop_pct:.0f}%",
            evidence_refs = ["bestpos_analyzer.satellite_count.drop_events", "BESTPOS.num_svs"],
            metrics       = {
                "drop_event_count": len(drop_events),
                "max_drop_pct": max_drop_pct,
                "min_satellites": min_sats,
                "avg_satellites": avg_sats,
            },
            count = len(drop_events),
        ))

    # ── Poor vertical accuracy ────────────────────────────────────────
    hgt_std_avg = pos_acc.get("hgt_std_avg")
    if hgt_std_avg is not None and hgt_std_avg > Thresholds.HTG_STD_DEGRADED:
        events.append(SemanticEvent(
            event_type    = "POOR_VERTICAL_ACCURACY",
            category      = "positioning",
            severity      = "medium",
            confidence    = 0.85,
            description   = f"Average vertical accuracy {hgt_std_avg:.3f}m exceeds {Thresholds.HTG_STD_DEGRADED}m threshold",
            evidence_refs = ["bestpos_analyzer.position_accuracy.hgt_std_avg", "BESTPOS"],
            metrics       = {"hgt_std_avg": hgt_std_avg, "threshold": Thresholds.HTG_STD_DEGRADED},
        ))

    return events


def _events_from_correction_age(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    avg_age     = result.get("avg_correction_age", 0)
    max_age     = result.get("max_correction_age", 0)
    loss_pct    = result.get("correction_loss_pct", 0)
    high_count  = result.get("high_age_event_count", 0)
    high_events = result.get("high_age_events", [])

    t_first = high_events[0].get("utc_time", "") if high_events else ""
    t_last  = high_events[-1].get("utc_time", "") if high_events else ""

    if loss_pct >= Thresholds.CORR_LOSS_PCT:
        severity = "critical" if loss_pct > 50 else "high"
        events.append(SemanticEvent(
            event_type      = "CORRECTION_AVAILABILITY_POOR",
            category        = "corrections",
            severity        = severity,
            confidence      = 0.92,
            description     = f"Corrections unavailable/stale in {loss_pct:.0f}% of records (avg age: {avg_age:.1f}s, max: {max_age:.1f}s)",
            evidence_refs   = ["correction_age_analyzer", "BESTPOS.diff_age"],
            metrics         = {
                "avg_correction_age": avg_age,
                "max_correction_age": max_age,
                "correction_loss_pct": loss_pct,
                "high_age_event_count": high_count,
            },
            timestamp_first = t_first,
            timestamp_last  = t_last,
            count           = high_count,
        ))

    return events


def _events_from_ins(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    status_dist = result.get("ins_status_distribution", {})
    dominant    = result.get("dominant_ins_status", "")
    total       = result.get("total_records", 1) or 1

    bad_count = sum(status_dist.get(s, 0) for s in Thresholds.INS_BAD_STATUSES)
    bad_pct   = bad_count / total * 100

    if dominant in Thresholds.INS_BAD_STATUSES:
        events.append(SemanticEvent(
            event_type    = "INS_NOT_CONVERGED",
            category      = "inertial",
            severity      = "high",
            confidence    = 0.95,
            description   = f"Dominant INS status is '{dominant}' — INS has not converged to a good solution",
            evidence_refs = ["ins_analyzer.dominant_ins_status", "INSPVA"],
            metrics       = {"dominant_status": dominant, "bad_status_pct": round(bad_pct, 1)},
        ))
    elif bad_pct > 10:
        events.append(SemanticEvent(
            event_type    = "INS_INTERMITTENT_ISSUES",
            category      = "inertial",
            severity      = "medium",
            confidence    = 0.80,
            description   = f"INS was in a degraded state for {bad_pct:.0f}% of records",
            evidence_refs = ["ins_analyzer.ins_status_distribution", "INSPVA"],
            metrics       = {"bad_status_pct": round(bad_pct, 1), "status_distribution": status_dist},
        ))

    # High azimuth variance
    az_stats = result.get("azimuth_stats", {})
    if az_stats.get("std_dev") and az_stats["std_dev"] > 2.0:
        events.append(SemanticEvent(
            event_type    = "HIGH_HEADING_VARIANCE",
            category      = "inertial",
            severity      = "low",
            confidence    = 0.70,
            description   = f"Heading std_dev {az_stats['std_dev']:.2f}° suggests dynamics or INS instability",
            evidence_refs = ["ins_analyzer.azimuth_stats", "INSPVA"],
            metrics       = az_stats,
        ))

    return events


def _events_from_time(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    # Just an informational event — file time coverage
    events.append(SemanticEvent(
        event_type    = "FILE_TIME_COVERAGE",
        category      = "data_integrity",
        severity      = "info",
        confidence    = 1.0,
        description   = f"File covers {result.get('duration_minutes', 0):.1f} minutes from {result.get('start_utc', 'N/A')} to {result.get('end_utc', 'N/A')}",
        evidence_refs = ["time_analyzer"],
        metrics       = {
            "duration_seconds": result.get("duration_seconds"),
            "duration_minutes": result.get("duration_minutes"),
            "start_utc":        result.get("start_utc"),
            "end_utc":          result.get("end_utc"),
        },
    ))

    return events


def _events_from_data_gaps(result: dict) -> list[SemanticEvent]:
    events = []
    if result.get("status") != "ok":
        return events

    gap_count = result.get("gap_count", 0)
    if gap_count == 0:
        return events

    continuity = result.get("data_continuity_pct", 100.0)
    total_missing = result.get("total_missing_seconds", 0)

    severity = "info"
    if gap_count >= Thresholds.GAP_CRITICAL or continuity < Thresholds.CONTINUITY_WARNING:
        severity = "high"
    elif gap_count >= Thresholds.GAP_WARNING:
        severity = "medium"

    events.append(SemanticEvent(
        event_type    = "DATA_GAPS_DETECTED",
        category      = "data_integrity",
        severity      = severity,
        confidence    = 1.0,
        description   = f"{gap_count} data gap(s) detected totalling {total_missing:.1f}s — data continuity: {continuity:.1f}%",
        evidence_refs = ["data_gap_analyzer"],
        metrics       = {
            "gap_count":              gap_count,
            "total_missing_seconds":  total_missing,
            "data_continuity_pct":    continuity,
        },
        count = gap_count,
    ))

    return events


# ═══════════════════════════════════════════════════════════════════
# CROSS-TOOL CORRELATION EVENTS
# These events require evidence from MULTIPLE tools simultaneously.
# This is the core value of the correlation architecture.
# ═══════════════════════════════════════════════════════════════════

def _generate_correlation_events(results: dict[str, dict]) -> list[SemanticEvent]:
    """
    Generates events that can ONLY be identified by correlating
    evidence from multiple tools simultaneously.

    These are the highest-value events — deterministic multi-log diagnosis.
    """
    events = []

    rx  = results.get("rxstatus_analyzer", {})
    cn0 = results.get("cn0_analyzer", {})
    bp  = results.get("bestpos_analyzer", {})
    itd = results.get("itdetect_analyzer", {})
    ca  = results.get("correction_age_analyzer", {})

    rx_ok  = rx.get("status") == "ok"
    cn0_ok = cn0.get("status") == "ok"
    bp_ok  = bp.get("status") == "ok"
    itd_ok = itd.get("status") == "ok"
    ca_ok  = ca.get("status") == "ok"

    # ── COMPOUND INTERFERENCE SIGNATURE ──────────────────────────────
    # Rule: jamming + low C/No + satellite loss = strong interference
    jamming   = rx_ok and rx.get("jamming_detected", False)
    low_cn0   = cn0_ok and cn0.get("avg_cn0", 99) < Thresholds.CN0_WARNING
    sat_loss  = (
        cn0_ok and cn0.get("min_satellites_tracked", 99) < Thresholds.SAT_MIN_RTK
        or
        bp_ok  and (bp.get("satellite_count", {}).get("min") or 99) < Thresholds.SAT_MIN_RTK
    )

    if jamming and low_cn0 and sat_loss:
        confidence = 0.97
        ref_tools = []
        if rx_ok:  ref_tools.append("rxstatus_analyzer")
        if cn0_ok: ref_tools.append("cn0_analyzer")
        if bp_ok:  ref_tools.append("bestpos_analyzer")
        events.append(SemanticEvent(
            event_type    = "COMPOUND_INTERFERENCE_SIGNATURE",
            category      = "interference",
            severity      = "critical",
            confidence    = confidence,
            description   = (
                "Multi-source interference confirmed: RXSTATUS jamming bit + low C/No + "
                "satellite loss all present simultaneously — strong active jamming signature"
            ),
            evidence_refs = ref_tools,
            metrics       = {
                "jamming_confirmed": True,
                "avg_cn0": cn0.get("avg_cn0") if cn0_ok else None,
                "min_satellites": cn0.get("min_satellites_tracked") if cn0_ok else None,
            },
        ))

    elif jamming and low_cn0:
        events.append(SemanticEvent(
            event_type    = "INTERFERENCE_CORROBORATED",
            category      = "interference",
            severity      = "critical",
            confidence    = 0.93,
            description   = (
                f"Jamming flag (RXSTATUS) corroborated by degraded C/No "
                f"({cn0.get('avg_cn0', 'N/A'):.1f} dB-Hz) in TRACKSTAT — consistent with active interference"
                if cn0_ok else
                "Jamming flag (RXSTATUS) confirmed by firmware"
            ),
            evidence_refs = ["rxstatus_analyzer", "cn0_analyzer"],
            metrics       = {
                "jamming_confirmed": True,
                "avg_cn0": cn0.get("avg_cn0") if cn0_ok else None,
            },
        ))

    # ── RTK INSTABILITY ROOT CAUSE ────────────────────────────────────
    # Rule: RTK float + high correction age + sat drop = diagnosable RTK failure
    if bp_ok:
        fix_dist    = bp.get("fix_type_distribution", {})
        total_recs  = bp.get("total_records", 1) or 1
        float_types = {"NARROW_FLOAT", "INS_RTKFLOAT", "WIDE_FLOAT", "FLOAT_CONV"}
        float_count = sum(fix_dist.get(k, 0) for k in float_types)
        float_pct   = float_count / total_recs * 100

        high_corr_age = (
            (bp_ok and (bp.get("correction_age", {}).get("avg") or 0) > Thresholds.CORR_AGE_WARNING)
            or
            (ca_ok and (ca.get("avg_correction_age") or 0) > Thresholds.CORR_AGE_WARNING)
        )
        sat_drops = len(bp.get("satellite_count", {}).get("drop_events", []))
        low_sats  = (bp.get("satellite_count", {}).get("min") or 99) < Thresholds.SAT_MIN_RTK

        if float_pct >= Thresholds.RTK_FLOAT_PCT and high_corr_age:
            ref_tools = ["bestpos_analyzer"]
            if ca_ok: ref_tools.append("correction_age_analyzer")
            cause_parts = []
            avg_age = (
                ca.get("avg_correction_age") if ca_ok
                else bp.get("correction_age", {}).get("avg")
            )
            if avg_age:
                cause_parts.append(f"stale corrections (avg {avg_age:.1f}s)")
            if sat_drops:
                cause_parts.append(f"{sat_drops} satellite drop event(s)")
                ref_tools.append("bestpos_analyzer.satellite_count")
            if low_sats:
                cause_parts.append(f"insufficient satellites (min {bp.get('satellite_count', {}).get('min')})")

            events.append(SemanticEvent(
                event_type    = "RTK_INSTABILITY_DIAGNOSED",
                category      = "positioning",
                severity      = "high",
                confidence    = min(0.75 + len(cause_parts) * 0.07, 0.95),
                description   = (
                    f"RTK instability diagnosed: {float_pct:.0f}% float solution. "
                    f"Contributing factors: {'; '.join(cause_parts)}"
                    if cause_parts else
                    f"RTK unstable ({float_pct:.0f}% float) with high correction age"
                ),
                evidence_refs = list(set(ref_tools)),
                metrics       = {
                    "float_pct":           round(float_pct, 1),
                    "avg_correction_age":  avg_age,
                    "satellite_drop_count": sat_drops,
                },
            ))

    # ── SPOOFING CORROBORATION ────────────────────────────────────────
    # Rule: spoofing flag + position drift + high C/No (artificially strong) = spoofing
    spoofing = rx_ok and rx.get("spoofing_detected", False)
    if spoofing and cn0_ok:
        high_cn0 = cn0.get("avg_cn0", 0) > 45.0   # Unusually high C/No = artificial signal
        if high_cn0:
            events.append(SemanticEvent(
                event_type    = "SPOOFING_CORROBORATED",
                category      = "interference",
                severity      = "critical",
                confidence    = 0.95,
                description   = (
                    f"Spoofing corroborated: firmware flag + unusually high C/No "
                    f"({cn0.get('avg_cn0'):.1f} dB-Hz) consistent with artificially strong spoofing signal"
                ),
                evidence_refs = ["rxstatus_analyzer", "cn0_analyzer"],
                metrics       = {
                    "spoofing_confirmed": True,
                    "avg_cn0": cn0.get("avg_cn0"),
                    "high_cn0_indicator": True,
                },
            ))

    # ── CORRECTION IMPACT ON RTK ──────────────────────────────────────
    # Rule: correction outage period coincides with RTK float = correction is the cause
    if ca_ok and bp_ok:
        max_age  = ca.get("max_correction_age", 0)
        fix_dist = bp.get("fix_type_distribution", {})
        total    = bp.get("total_records", 1) or 1
        float_types = {"NARROW_FLOAT", "INS_RTKFLOAT", "WIDE_FLOAT", "FLOAT_CONV"}
        float_pct = sum(fix_dist.get(k, 0) for k in float_types) / total * 100

        if max_age > Thresholds.CORR_AGE_LOSS and float_pct > 15:
            events.append(SemanticEvent(
                event_type    = "CORRECTION_LOSS_CAUSED_RTK_FLOAT",
                category      = "corrections",
                severity      = "high",
                confidence    = 0.87,
                description   = (
                    f"Correction loss (max age {max_age:.1f}s) likely caused RTK float "
                    f"({float_pct:.0f}% of records) — receiver reverted to float when base corrections were unavailable"
                ),
                evidence_refs = ["correction_age_analyzer", "bestpos_analyzer"],
                metrics       = {
                    "max_correction_age": max_age,
                    "float_pct":          round(float_pct, 1),
                    "loss_threshold":     Thresholds.CORR_AGE_LOSS,
                },
            ))

    return events


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def generate_semantic_events(results: dict[str, dict]) -> list[dict]:
    """
    Main entry point — takes all tool results and returns
    a complete list of semantic events as plain dicts.

    Called by the orchestrator after all tools have run.

    Args:
        results: dict mapping tool_id → tool output dict

    Returns:
        List of event dicts (sorted by severity priority)
    """
    all_events: list[SemanticEvent] = []

    # ── Per-tool event generators ─────────────────────────────────────
    _PER_TOOL_GENERATORS = {
        "rxstatus_analyzer":       _events_from_rxstatus,
        "itdetect_analyzer":       _events_from_itdetect,
        "cn0_analyzer":            _events_from_cn0,
        "bestpos_analyzer":        _events_from_bestpos,
        "correction_age_analyzer": _events_from_correction_age,
        "ins_analyzer":            _events_from_ins,
        "time_analyzer":           _events_from_time,
        "data_gap_analyzer":       _events_from_data_gaps,
        # receiver_health_analyzer delegates to rxstatus — no separate generator needed
    }

    for tool_id, generator in _PER_TOOL_GENERATORS.items():
        if tool_id in results:
            try:
                tool_events = generator(results[tool_id])
                all_events.extend(tool_events)
            except Exception as e:
                print(f"[SEMANTIC_EVENTS] Error in {tool_id} generator: {e}")

    # ── Cross-tool correlation events ─────────────────────────────────
    try:
        correlation_events = _generate_correlation_events(results)
        all_events.extend(correlation_events)
    except Exception as e:
        print(f"[SEMANTIC_EVENTS] Error in correlation event generator: {e}")

    # ── Sort by severity priority ─────────────────────────────────────
    _SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    all_events.sort(key=lambda e: _SEVERITY_ORDER.get(e.severity, 99))

    # Deduplicate by event_type — keep highest confidence if duplicated
    seen: dict[str, SemanticEvent] = {}
    for ev in all_events:
        if ev.event_type not in seen or ev.confidence > seen[ev.event_type].confidence:
            seen[ev.event_type] = ev

    final = sorted(seen.values(), key=lambda e: _SEVERITY_ORDER.get(e.severity, 99))

    print(f"[SEMANTIC_EVENTS] Generated {len(final)} events from {len(results)} tools")
    for ev in final:
        print(f"  [{ev.severity.upper():8s}] {ev.event_type} (conf={ev.confidence:.2f})")

    return [ev.to_dict() for ev in final]
