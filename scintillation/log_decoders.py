"""
log_decoders.py — NovAtel OEM7 multi-log parser for scintillation analysis.

Parses the following logs from a single NovAtel ASCII/binary log file:
  - RANGEA           → range_df        (one row per satellite observation)
  - ITDETECTSTATUSA  → itdetect_df     (one row per interference detection)
  - TRACKSTATA       → trackstat_df    (one row per channel entry)

Usage:
    from log_decoders import decode_file

    range_df, range_pivot_df, itdetect_df, trackstat_df = decode_file("mylog.log")

Or individually:
    from log_decoders import parse_range_from_file
    from log_decoders import parse_itdetect_from_file
    from log_decoders import parse_trackstat_from_file
"""

import re
import pandas as pd
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# SHARED CONSTANTS
# ═══════════════════════════════════════════════════════════════════

# NovAtel full ASCII log header line pattern
_HEADER_RE = re.compile(
    r"^#(?P<log_name>[A-Z0-9_]+),"
    r"(?P<header>[^;]*);"
    r"(?P<body>.+?)(?:\*[0-9a-fA-F]{1,8})?\s*$"
)

# Abbreviated ASCII header: <TRACKSTAT USB1 0 50.0 FINESTEERING 2209 515256.000 ...
_ABBREV_HEADER_RE = re.compile(
    r"^<\s*(?P<log_name>TRACKSTAT[A-Z0-9_]*)\s+(?P<rest>.+)$"
)

# Constellation map — shared across all logs
_CONSTELLATION_MAP = {
    0: "GPS", 1: "GLONASS", 2: "SBAS", 3: "Galileo",
    4: "BeiDou", 5: "QZSS", 6: "NavIC", 7: "Other",
}

# ITDETECTSTATUS detect_type normalization
_DETECT_TYPE_NORMALIZE = {
    "SPECTRUMANALYSIS":    "SPECTRUMANALYSIS",
    "STATISTICALANALYSIS": "STATISTICALANALYSIS",
    "STATISTICANALYSIS":   "STATISTICALANALYSIS",  # firmware spelling variant
}


# ═══════════════════════════════════════════════════════════════════
# CHANNEL TRACKING STATUS DECODER
# Reference: NovAtel OEM7 Channel Tracking Status table
#   Bits 16-18 : Satellite system / constellation (3 bits)
#   Bit  19    : Reserved
#   Bit  20    : Grouping flag
#   Bits 21-25 : Signal type (5 bits, dependent on constellation)
# Same bit layout used for BOTH RANGE and TRACKSTAT logs.
# ═══════════════════════════════════════════════════════════════════

# (constellation_id, signal_id) → signal name
# Directly from the official OEM7 Channel Tracking Status table
_SIGNAL_MAP = {
    # GPS (0)
    (0, 0):  "L1C/A",
    (0, 5):  "L2P",
    (0, 9):  "L2P(Y)",
    (0, 14): "L5(Q)",
    (0, 16): "L1C(P)",
    (0, 17): "L2C(M)",
    # GLONASS (1)
    (1, 0):  "L1C/A",
    (1, 1):  "L2C/A",
    (1, 5):  "L2P",
    (1, 6):  "L3(Q)",
    # SBAS (2)
    (2, 0):  "L1C/A",
    (2, 6):  "L5(I)",
    # Galileo (3)
    (3, 2):  "E1(C)",
    (3, 6):  "E6B",
    (3, 7):  "E6C",
    (3, 12): "E5a(Q)",
    (3, 17): "E5b(Q)",
    (3, 20): "E5AltBOC(Q)",
    # BeiDou (4)
    (4, 0):  "B1(I)_D1",
    (4, 1):  "B2(I)_D1",
    (4, 2):  "B3(I)_D1",
    (4, 4):  "B1(I)_D2",
    (4, 5):  "B2(I)_D2",
    (4, 6):  "B3(I)_D2",
    (4, 7):  "B1C(P)",
    (4, 9):  "B2a(P)",
    (4, 11): "B2b(I)",
    # QZSS (5)
    (5, 0):  "L1C/A",
    (5, 14): "L5(Q)",
    (5, 16): "L1C(P)",
    (5, 17): "L2C(M)",
    (5, 27): "L6P",
    (5, 28): "L6D",
    # NavIC (6)
    (6, 0):  "L5_SPS",
    # Other / L-band (7)
    (7, 19): "L-band",
}


def _decode_ch_tr_status(hex_str: str) -> tuple[str, str]:
    """
    Decode NovAtel channel tracking status word (used for both RANGE and TRACKSTAT).
    Bits 16-18 = constellation, bits 21-25 = signal type.
    Returns (constellation, signal_name).
    """
    try:
        val = int(hex_str.strip(), 16)
        constel_id = (val >> 16) & 0x07   # bits 16-18
        signal_id  = (val >> 21) & 0x1F   # bits 21-25
        constellation = _CONSTELLATION_MAP.get(constel_id, f"Unknown({constel_id})")
        signal = _SIGNAL_MAP.get((constel_id, signal_id), f"Sig{signal_id}")
        return constellation, signal
    except (ValueError, TypeError):
        return "Unknown", "Unknown"


# ═══════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════

def _safe_float(v: str, default=None):
    try:
        return float(v.strip())
    except (ValueError, AttributeError):
        return default


def _safe_int(v: str, default=None):
    try:
        return int(v.strip())
    except (ValueError, AttributeError):
        return default


def _parse_header_time(header_parts: list[str]) -> tuple[int, float]:
    try:
        week    = int(header_parts[4])   if len(header_parts) > 4 else 0
        seconds = float(header_parts[5]) if len(header_parts) > 5 else 0.0
    except (ValueError, IndexError):
        week, seconds = 0, 0.0
    return week, seconds


# ═══════════════════════════════════════════════════════════════════
# RANGEA PARSER
# ═══════════════════════════════════════════════════════════════════

def _parse_range_line(line: str) -> list[dict] | None:
    """Parse a single RANGEA line. Returns list of obs dicts or None."""
    m = _HEADER_RE.match(line.strip())
    if not m or m.group("log_name").upper() != "RANGEA":
        return None

    header_parts = [p.strip() for p in m.group("header").split(",")]
    week, seconds = _parse_header_time(header_parts)

    body_parts = [p.strip() for p in m.group("body").split(",")]
    try:
        num_obs = int(body_parts[0])
    except (ValueError, IndexError):
        return None

    FIELDS_PER_OBS = 10
    observations = []
    for i in range(num_obs):
        base = 1 + i * FIELDS_PER_OBS
        if base + FIELDS_PER_OBS > len(body_parts):
            break
        ch_tr_hex = body_parts[base + 9] if base + 9 < len(body_parts) else ""
        constellation, signal = _decode_ch_tr_status(ch_tr_hex)
        observations.append({
            "gps_week":      week,
            "gps_seconds":   seconds,
            "prn":           _safe_int(body_parts[base + 0]),
            "constellation": constellation,
            "signal":        signal,
            "adr_std":       _safe_float(body_parts[base + 5]),
            "cn0":           _safe_float(body_parts[base + 7]),
            "locktime":      _safe_float(body_parts[base + 8]),
        })
    return observations if observations else None


def parse_range_from_text(text: str) -> pd.DataFrame:
    all_obs = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("#RANGEA,"):
            continue
        obs = _parse_range_line(line)
        if obs:
            all_obs.extend(obs)
    if not all_obs:
        return pd.DataFrame()
    df = pd.DataFrame(all_obs)
    print(f"[RANGE]          {len(df)} obs, {df['gps_seconds'].nunique()} epochs")
    return df


def parse_range_from_file(filepath: str) -> pd.DataFrame:
    """Parse RANGEA from an ASCII file."""
    return parse_range_from_text(Path(filepath).read_text(encoding="utf-8", errors="replace"))


def parse_range_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    return parse_range_from_text(file_bytes.decode("utf-8", errors="replace"))


# ═══════════════════════════════════════════════════════════════════
# ITDETECTSTATUSA PARSER
# ═══════════════════════════════════════════════════════════════════

def _parse_itdetect_line(line: str) -> list[dict] | None:
    m = _HEADER_RE.match(line.strip())
    if not m or m.group("log_name").upper() != "ITDETECTSTATUSA":
        return None

    header_parts = [p.strip() for p in m.group("header").split(",")]
    week, seconds = _parse_header_time(header_parts)

    body_parts = [p.strip() for p in m.group("body").split(",")]
    num_entries = _safe_int(body_parts[0])
    if num_entries is None:
        return None

    # Zero entries = interference cleared; keep as sentinel
    if num_entries == 0:
        return [{
            "gps_week": week, "gps_seconds": seconds,
            "rf_path": None, "detect_type": "NONE",
            "center_freq_mhz": None, "bandwidth_mhz": None,
            "power_dbm": None, "psd_dbmhz": None,
            "param1": None, "param2": None, "param3": None, "param4": None,
        }]

    FIELDS_PER_ENTRY = 9
    entries = []
    for i in range(num_entries):
        base = 1 + i * FIELDS_PER_ENTRY
        if base + FIELDS_PER_ENTRY > len(body_parts):
            break
        rf_path     = body_parts[base + 0].upper()
        raw_type    = body_parts[base + 1].upper()
        detect_type = _DETECT_TYPE_NORMALIZE.get(raw_type, raw_type)
        p1 = _safe_float(body_parts[base + 2])
        p2 = _safe_float(body_parts[base + 3])
        p3 = _safe_float(body_parts[base + 4])
        p4 = _safe_float(body_parts[base + 5])
        is_spectrum = detect_type == "SPECTRUMANALYSIS"
        entries.append({
            "gps_week":        week,
            "gps_seconds":     seconds,
            "rf_path":         rf_path,
            "detect_type":     detect_type,
            "center_freq_mhz": p1 if is_spectrum else None,
            "bandwidth_mhz":   p2 if is_spectrum else None,
            "power_dbm":       p3 if is_spectrum else None,
            "psd_dbmhz":       p4 if is_spectrum else None,
            "param1": p1, "param2": p2, "param3": p3, "param4": p4,
        })
    return entries if entries else None


def parse_itdetect_from_text(text: str) -> pd.DataFrame:
    all_entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("#ITDETECTSTATUSA,"):
            continue
        entries = _parse_itdetect_line(line)
        if entries:
            all_entries.extend(entries)
    if not all_entries:
        return pd.DataFrame()
    df = pd.DataFrame(all_entries)
    detected = (df["detect_type"] != "NONE").sum()
    print(f"[ITDETECTSTATUS] {detected} interference entries, {df['gps_seconds'].nunique()} epochs")
    return df


def parse_itdetect_from_file(filepath: str) -> pd.DataFrame:
    """Parse ITDETECTSTATUSA from an ASCII file."""
    return parse_itdetect_from_text(Path(filepath).read_text(encoding="utf-8", errors="replace"))


def parse_itdetect_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    return parse_itdetect_from_text(file_bytes.decode("utf-8", errors="replace"))


# ═══════════════════════════════════════════════════════════════════
# TRACKSTATA PARSER (full ASCII + abbreviated ASCII)
# ═══════════════════════════════════════════════════════════════════

FIELDS_PER_CHANNEL = 10


def _build_channel_row(week: int, seconds: float,
                        sol_status: str, pos_type: str, cutoff,
                        fields: list[str]) -> dict:
    ch_tr_hex = fields[2]
    constellation, signal = _decode_ch_tr_status(ch_tr_hex)
    prn = _safe_int(fields[0])
    return {
        "gps_week":      week,
        "gps_seconds":   seconds,
        "sol_status":    sol_status,
        "pos_type":      pos_type,
        "cutoff":        cutoff,
        "prn":           prn,
        "glofreq":       _safe_int(fields[1]),
        "constellation": constellation,
        "signal":        signal,
        "psr":           _safe_float(fields[3]),
        "doppler":       _safe_float(fields[4]),
        "cn0":           _safe_float(fields[5]),
        "locktime":      _safe_float(fields[6]),
        "psr_res":       _safe_float(fields[7]),
        "reject":        fields[8].strip(),
        "psr_weight":    _safe_float(fields[9]),
        "ch_tr_status":  ch_tr_hex.strip(),
        "is_idle":       prn == 0,
    }


def _parse_trackstat_line(line: str) -> list[dict] | None:
    """Parse a single full-ASCII TRACKSTATA line."""
    m = _HEADER_RE.match(line.strip())
    if not m:
        return None
    log_name = m.group("log_name").upper()
    # Accept ONLY exactly TRACKSTATA
    if log_name != "TRACKSTATA":
        return None

    header_parts = [p.strip() for p in m.group("header").split(",")]
    week, seconds = _parse_header_time(header_parts)

    body_parts = [p.strip() for p in m.group("body").split(",")]
    if len(body_parts) < 4:
        return None

    sol_status = body_parts[0]
    pos_type   = body_parts[1]
    cutoff     = _safe_float(body_parts[2])
    num_chans  = _safe_int(body_parts[3], 0) or 0

    entries = []
    for i in range(num_chans):
        base = 4 + i * FIELDS_PER_CHANNEL
        if base + FIELDS_PER_CHANNEL > len(body_parts):
            break
        entries.append(_build_channel_row(
            week, seconds, sol_status, pos_type, cutoff,
            body_parts[base:base + FIELDS_PER_CHANNEL]
        ))
    return entries if entries else None


def _parse_abbrev_trackstat_blocks(lines: list[str]) -> list[dict]:
    """Parse abbreviated ASCII TRACKSTAT blocks (< prefixed, multi-line)."""
    entries = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        m = _ABBREV_HEADER_RE.match(line)
        if not m:
            i += 1
            continue
        header_tokens = m.group("rest").split()
        try:
            week    = int(header_tokens[4])   if len(header_tokens) > 4 else 0
            seconds = float(header_tokens[5]) if len(header_tokens) > 5 else 0.0
        except (ValueError, IndexError):
            week, seconds = 0, 0.0
        i += 1
        if i >= n:
            break
        info_tokens = lines[i].strip().lstrip("<").split()
        if len(info_tokens) < 4:
            continue
        sol_status = info_tokens[0]
        pos_type   = info_tokens[1]
        cutoff     = _safe_float(info_tokens[2])
        num_chans  = _safe_int(info_tokens[3], 0) or 0
        parsed = 0
        i += 1
        while i < n and parsed < num_chans:
            ch_line = lines[i].strip()
            if not ch_line.startswith("<"):
                break
            tokens = ch_line.lstrip("<").split()
            if len(tokens) >= FIELDS_PER_CHANNEL:
                entries.append(_build_channel_row(
                    week, seconds, sol_status, pos_type, cutoff,
                    tokens[:FIELDS_PER_CHANNEL]
                ))
                parsed += 1
            i += 1
    return entries


def parse_trackstat_from_text(text: str) -> pd.DataFrame:
    all_entries = []
    lines = text.splitlines()
    # Full ASCII
    for line in lines:
        line = line.strip()
        if not line.startswith("#TRACKSTATA,"):
            continue
        entries = _parse_trackstat_line(line)
        if entries:
            all_entries.extend(entries)
    # Abbreviated ASCII
    all_entries.extend(_parse_abbrev_trackstat_blocks(lines))
    if not all_entries:
        return pd.DataFrame()
    df = pd.DataFrame(all_entries)
    print(f"[TRACKSTAT]      {len(df)} channels, {df['gps_seconds'].nunique()} epochs")
    return df


def parse_trackstat_from_file(filepath: str) -> pd.DataFrame:
    """Parse TRACKSTATA from an ASCII file."""
    return parse_trackstat_from_text(Path(filepath).read_text(encoding="utf-8", errors="replace"))


def parse_trackstat_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    return parse_trackstat_from_text(file_bytes.decode("utf-8", errors="replace"))


# ═══════════════════════════════════════════════════════════════════
# SATVIS2A PARSER
# ═══════════════════════════════════════════════════════════════════
# SATVIS2 ASCII body layout:
#  field[0] = satellite_system  (GPS, GLONASS, SBAS, GALILEO, BEIDOU, QZSS, ...)
#  field[1] = sat_vis           (TRUE / FALSE — is visibility valid?)
#  field[2] = almanac_flag      (TRUE / FALSE — complete almanac used?)
#  field[3] = num_sats          (number of satellites to follow)
#  Per satellite (6 fields each):
#    +0: satellite_id      (PRN for GPS; slot+channel for GLONASS e.g. "13-2")
#    +1: health            (0 = healthy, non-zero = unhealthy)
#    +2: elevation         (degrees, -90 to +90)
#    +3: azimuth           (degrees, 0 to 360)
#    +4: true_doppler      (Hz)
#    +5: apparent_doppler  (Hz, includes receiver clock drift)
#
# NOTE: SATVIS2 emits one message PER CONSTELLATION per epoch.
# A single GPS epoch will have one #SATVIS2A line for GPS,
# another for GLONASS, etc. All are merged into one DataFrame.

_SATVIS2_SYSTEM_MAP = {
    "GPS": "GPS", "GLONASS": "GLONASS", "SBAS": "SBAS",
    "GALILEO": "Galileo", "BEIDOU": "BeiDou",
    "QZSS": "QZSS", "NAVIC": "NavIC",
}

FIELDS_PER_SAT = 6


def _parse_satvis2_line(line: str) -> list[dict] | None:
    """Parse a single SATVIS2A line. Returns list of satellite dicts or None."""
    m = _HEADER_RE.match(line.strip())
    if not m or m.group("log_name").upper() != "SATVIS2A":
        return None

    header_parts = [p.strip() for p in m.group("header").split(",")]
    week, seconds = _parse_header_time(header_parts)

    body_parts = [p.strip() for p in m.group("body").split(",")]
    if len(body_parts) < 4:
        return None

    system_raw   = body_parts[0].upper()
    constellation = _SATVIS2_SYSTEM_MAP.get(system_raw, system_raw)
    sat_vis       = body_parts[1].upper() == "TRUE"
    almanac_flag  = body_parts[2].upper() == "TRUE"

    try:
        num_sats = int(body_parts[3])
    except (ValueError, IndexError):
        return None

    sats = []
    for i in range(num_sats):
        base = 4 + i * FIELDS_PER_SAT
        if base + FIELDS_PER_SAT > len(body_parts):
            break

        sat_id_raw = body_parts[base + 0].strip()
        # GLONASS slot+channel: "13-2" → prn=13, glo_channel=-2
        prn, glo_channel = sat_id_raw, None
        if "-" in sat_id_raw:
            parts_id = sat_id_raw.split("-", 1)
            prn = parts_id[0]
            glo_channel = _safe_int("-" + parts_id[1])

        sats.append({
            "gps_week":       week,
            "gps_seconds":    seconds,
            "constellation":  constellation,
            "sat_vis":        sat_vis,
            "almanac_flag":   almanac_flag,
            "satellite_id":   sat_id_raw,
            "prn":            _safe_int(prn),
            "glo_channel":    glo_channel,
            "health":         _safe_int(body_parts[base + 1]),
            "elevation":      _safe_float(body_parts[base + 2]),   # degrees
            "azimuth":        _safe_float(body_parts[base + 3]),   # degrees
            "true_doppler":   _safe_float(body_parts[base + 4]),   # Hz
            "app_doppler":    _safe_float(body_parts[base + 5]),   # Hz
        })
    return sats if sats else None


def parse_satvis2_from_text(text: str) -> pd.DataFrame:
    all_sats = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("#SATVIS2A,"):
            continue
        sats = _parse_satvis2_line(line)
        if sats:
            all_sats.extend(sats)
    if not all_sats:
        return pd.DataFrame()
    df = pd.DataFrame(all_sats)
    print(f"[SATVIS2]        {len(df)} sat records, {df['gps_seconds'].nunique()} epochs, "
          f"constellations: {sorted(df['constellation'].unique().tolist())}")
    return df


def parse_satvis2_from_file(filepath: str) -> pd.DataFrame:
    """Parse SATVIS2A from an ASCII file."""
    return parse_satvis2_from_text(Path(filepath).read_text(encoding="utf-8", errors="replace"))


def parse_satvis2_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    return parse_satvis2_from_text(file_bytes.decode("utf-8", errors="replace"))


# ═══════════════════════════════════════════════════════════════════
# BESTPOSA PARSER
# ═══════════════════════════════════════════════════════════════════
# BESTPOS ASCII body field layout (0-indexed from fields_raw):
#  0: sol_status     (SOL_COMPUTED, INSUFFICIENT_OBS, etc.)
#  1: pos_type       (SINGLE, PSRDIFF, PPP, NARROW_INT, INS_PPP, etc.)
#  2: latitude       (degrees)
#  3: longitude      (degrees)
#  4: height         (m, above ellipsoid)
#  5: undulation     (m, geoid undulation)
#  6: datum_id       (enum)
#  7: lat_std        (m, 1-sigma latitude std dev)
#  8: lon_std        (m, 1-sigma longitude std dev)
#  9: hgt_std        (m, 1-sigma height std dev)
# 10: stn_id         (base station ID)
# 11: pdop           (position dilution of precision)  ← note: some firmware omits
# 12: diff_age       (seconds, age of differential corrections)
# 13: num_svs        (number of satellites tracked)
# 14: num_sol_svs    (number of satellites used in solution)

def _parse_bestpos_line(line: str) -> dict | None:
    """Parse a single BESTPOSA line. Returns one dict or None."""
    m = _HEADER_RE.match(line.strip())
    if not m or m.group("log_name").upper() != "BESTPOSA":
        return None

    header_parts = [p.strip() for p in m.group("header").split(",")]
    week, seconds = _parse_header_time(header_parts)

    body_parts = [p.strip() for p in m.group("body").split(",")]
    if len(parts := body_parts) < 10:
        return None

    return {
        "gps_week":          week,
        "gps_seconds":       seconds,
        "sol_status":        parts[0]             if len(parts) > 0  else "",
        "pos_type":          parts[1]             if len(parts) > 1  else "",
        "latitude":          _safe_float(parts[2]) if len(parts) > 2  else None,
        "longitude":         _safe_float(parts[3]) if len(parts) > 3  else None,
        "height":            _safe_float(parts[4]) if len(parts) > 4  else None,
        "undulation":        _safe_float(parts[5]) if len(parts) > 5  else None,
        "datum_id":          parts[6]             if len(parts) > 6  else "",
        "lat_std":           _safe_float(parts[7]) if len(parts) > 7  else None,
        "lon_std":           _safe_float(parts[8]) if len(parts) > 8  else None,
        "hgt_std":           _safe_float(parts[9]) if len(parts) > 9  else None,
        "stn_id":            parts[10]            if len(parts) > 10 else "",
        "diff_age":          _safe_float(parts[11]) if len(parts) > 11 else None,
        "sol_age":           _safe_float(parts[12]) if len(parts) > 12 else None,
        "num_svs":           _safe_int(parts[13])  if len(parts) > 13 else None,
        "num_sol_svs":       _safe_int(parts[14])  if len(parts) > 14 else None,
        "num_sol_L1svs":     _safe_int(parts[15])  if len(parts) > 15 else None,
        "num_sol_multi_svs": _safe_int(parts[16])  if len(parts) > 16 else None,
    }


def parse_bestpos_from_text(text: str) -> pd.DataFrame:
    all_rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("#BESTPOSA,"):
            continue
        row = _parse_bestpos_line(line)
        if row:
            all_rows.append(row)
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    print(f"[BESTPOS]        {len(df)} records, {df['gps_seconds'].nunique()} epochs")
    return df


def parse_bestpos_from_file(filepath: str) -> pd.DataFrame:
    """Parse BESTPOSA from an ASCII file."""
    return parse_bestpos_from_text(Path(filepath).read_text(encoding="utf-8", errors="replace"))


def parse_bestpos_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    return parse_bestpos_from_text(file_bytes.decode("utf-8", errors="replace"))




def decode_file(filepath: str) -> tuple:
    """
    Decode RANGEA, ITDETECTSTATUSA, TRACKSTATA, BESTPOSA, SATVIS2A from a
    single NovAtel ASCII log file.  No external dependencies — plain text read.

    Returns:
        (range_df, range_pivot_df, epoch_health_df, itdetect_df, trackstat_df, bestpos_df, satvis2_df)

        range_df        : long-form, one row per observation, enriched with
                          cno_drop, lock_drop, cno_flag, adr_flag, lock_flag, combined_flag
        range_pivot_df  : wide-form pivot — rows = timestamp, columns = CONSTELLATION_SIGNAL_PRN
        epoch_health_df : one row per epoch — cno/adr/lock epoch flags + signal counts
    """
    text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    range_obs     = []
    itdetect_obs  = []
    trackstat_obs = []
    bestpos_obs   = []
    satvis2_obs   = []

    # Single pass over all lines — route each to its parser
    for line in lines:
        s = line.strip()
        if not s or s[0] not in ("#", "<"):
            continue

        if s.startswith("#RANGEA,"):
            obs = _parse_range_line(s)
            if obs:
                range_obs.extend(obs)

        elif s.startswith("#ITDETECTSTATUSA,"):
            entries = _parse_itdetect_line(s)
            if entries:
                itdetect_obs.extend(entries)

        elif s.startswith("#TRACKSTATA,") or s.startswith("<"):
            # full ASCII TRACKSTATA handled inline; abbreviated blocks handled below
            if s.startswith("#TRACKSTATA,"):
                entries = _parse_trackstat_line(s)
                if entries:
                    trackstat_obs.extend(entries)

        elif s.startswith("#BESTPOSA,"):
            row = _parse_bestpos_line(s)
            if row:
                bestpos_obs.append(row)

        elif s.startswith("#SATVIS2A,"):
            sats = _parse_satvis2_line(s)
            if sats:
                satvis2_obs.extend(sats)

    # Abbreviated TRACKSTAT blocks need the full line list
    trackstat_obs.extend(_parse_abbrev_trackstat_blocks(lines))

    range_df     = pd.DataFrame(range_obs)     if range_obs     else pd.DataFrame()
    itdetect_df  = pd.DataFrame(itdetect_obs)  if itdetect_obs  else pd.DataFrame()
    trackstat_df = pd.DataFrame(trackstat_obs) if trackstat_obs else pd.DataFrame()
    bestpos_df   = pd.DataFrame(bestpos_obs)   if bestpos_obs   else pd.DataFrame()
    satvis2_df   = pd.DataFrame(satvis2_obs)   if satvis2_obs   else pd.DataFrame()

    # Enrich RANGE: add diff columns + per-signal flags
    from scintillation.scintillation_detector import (enrich_range_df, enrich_range_with_elevation,
                                                      epoch_health, enrich_bestpos_df,
                                                      detect_scintillation)
    range_df        = enrich_range_df(range_df)
    range_df        = enrich_range_with_elevation(range_df, satvis2_df)
    epoch_health_df = epoch_health(range_df)

    # Enrich BESTPOS: add region_flag, local_hour, time_flag
    bestpos_df = enrich_bestpos_df(bestpos_df)

    # Final scintillation decision — one row per epoch
    scintillation_df = detect_scintillation(epoch_health_df, bestpos_df)

    # Pivot RANGE into wide format (timestamp × signal+PRN blob)
    range_pivot_df = pivot_range_df(range_df)

    print(f"\n[DECODED] {filepath}")
    if not range_df.empty:
        print(f"  RANGE          : {len(range_df)} obs, {range_df['gps_seconds'].nunique()} epochs")
        print(f"  RANGE (pivoted): {range_pivot_df.shape[0]} timestamps × {range_pivot_df.shape[1]} columns")
        if not epoch_health_df.empty:
            bad  = (epoch_health_df["cno_epoch_flag"] == "BAD").sum()
            warn = (epoch_health_df["cno_epoch_flag"] == "WARNING").sum()
            print(f"  EPOCH HEALTH   : {bad} BAD, {warn} WARNING epochs (cno)")
        if not scintillation_df.empty:
            for lvl in ["VERY_HIGH", "STRONG", "TRUE", "POSSIBLE_INTERFERENCE"]:
                n = (scintillation_df["scintillation_flag"] == lvl).sum()
                if n:
                    print(f"  SCINTILLATION  : {n} epochs → {lvl}")
    else:
        print("  RANGE          : No RANGEA records")
    if not itdetect_df.empty:
        detected = (itdetect_df["detect_type"] != "NONE").sum()
        print(f"  ITDETECTSTATUS : {detected} interference entries, {itdetect_df['gps_seconds'].nunique()} epochs")
    else:
        print("  ITDETECTSTATUS : No ITDETECTSTATUSA records")
    if not trackstat_df.empty:
        print(f"  TRACKSTAT      : {len(trackstat_df)} channels, {trackstat_df['gps_seconds'].nunique()} epochs")
    else:
        print("  TRACKSTAT      : No TRACKSTATA records")
    if not bestpos_df.empty:
        print(f"  BESTPOS        : {len(bestpos_df)} records, {bestpos_df['gps_seconds'].nunique()} epochs")
        region_pct = bestpos_df["region_flag"].mean() * 100
        time_pct   = bestpos_df["time_flag"].mean() * 100
        lat_mean   = bestpos_df["latitude"].mean()
        lat_min    = bestpos_df["latitude"].min()
        lat_max    = bestpos_df["latitude"].max()
        zone = ("EQUATORIAL" if abs(lat_mean) <= 20
                else "AURORAL"     if 60 <= abs(lat_mean) <= 75
                else "MID-LATITUDE (not scintillation-prone)")
        print(f"  BESTPOS region : {zone}")
        print(f"  BESTPOS lat    : min={lat_min:.3f}°  mean={lat_mean:.3f}°  max={lat_max:.3f}°")
        print(f"  region_flag=True: {region_pct:.0f}%   time_flag=True: {time_pct:.0f}%")
        if region_pct == 0:
            print("  NOTE: region_flag=False throughout — location is mid-latitude.")
            print("        scintillation_flag will not reach TRUE via region path,")
            print("        but STRONG/VERY_HIGH can still trigger from adr/lock/elevation evidence.")
    else:
        print("  BESTPOS        : No BESTPOSA records")
    if not satvis2_df.empty:
        consts = sorted(satvis2_df["constellation"].unique().tolist())
        print(f"  SATVIS2        : {len(satvis2_df)} sat records, {satvis2_df['gps_seconds'].nunique()} epochs, {consts}")
    else:
        print("  SATVIS2        : No SATVIS2A records")

    return range_df, range_pivot_df, epoch_health_df, scintillation_df, itdetect_df, trackstat_df, bestpos_df, satvis2_df


# ═══════════════════════════════════════════════════════════════════
# SUMMARY HELPERS
# ═══════════════════════════════════════════════════════════════════

# ── RANGE pivot ──────────────────────────────────────────────────
def _fmt_blob(cn0, adr_std, locktime) -> str | None:
    """Format three metrics into a single cell string blob.
    Returns None (NaN) if all three values are missing."""
    if pd.isna(cn0) and pd.isna(adr_std) and pd.isna(locktime):
        return None
    parts = []
    if not pd.isna(cn0):
        parts.append(f"cn0={cn0:.3f}")
    if not pd.isna(adr_std):
        parts.append(f"adr={adr_std:.4f}")
    if not pd.isna(locktime):
        parts.append(f"lock={locktime:.3f}")
    return " | ".join(parts)


def pivot_range_df(range_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot the long-form RANGE DataFrame into a wide format.

    Input columns : gps_week, gps_seconds, prn, signal, cn0, adr_std, locktime
    Output layout :
        - Index   : timestamp  "WWWW SSSSS.SSS"  (GPS week + seconds)
        - Columns : one column per (signal, PRN) e.g. "GPS_L1CA 6"
        - Cells   : blob string  "cn0=53.964 | adr=0.0031 | lock=1767.330"
                    (NaN when that satellite is not observed at that epoch)

    Columns are sorted by signal name then PRN number.
    """
    if range_df.empty:
        return pd.DataFrame()

    df = range_df.copy()

    # Numeric sort key — not stored in the output
    df["_ts_sort"] = df["gps_week"] * 604800.0 + df["gps_seconds"]
    df["timestamp"] = df.apply(
        lambda r: f"{int(r['gps_week'])} {r['gps_seconds']:.3f}", axis=1
    )

    # Column label e.g. "GPS_L2P_58", "BeiDou_B1(I)_D1_27"
    df["sig_prn"] = (
        df["constellation"].astype(str) + "_"
        + df["signal"].astype(str) + "_"
        + df["prn"].astype(str)
    )

    # Build blob per row
    df["blob"] = df.apply(
        lambda r: _fmt_blob(r["cn0"], r["adr_std"], r["locktime"]), axis=1
    )

    # Pivot: one row per timestamp, one column per sig_prn
    # Use first() in case of duplicate (timestamp, sig_prn) — should not happen
    wide = df.pivot_table(
        index=["timestamp", "_ts_sort"],
        columns="sig_prn",
        values="blob",
        aggfunc="first",
    )
    wide.columns.name = None  # remove the "sig_prn" axis label from columns

    # Sort columns: constellation+signal first, then PRN number
    def _col_sort_key(sp: str):
        # label format: "CONSTELLATION_SIGNAL_PRN"  e.g. "GPS_L2P_58"
        # PRN is always the last underscore-separated token
        parts = sp.rsplit("_", 1)
        prefix = parts[0]                                          # "GPS_L2P"
        prn = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        return (prefix, prn)

    wide = wide.reindex(columns=sorted(wide.columns, key=_col_sort_key))

    # Sort rows chronologically, then clean up the sort-key level
    wide = wide.sort_values("_ts_sort")
    wide = wide.reset_index().drop(columns=["_ts_sort"]).set_index("timestamp")
    wide.index.name = "timestamp [GPS week, seconds]"

    return wide


# ── RANGE summaries ───────────────────────────────────────────────
def get_range_constellation_summary(range_df: pd.DataFrame) -> pd.DataFrame:
    """Summarise by constellation and signal."""
    if range_df.empty:
        return pd.DataFrame()
    return range_df.groupby(["constellation", "signal"]).agg(
        satellites=("prn", "nunique"),
        avg_cn0=("cn0", "mean"),
        min_cn0=("cn0", "min"),
        max_cn0=("cn0", "max"),
    ).round(2).reset_index()


def get_range_signal_summary(range_df: pd.DataFrame) -> pd.DataFrame:
    if range_df.empty:
        return pd.DataFrame()
    return range_df.groupby(["constellation", "signal"]).agg(
        channels=("prn", "count"),
        avg_cn0=("cn0", "mean"),
    ).round(2).reset_index()


# ── ITDETECTSTATUS summaries ──────────────────────────────────────
def get_rf_path_summary(itdetect_df: pd.DataFrame) -> pd.DataFrame:
    if itdetect_df.empty:
        return pd.DataFrame()
    detected = itdetect_df[itdetect_df["detect_type"] != "NONE"]
    if detected.empty:
        return pd.DataFrame()
    return detected.groupby(["rf_path", "detect_type"]).agg(
        detections=("gps_seconds", "count"),
        epochs=("gps_seconds", "nunique"),
        max_power_dbm=("power_dbm", "max"),
        avg_power_dbm=("power_dbm", "mean"),
    ).round(2).reset_index()


def get_spectrum_events(itdetect_df: pd.DataFrame) -> pd.DataFrame:
    if itdetect_df.empty:
        return pd.DataFrame()
    spec = itdetect_df[itdetect_df["detect_type"] == "SPECTRUMANALYSIS"].copy()
    if spec.empty:
        return pd.DataFrame()
    spec["freq_bin_mhz"] = spec["center_freq_mhz"].round(0)
    return spec.groupby(["rf_path", "freq_bin_mhz"]).agg(
        detections=("gps_seconds", "count"),
        first_seen=("gps_seconds", "min"),
        last_seen=("gps_seconds", "max"),
        avg_bandwidth_mhz=("bandwidth_mhz", "mean"),
        max_power_dbm=("power_dbm", "max"),
        max_psd_dbmhz=("psd_dbmhz", "max"),
    ).round(3).reset_index()


# ── TRACKSTAT summaries ───────────────────────────────────────────
def get_active_channels(trackstat_df: pd.DataFrame) -> pd.DataFrame:
    if trackstat_df.empty:
        return pd.DataFrame()
    return trackstat_df[~trackstat_df["is_idle"]].reset_index(drop=True)


def get_trackstat_constellation_summary(trackstat_df: pd.DataFrame) -> pd.DataFrame:
    active = get_active_channels(trackstat_df)
    if active.empty:
        return pd.DataFrame()
    return active.groupby("constellation").agg(
        satellites=("prn", "nunique"),
        avg_cn0=("cn0", "mean"),
        min_cn0=("cn0", "min"),
        max_cn0=("cn0", "max"),
    ).round(2).reset_index()


def get_reject_summary(trackstat_df: pd.DataFrame) -> pd.DataFrame:
    if trackstat_df.empty:
        return pd.DataFrame()
    return (
        trackstat_df.groupby("reject")
        .agg(channels=("prn", "count"), avg_cn0=("cn0", "mean"))
        .round(2).reset_index()
        .sort_values("channels", ascending=False, ignore_index=True)
    )


def get_trackstat_signal_summary(trackstat_df: pd.DataFrame) -> pd.DataFrame:
    active = get_active_channels(trackstat_df)
    if active.empty:
        return pd.DataFrame()
    return active.groupby(["constellation", "signal"]).agg(
        channels=("prn", "count"),
        avg_cn0=("cn0", "mean"),
    ).round(2).reset_index()


# ═══════════════════════════════════════════════════════════════════
# STANDALONE — set file path and run
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # ── Set your paths here ───────────────────────────────────────────
    FILE_PATH        = r"D:\DATASET\NMZT.ascii"   # ← input file
    OUT_RANGE        = r"D:\DATASET\range_df.csv"
    OUT_RANGE_PIVOT  = r"D:\DATASET\range_pivot_df.csv"
    OUT_ITDETECT     = r"D:\DATASET\itdetect_df.csv"
    OUT_TRACKSTAT    = r"D:\DATASET\trackstat_df.csv"
    OUT_BESTPOS      = r"D:\DATASET\bestpos_df.csv"
    OUT_SATVIS2      = r"D:\DATASET\satvis2_df.csv"
    # ─────────────────────────────────────────────────────────────────

    # Create output folder if it doesn't exist
    Path(OUT_RANGE).parent.mkdir(parents=True, exist_ok=True)

    range_df, range_pivot_df, epoch_health_df, scintillation_df, itdetect_df, trackstat_df, bestpos_df, satvis2_df = decode_file(FILE_PATH)

    # ── RANGE ─────────────────────────────────────────────────────────
    if not range_df.empty:
        print("\n── range_df (long-form, enriched) ──")
        print(range_df[["gps_seconds", "constellation", "signal", "prn",
                         "cn0", "cno_drop", "cno_flag",
                         "adr_std", "adr_flag",
                         "locktime", "lock_drop", "lock_flag",
                         "combined_flag"]].head(10))
        print(f"Shape: {range_df.shape}")
        print("\n── Constellation summary (RANGE) ──")
        print(get_range_constellation_summary(range_df))
        range_df.to_csv(OUT_RANGE, index=False)
        print(f"Saved → {OUT_RANGE}")

    if not range_pivot_df.empty:
        print("\n── range_pivot_df (wide-form) ──")
        print(range_pivot_df.iloc[:5, :6])
        print(f"Shape: {range_pivot_df.shape}")
        range_pivot_df.to_csv(OUT_RANGE_PIVOT)
        print(f"Saved → {OUT_RANGE_PIVOT}")

    if not epoch_health_df.empty:
        OUT_EPOCH = OUT_RANGE.replace("range_df.csv", "epoch_health_df.csv")
        print("\n── epoch_health_df ──")
        print(epoch_health_df.head(10))
        epoch_health_df.to_csv(OUT_EPOCH, index=False)
        print(f"Saved → {OUT_EPOCH}")

    if not scintillation_df.empty:
        OUT_SCINT = OUT_RANGE.replace("range_df.csv", "scintillation_df.csv")
        print("\n── scintillation_df ──")
        print(scintillation_df[["gps_seconds", "scintillation_flag", "confidence_level",
                                 "region_flag", "time_flag",
                                 "cno_epoch_flag", "adr_epoch_flag", "lock_epoch_flag",
                                 "high_elev_lock_flag"]].head(20).to_string(index=False))
        for lvl in ["VERY_HIGH", "STRONG", "TRUE", "POSSIBLE_INTERFERENCE"]:
            n = (scintillation_df["scintillation_flag"] == lvl).sum()
            if n:
                print(f"  {lvl}: {n} epochs")
        scintillation_df.to_csv(OUT_SCINT, index=False)
        print(f"Saved → {OUT_SCINT}")

    # ── ITDETECTSTATUS ────────────────────────────────────────────────
    if not itdetect_df.empty:
        print("\n── itdetect_df ──")
        print(itdetect_df.head())
        print(f"Shape: {itdetect_df.shape}")
        print("\n── RF path summary ──")
        print(get_rf_path_summary(itdetect_df))
        print("\n── Spectrum events ──")
        print(get_spectrum_events(itdetect_df))
        itdetect_df.to_csv(OUT_ITDETECT, index=False)
        print(f"Saved → {OUT_ITDETECT}")

    # ── TRACKSTAT ─────────────────────────────────────────────────────
    if not trackstat_df.empty:
        print("\n── trackstat_df ──")
        print(trackstat_df.head())
        print(f"Shape: {trackstat_df.shape}")
        print("\n── Reject summary (TRACKSTAT) ──")
        print(get_reject_summary(trackstat_df))
        print("\n── Constellation summary (TRACKSTAT) ──")
        print(get_trackstat_constellation_summary(trackstat_df))
        trackstat_df.to_csv(OUT_TRACKSTAT, index=False)
        print(f"Saved → {OUT_TRACKSTAT}")

    # ── BESTPOS ───────────────────────────────────────────────────────
    if not bestpos_df.empty:
        print("\n── bestpos_df (with region & time flags) ──")
        print(bestpos_df[["gps_seconds", "latitude", "longitude",
                           "local_hour", "region_flag", "time_flag"]].head(10))
        print(f"Shape: {bestpos_df.shape}")
        print(f"region_flag True: {bestpos_df['region_flag'].sum()} / {len(bestpos_df)} records")
        print(f"time_flag   True: {bestpos_df['time_flag'].sum()} / {len(bestpos_df)} records")
        bestpos_df.to_csv(OUT_BESTPOS, index=False)
        print(f"Saved → {OUT_BESTPOS}")

    # ── SATVIS2 ───────────────────────────────────────────────────────
    if not satvis2_df.empty:
        print("\n── satvis2_df ──")
        print(satvis2_df.head())
        print(f"Shape: {satvis2_df.shape}")
        print(f"Columns: {list(satvis2_df.columns)}")
        satvis2_df.to_csv(OUT_SATVIS2, index=False)
        print(f"Saved → {OUT_SATVIS2}")

    # ── Scintillation summary JSON ─────────────────────────────────────
    from scintillation.scintillation_detector import summarise_results
    import json

    summary = summarise_results(scintillation_df, epoch_health_df, bestpos_df, range_df)
    OUT_SUMMARY = OUT_RANGE.replace("range_df.csv", "scintillation_summary.json")
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n" + "═" * 60)
    print("  SCINTILLATION ANALYSIS SUMMARY")
    print("═" * 60)
    print(f"  Answer    : {summary['answer']}")
    print(f"  Confidence: {summary['confidence_level']}")
    print(f"  Worst flag: {summary['worst_flag']}")
    print(f"  Reason    : {summary['reason']}")
    print("─" * 60)
    print("  EPOCH FLAGS")
    for k, v in summary.get("epoch_flags", {}).items():
        print(f"    {k:<22}: {v}")
    print("─" * 60)
    print("  PER-SIGNAL FLAGS (any epoch)")
    for k, v in summary.get("per_signal_flags", {}).items():
        print(f"    {k:<26}: {v}")
    print("─" * 60)
    print("  LOCATION")
    loc = summary.get("location_flags", {})
    print(f"    Zone        : {loc.get('zone')}")
    print(f"    Mean lat/lon: {loc.get('mean_latitude')}, {loc.get('mean_longitude')}")
    print(f"    region_flag : {loc.get('region_flag')}")
    print(f"    time_flag   : {loc.get('time_flag')}")
    print("─" * 60)
    print("  NOT YET EVALUATED")
    for s in summary.get("steps_not_evaluated", []):
        print(f"    • {s}")
    print("═" * 60)
    print(f"\nFull JSON summary saved → {OUT_SUMMARY}")
