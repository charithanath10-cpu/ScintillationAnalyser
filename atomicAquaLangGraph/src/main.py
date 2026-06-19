"""
main.py — NovAtel OEM7 log analyst + documentation Q&A.

Architecture
────────────
Log file questions  → Deterministic pipeline (config-driven, minimal LLM):
                        1. DeterministicMapper keyword match → log + field (NO LLM)
                        2. Python analysis (do_check_bit / do_analyze_field / do_summarize_log)
                        3. Fast formatting (templates for bit_check/numeric_stat, LLM only for raw_listing)
                      Falls back to LLM pipeline when confidence < 0.5:
                        1. LLM picks log from file inventory
                        2. Fetch live NovAtel docs
                        3. LLM extracts field/bit from docs
                        4. Python analysis
                        5. Format answer

Documentation Q&A   → LangGraph ReAct agent with kb_retriever + context_expander only
"""

from langgraph.errors import GraphRecursionError
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory.client import MemoryClient
from src.model.load import load_model
from src.evidence_planner import build_execution_plan
from src.correlation_orchestrator import execute_plan
from src.reasoning_layer import synthesize_response
from src.scintillation_handler import (
    is_scintillation_question,
    analyse_bytes as scint_analyse_bytes,
    build_llm_prompt as scint_build_prompt,
)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
import boto3
import base64
import os
import re
import io
import json
import time
import tempfile
import datetime
import contextvars
import pandas as pd
from collections import Counter, defaultdict
from botocore.config import Config as BotocoreConfig
from urllib.parse import urlparse

# ── GPS helpers ───────────────────────────────────────────────────────
_GPS_EPOCH    = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)
_LEAP_SECONDS = 18


def gps_to_utc(week: int, seconds: float) -> datetime.datetime:
    """Convert GPS week + seconds-of-week to UTC datetime."""
    return _GPS_EPOCH + datetime.timedelta(seconds=week * 604800 + seconds - _LEAP_SECONDS)


def gps_to_utc_str(week: int, seconds: float) -> str:
    """Return ISO-8601 UTC string for a GPS week/seconds pair."""
    if week <= 0:
        return ""
    return gps_to_utc(week, seconds).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ── Config ────────────────────────────────────────────────────────────
REGION          = "us-east-1"
MEMORY_ID       = os.getenv("MEMORY_ID")
S3_BUCKET       = os.getenv("S3_BUCKET")
KB_ID           = os.getenv("KB_ID", "FH00WKSBPL")
GUARDRAIL_ID    = os.getenv("GUARDRAIL_ID", "gcorc7d9sd08")
GUARDRAIL_VER   = os.getenv("GUARDRAIL_VERSION", "1")
ACTOR_ID        = "default-user"
SIZE_THRESHOLD  = 5 * 1024 * 1024
MAX_RESULTS     = int(os.getenv("MAX_RESULTS", "15"))
EXPANSION_PAGES = int(os.getenv("EXPANSION_PAGES", "2"))
_LLM_COLS       = {"element_id", "element_type", "content_markdown", "page_number"}

# BedrockAgentCoreApp is only needed when running as a standalone AgentCore deployment.
# When imported by Streamlit, instantiating it would attempt AWS service calls at
# import time and crash if AgentCore credentials are not configured.
# We defer construction to __main__ only.
_agentcore_app = None

def _get_agentcore_app():
    global _agentcore_app
    if _agentcore_app is None:
        _agentcore_app = BedrockAgentCoreApp()
    return _agentcore_app

# Compatibility shim so @app.entrypoint and app.run() still work
class _AppProxy:
    def entrypoint(self, fn):
        return _get_agentcore_app().entrypoint(fn)
    def run(self):
        return _get_agentcore_app().run()

app = _AppProxy()

# ── Status tracking for UI updates ───────────────────────────────────
_current_status: dict[str, str] = {}
_status_trail: dict[str, list[str]] = {}


def set_status(session_id: str, status: str):
    """Set current processing status for UI display."""
    _current_status[session_id] = status
    # Accumulate trail for response
    if session_id not in _status_trail:
        _status_trail[session_id] = []
    _status_trail[session_id].append(status)
    print(f"[STATUS] {session_id}: {status}")


def get_status(session_id: str) -> str:
    """Get current processing status."""
    return _current_status.get(session_id, "")


def clear_status(session_id: str):
    """Clear status after completion."""
    _current_status.pop(session_id, None)


def get_and_clear_status_trail(session_id: str) -> list[str]:
    """Get accumulated status trail and clear it."""
    trail = _status_trail.pop(session_id, [])
    return trail


# ── Lazy singletons ───────────────────────────────────────────────────
_llm = _memory_client = _s3_client = _kb_client = _bedrock_runtime = None
_BOTO_CONFIG = BotocoreConfig(read_timeout=300)
_gnss_kb = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = load_model()
    return _llm


def get_gnss_kb():
    """Load GNSS knowledge base (79KB markdown) for LLM context."""
    global _gnss_kb
    if _gnss_kb is None:
        try:
            kb_path = "gnss_knowledge_base.md"
            with open(kb_path, 'r', encoding='utf-8') as f:
                _gnss_kb = f.read()
            print(f"[KB] Loaded GNSS knowledge base: {len(_gnss_kb)} chars")
        except FileNotFoundError:
            print("[KB] Warning: gnss_knowledge_base.md not found, using empty KB")
            _gnss_kb = ""
        except Exception as e:
            print(f"[KB] Error loading knowledge base: {e}")
            _gnss_kb = ""
    return _gnss_kb


def get_memory_client():
    global _memory_client
    if _memory_client is None:
        _memory_client = MemoryClient(region_name=REGION)
    return _memory_client


def save_to_memory(session_id: str, user_msg: str, assistant_msg: str):
    """Save a conversation turn to Bedrock AgentCore memory."""
    if not MEMORY_ID:
        return
    try:
        get_memory_client().create_event(
            memory_id=MEMORY_ID, actor_id=ACTOR_ID, session_id=session_id,
            messages=[(user_msg, "USER"), (assistant_msg, "ASSISTANT")],
        )
    except Exception as e:
        print(f"[MEMORY] save error: {e}")


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name="ap-south-1", config=_BOTO_CONFIG)
    return _s3_client


def get_kb_client():
    global _kb_client
    if _kb_client is None:
        _kb_client = boto3.client("bedrock-agent-runtime", region_name="us-west-2", config=_BOTO_CONFIG)
    return _kb_client


def get_bedrock_runtime():
    global _bedrock_runtime
    if _bedrock_runtime is None:
        _bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION, config=_BOTO_CONFIG)
    return _bedrock_runtime


# Separate client for guardrail (may be in a different region than inference)
_guardrail_runtime = None
_GUARDRAIL_REGION = "us-west-2"


def _get_guardrail_runtime():
    global _guardrail_runtime
    if _guardrail_runtime is None:
        _guardrail_runtime = boto3.client("bedrock-runtime", region_name=_GUARDRAIL_REGION, config=_BOTO_CONFIG)
    return _guardrail_runtime


# ── Guardrail ─────────────────────────────────────────────────────────
def apply_guardrail(text: str, source: str = "INPUT") -> str:
    _gid = GUARDRAIL_ID.strip() if GUARDRAIL_ID else ""
    if not _gid or len(_gid) < 3:
        return text
    try:
        resp = _get_guardrail_runtime().apply_guardrail(
            guardrailIdentifier=_gid,
            guardrailVersion=GUARDRAIL_VER,
            source=source,
            content=[{"text": {"text": text}}],
        )
        if resp["action"] == "GUARDRAIL_INTERVENED":
            blocked = resp.get("outputs", [{}])[0].get("text", "Content blocked by guardrail.")
            raise ValueError(blocked)
    except ValueError:
        raise
    except Exception as e:
        print(f"[GUARDRAIL] disabled — call failed: {e}")
    return text
    return text


# ── KB helpers ────────────────────────────────────────────────────────
_tool_call_log: list[dict] = []
_csv_cache: dict[str, pd.DataFrame] = {}


def _download_and_parse_key(bucket: str, key: str) -> pd.DataFrame:
    with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as tmp:
        get_s3_client().download_fileobj(bucket, key, tmp)
        tmp.flush()
        tmp_path = tmp.name
    try:
        with open(tmp_path, "r", encoding="utf-8") as f:
            raw = f.read()
        try:
            data = json.loads(raw)
            rows = [e["contentMetadata"] for e in data.get("fileContents", []) if "contentMetadata" in e]
            df = pd.DataFrame(rows)
        except (json.JSONDecodeError, KeyError):
            df = pd.read_csv(io.StringIO(raw))
    finally:
        os.unlink(tmp_path)
    return df


def _download_and_parse(source_uri: str) -> pd.DataFrame:
    if source_uri in _csv_cache:
        return _csv_cache[source_uri]
    parsed = urlparse(source_uri)
    bucket = parsed.netloc
    key    = parsed.path.lstrip("/")
    df = _download_and_parse_key(bucket, key)
    if "element_id" not in df.columns and not key.startswith("Output/"):
        df = _download_and_parse_key(bucket, f"Output/{key}")
    if "page_number" in df.columns:
        df["page_number"] = pd.to_numeric(df["page_number"], errors="coerce").fillna(0).astype(int)
    _csv_cache[source_uri] = df
    return df


def _resolve_data_uri(source_uri: str) -> str:
    if not source_uri.lower().endswith(".pdf"):
        return source_uri
    for entry in reversed(_tool_call_log):
        if entry.get("tool") != "kb_retriever":
            continue
        for el in entry["result"].get("elements", []):
            if el.get("source_uri") == source_uri and el.get("csv_source_uri"):
                return el["csv_source_uri"]
    raise ValueError(f"Cannot resolve data URI from PDF path: {source_uri}")


# ── NovAtel ASCII log parser ──────────────────────────────────────────
_log_store: dict[str, dict] = {}

# ── Scintillation: raw file bytes kept per session (no disk I/O) ──────
# Populated by ingest_log_file; consumed by run_scintillation_analysis.
_scint_bytes_store: dict[str, bytes] = {}
# For large S3 files, store the key instead of bytes to avoid OOM.
_scint_s3_key_store: dict[str, str] = {}

_ASCII_FULL_RE = re.compile(
    r"^#(?P<log_name>[A-Z0-9_]+),"
    r"(?P<header>[^;]*);"
    r"(?P<fields>.*?)"
    r"(?:\*[0-9a-fA-F]{1,8})?\s*$"
)


def _parse_line(line: str) -> dict | None:
    m = _ASCII_FULL_RE.match(line.strip())
    if not m:
        return None
    g = m.groupdict()
    h = [p.strip() for p in g["header"].split(",")]

    def _get(i, d=""):
        return h[i] if i < len(h) else d

    def _tryf(v, d=0.0):
        try:
            return float(v)
        except Exception:
            return d

    def _tryi(v, d=0):
        try:
            return int(v)
        except Exception:
            return d

    log_name   = g["log_name"]
    normalized = log_name[:-1] if (log_name.endswith("A") and len(log_name) > 4) else log_name
    week       = _tryi(_get(4))
    seconds    = _tryf(_get(5))

    return {
        "log_name":     normalized,
        "log_name_raw": log_name,
        "port":         _get(0),
        "seq":          _tryi(_get(1)),
        "idle_pct":     _tryf(_get(2)),
        "time_status":  _get(3),
        "week":         week,
        "seconds":      seconds,
        "utc_time":     gps_to_utc_str(week, seconds),
        "rx_status":    _get(6),
        "fields_raw":   g["fields"],
    }


def parse_novatel_ascii(text: str) -> pd.DataFrame:
    records, skipped = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        rec = _parse_line(line)
        if rec:
            records.append(rec)
        else:
            skipped += 1
    print(f"[PARSE] matched={len(records)} skipped={skipped}")
    return pd.DataFrame(records) if records else pd.DataFrame()


# ── RXSTATUS bit decoder ──────────────────────────────────────────────
_RXSTATUS_BITS = {
    0:  "Error flag",
    1:  "Temperature status warning",
    2:  "Voltage supply status warning",
    3:  "Primary antenna not powered",
    4:  "LNA failure",
    5:  "Primary antenna open circuit",
    6:  "Primary antenna short circuit",
    7:  "CPU overload",
    8:  "COM port transmit buffer overrun",
    9:  "Spoofing detected",
    11: "Link overrun",
    12: "Input overrun",
    13: "Aux transmit overrun",
    14: "Antenna gain out of range",
    15: "Jammer detected",
    16: "INS reset",
    17: "IMU communication failure",
    18: "GPS almanac / UTC invalid",
    19: "Position solution invalid",
    20: "Position fixed",
    21: "Clock steering disabled",
    22: "Clock model invalid",
    23: "External oscillator locked",
    24: "Software resource warning",
    25: "Version bit 0",
    26: "Version bit 1",
    27: "HDR tracking mode",
    28: "Digital filtering enabled",
    29: "Auxiliary 3 status event",
    30: "Auxiliary 2 status event",
    31: "Auxiliary 1 status event",
}


def decode_rxstatus(hex_str: str) -> dict:
    """Decode an RXSTATUS hex word."""
    try:
        val = int(hex_str.strip(), 16)
    except (ValueError, AttributeError):
        return {"raw_hex": hex_str, "set_bits": [], "decode_error": True}

    set_bits = []
    for bit, name in _RXSTATUS_BITS.items():
        if val & (1 << bit):
            set_bits.append({"bit": bit, "name": name})

    return {
        "raw_hex":            hex_str.strip(),
        "set_bits":           set_bits,
        "error_flag":         bool(val & (1 << 0)),
        "spoofing_detected":  bool(val & (1 << 9)),
        "jamming_detected":   bool(val & (1 << 15)),
        "antenna_open":       bool(val & (1 << 5)),
        "antenna_shorted":    bool(val & (1 << 6)),
        "position_invalid":   bool(val & (1 << 19)),
    }


# ── AUX4 status bit decoder ──────────────────────────────────────────
def decode_aux4_tracking(hex_str: str) -> dict:
    """Decode AUX4 status word for satellite tracking flags."""
    try:
        val = int(hex_str.strip(), 16)
    except (ValueError, AttributeError):
        return {"tracking_degraded": False, "tracking_critical": False, "decode_error": True}
    return {
        "tracking_degraded": bool(val & (1 << 0)),
        "tracking_critical": bool(val & (1 << 1)),
    }


# ── ITDETECTSTATUS ASCII parser ───────────────────────────────────────
_ITDETECT_FIELDS_PER_ENTRY = 9


def decode_itdetectstatus(payload: str) -> dict:
    """Parse the semicolon-payload of an ITDETECTSTATUS ASCII log line."""
    parts = [p.strip() for p in payload.split(",")]
    try:
        num_entries = int(parts[0])
    except (ValueError, IndexError):
        return {"payload": payload, "decode_error": True}

    entries = []
    for i in range(num_entries):
        base = 1 + i * _ITDETECT_FIELDS_PER_ENTRY
        if base + _ITDETECT_FIELDS_PER_ENTRY - 1 >= len(parts):
            break
        rf_path     = parts[base]
        detect_type = parts[base + 1]
        entry = {"rf_path": rf_path, "detect_type": detect_type}
        if detect_type == "SPECTRUMANALYSIS":
            try:
                entry["center_freq_mhz"] = float(parts[base + 2])
                entry["bandwidth_mhz"]   = float(parts[base + 3])
                entry["power_dbm"]       = float(parts[base + 4])
                entry["peak_psd_dbm_hz"] = float(parts[base + 5])
            except ValueError:
                entry["param_parse_error"] = True
        entries.append(entry)

    return {
        "num_entries": num_entries,
        "entries":     entries,
        "has_spectrum_interference":     any(e["detect_type"] == "SPECTRUMANALYSIS" for e in entries),
        "has_statistical_interference":  any(e["detect_type"] == "STATISTICALANALYSIS" for e in entries),
    }


# ── BESTPOS solution type parser ──────────────────────────────────────
def decode_bestpos_fields(fields_raw: str) -> dict:
    """Extract sol_status and pos_type from BESTPOS fields."""
    parts = [p.strip() for p in fields_raw.split(",")]
    return {
        "sol_status": parts[0] if len(parts) > 0 else "",
        "pos_type":   parts[1] if len(parts) > 1 else "",
        "num_svs":    int(parts[11]) if len(parts) > 11 else None,
    }


def _summarize_log(df: pd.DataFrame, filename: str) -> str:
    if df.empty:
        return f"Uploaded file '{filename}' had no parseable NovAtel ASCII log lines."
    log_counts = Counter(df["log_name_raw"])
    top_logs   = ", ".join(f"{n}({c})" for n, c in log_counts.most_common(10))
    VALID_TIME = {"FINESTEERING", "FINE", "FINEBACKUPSTEERING", "FINEADJUSTING",
                  "COARSE", "COARSESTEERING", "COARSEADJUSTING", "FREEWHEELING"}
    valid = df[df["time_status"].isin(VALID_TIME) & (df["week"] > 0)]
    parts = [f"Log '{filename}': {len(df)} records, {len(log_counts)} distinct log types.",
             f"Top log types: {top_logs}."]
    if not valid.empty:
        weeks   = sorted(valid["week"].unique().tolist())
        t_start = valid["seconds"].min()
        t_end   = valid["seconds"].max()
        w_start = int(valid.loc[valid["seconds"].idxmin(), "week"])
        w_end   = int(valid.loc[valid["seconds"].idxmax(), "week"])
        dur     = (weeks[-1] - weeks[0]) * 604800 + (t_end - t_start) if len(weeks) > 1 else t_end - t_start
        parts.append(
            f"File time range: {gps_to_utc_str(w_start, t_start)} to "
            f"{gps_to_utc_str(w_end, t_end)} (duration {dur:.1f}s = {dur/60:.2f} min)."
        )
    return " ".join(parts)


def _build_event_index(df: pd.DataFrame) -> dict:
    """Pre-compute structured event lists from RXSTATUS and ITDETECTSTATUS."""
    events: dict[str, list] = {
        "spoofing": [], "jamming": [], "antenna_open": [], "antenna_shorted": [],
        "position_invalid": [], "tracking_degraded": [], "tracking_critical": [],
        "itdetect_interference": [],
    }

    rxs = df[df["log_name"] == "RXSTATUS"].copy()
    for _, row in rxs.iterrows():
        decoded = decode_rxstatus(row.get("rx_status", ""))
        ts   = row.get("utc_time", "") or f"GPS {row['week']}w {row['seconds']:.3f}s"
        week = int(row["week"])
        sow  = row["seconds"]
        base = {"utc_time": ts, "week": week, "seconds": sow,
                "raw_hex": decoded.get("raw_hex", ""), "set_bits": decoded.get("set_bits", [])}
        if decoded.get("spoofing_detected"):  events["spoofing"].append(base)
        if decoded.get("jamming_detected"):   events["jamming"].append(base)
        if decoded.get("antenna_open"):       events["antenna_open"].append(base)
        if decoded.get("antenna_shorted"):    events["antenna_shorted"].append(base)
        if decoded.get("position_invalid"):   events["position_invalid"].append(base)

        fields = [f.strip() for f in row.get("fields_raw", "").split(",")]
        if len(fields) > 16:
            aux4 = decode_aux4_tracking(fields[16])
            if aux4.get("tracking_degraded"): events["tracking_degraded"].append(base)
            if aux4.get("tracking_critical"): events["tracking_critical"].append(base)

    itd = df[df["log_name"].isin(["ITDETECTSTATUS", "ITDETECTSTAT"])].copy()
    for _, row in itd.iterrows():
        decoded = decode_itdetectstatus(row.get("fields_raw", ""))
        if decoded.get("decode_error"):
            continue
        ts   = row.get("utc_time", "") or f"GPS {row['week']}w {row['seconds']:.3f}s"
        week = int(row["week"])
        sow  = row["seconds"]
        for entry in decoded.get("entries", []):
            event = {"utc_time": ts, "week": week, "seconds": sow,
                     "rf_path": entry.get("rf_path", ""), "detect_type": entry.get("detect_type", "")}
            if entry.get("detect_type") == "SPECTRUMANALYSIS":
                event["center_freq_mhz"] = entry.get("center_freq_mhz")
                event["bandwidth_mhz"]   = entry.get("bandwidth_mhz")
                event["power_dbm"]       = entry.get("power_dbm")
                event["peak_psd_dbm_hz"] = entry.get("peak_psd_dbm_hz")
            events["itdetect_interference"].append(event)

    return events


def ingest_log_file(file_bytes: bytes, filename: str, session_id: str) -> dict:
    t0   = time.time()
    text = file_bytes.decode("utf-8", errors="replace")
    df   = parse_novatel_ascii(text)
    del text  # free the decoded string — DataFrame has what we need
    summary = _summarize_log(df, filename)
    events  = _build_event_index(df)
    _log_store[session_id] = {"df": df, "summary": summary, "filename": filename, "events": events}
    # Only keep raw bytes for small files — large files (>5 MB) use S3 key path
    # and set _scint_bytes_store themselves (or use _scint_s3_key_store).
    if len(file_bytes) <= SIZE_THRESHOLD:
        _scint_bytes_store[session_id] = file_bytes
    # Clear docs cache on new file upload
    _docs_cache.clear()
    print(f"[INGEST] {filename} parsed {len(df)} records session={session_id} took={time.time()-t0:.2f}s")
    return {"filename": filename, "records": len(df),
            "log_types": int(df["log_name"].nunique()) if not df.empty else 0,
            "summary": summary}


# ── Per-request session context ───────────────────────────────────────
_current_session_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_session_var", default=""
)


def _get_session_entry() -> dict | None:
    """Return the _log_store entry for the current request's session."""
    return _log_store.get(_current_session_var.get(""))


# ── Jamming/Spoofing event merger ─────────────────────────────────────
def _merge_jamming_events(rxstatus_events: list, itdetect_events: list) -> list:
    """Merge RXSTATUS and ITDETECTSTATUS events sharing the same GPS timestamp."""
    merged: dict[tuple, dict] = {}
    for ev in rxstatus_events:
        key = (int(ev.get("week", 0)), float(ev.get("seconds", 0.0)))
        if key not in merged:
            merged[key] = {"utc_time": ev.get("utc_time", ""), "week": key[0], "seconds": key[1],
                           "sources": [], "rxstatus_bits": [], "itdetect_entries": []}
        if "rxstatus" not in merged[key]["sources"]:
            merged[key]["sources"].append("rxstatus")
        merged[key]["rxstatus_bits"].extend(ev.get("set_bits", []))
    for ev in itdetect_events:
        key = (int(ev.get("week", 0)), float(ev.get("seconds", 0.0)))
        if key not in merged:
            merged[key] = {"utc_time": ev.get("utc_time", ""), "week": key[0], "seconds": key[1],
                           "sources": [], "rxstatus_bits": [], "itdetect_entries": []}
        if "itdetectstatus" not in merged[key]["sources"]:
            merged[key]["sources"].append("itdetectstatus")
        entry = {"rf_path": ev.get("rf_path", ""), "detect_type": ev.get("detect_type", "")}
        if ev.get("detect_type") == "SPECTRUMANALYSIS":
            for f in ("center_freq_mhz", "bandwidth_mhz", "power_dbm", "peak_psd_dbm_hz"):
                if f in ev:
                    entry[f] = ev[f]
        merged[key]["itdetect_entries"].append(entry)
    return sorted(merged.values(), key=lambda e: (e["week"], e["seconds"]))


# ── Field index conversion ────────────────────────────────────────────
def _doc_field_to_body_index(field_index: int) -> int:
    """
    NovAtel docs: fields are 1-based, header = field 1, first body field = field 2.
    Our fields_raw list is 0-based starting from body field 2.
    So: body_index = doc_field_index - 2.
    """
    return (field_index - 2) if field_index >= 2 else field_index


# ── Core analysis functions (deterministic, no agent) ─────────────────

def _safe_parse_hex(fv: str) -> int | None:
    fv = fv.strip()
    try:
        return int(fv, 16)
    except (ValueError, TypeError):
        try:
            return int(fv)
        except (ValueError, TypeError):
            return None


def do_check_bit(session_id: str, log_name: str, field_index: int,
                 bit_position: int, time_from: float = None,
                 time_to: float = None, max_results: int = 1000) -> dict:
    """Check which records have a specific bit set in a specific field."""
    entry = _log_store.get(session_id)
    if not entry:
        return {"status": "error", "error": "No log file uploaded."}
    df = entry["df"]

    if log_name.upper().endswith("A") and len(log_name) > 4:
        log_name = log_name[:-1]

    filtered = df[df["log_name"].str.upper() == log_name.upper()]
    if time_from is not None:
        filtered = filtered[filtered["seconds"] >= time_from]
    if time_to is not None:
        filtered = filtered[filtered["seconds"] <= time_to]

    if filtered.empty:
        return {"status": "success", "log_name": log_name, "total_checked": 0,
                "matches_found": 0, "records_with_bit_set": [],
                "note": f"No {log_name} records found in the file."}

    body_index = _doc_field_to_body_index(field_index)
    mask    = 1 << bit_position
    matches = []
    errors  = 0
    checked = 0

    for _, row in filtered.iterrows():
        fields = [f.strip() for f in row.get("fields_raw", "").split(",")]
        if body_index >= len(fields):
            errors += 1
            continue
        val = _safe_parse_hex(fields[body_index])
        if val is None:
            errors += 1
            continue
        checked += 1
        if val & mask:
            if len(matches) < max_results:
                matches.append({
                    "utc_time":        row.get("utc_time", ""),
                    "gps_week":        int(row["week"]),
                    "gps_seconds":     float(row["seconds"]),
                    "field_value_hex": hex(val),
                })

    print(f"[CHECK_BIT] log={log_name} field={field_index} bit={bit_position} "
          f"total={len(filtered)} checked={checked} matches={len(matches)} errors={errors}")
    return {
        "status": "success", "log_name": log_name,
        "doc_field_index": field_index, "body_index_used": body_index,
        "bit_position": bit_position, "bit_mask_hex": hex(mask),
        "total_checked": checked, "matches_found": len(matches),
        "parse_errors": errors, "records_with_bit_set": matches,
    }


def do_analyze_field(session_id: str, log_name: str, field_index: int) -> dict:
    """Compute min/max/avg for a numeric field."""
    entry = _log_store.get(session_id)
    if not entry:
        return {"status": "error", "error": "No log file uploaded."}
    df = entry["df"]

    if log_name.upper().endswith("A") and len(log_name) > 4:
        log_name = log_name[:-1]

    filtered = df[df["log_name"].str.upper() == log_name.upper()]
    if filtered.empty:
        return {"status": "error", "error": f"No {log_name} records found."}

    body_index = _doc_field_to_body_index(field_index)
    values, recs = [], []
    for _, row in filtered.iterrows():
        fields = [f.strip() for f in row.get("fields_raw", "").split(",")]
        if body_index >= len(fields):
            continue
        try:
            val = float(fields[body_index])
            values.append(val)
            recs.append({"value": val, "utc_time": row.get("utc_time", ""),
                         "seconds": row["seconds"], "week": int(row["week"])})
        except (ValueError, TypeError):
            continue

    if not values:
        return {"status": "error", "error": f"No numeric values at field {field_index} of {log_name}."}

    min_val = min(values)
    max_val = max(values)
    return {
        "status": "success", "log_name": log_name,
        "doc_field_index": field_index, "body_index_used": body_index,
        "total_records": len(filtered), "valid_values": len(values),
        "min_value": min_val, "max_value": max_val,
        "average_value": sum(values) / len(values), "range": max_val - min_val,
        "min_occurred_at": next(r for r in recs if r["value"] == min_val),
        "max_occurred_at": next(r for r in recs if r["value"] == max_val),
    }


def do_summarize_log(session_id: str, log_name: str,
                     question: str, limit: int = None) -> dict:
    """Return records from a log for LLM interpretation."""
    entry = _log_store.get(session_id)
    if not entry:
        return {"status": "error", "error": "No log file uploaded."}
    df = entry["df"]

    norm = log_name[:-1] if (log_name.upper().endswith("A") and len(log_name) > 4) else log_name
    filtered = df[df["log_name"].str.upper() == norm.upper()]
    if filtered.empty:
        return {"status": "error", "error": f"No {log_name} records found in the file."}

    total = len(filtered)
    if limit and total > limit:
        step = total // limit
        sample = filtered.iloc[::step].head(limit)
    else:
        sample = filtered

    records = []
    for _, row in sample.iterrows():
        fields_parsed = [f.strip() for f in row.get("fields_raw", "").split(",")]
        records.append({
            "utc_time": row.get("utc_time", ""), "week": int(row["week"]),
            "seconds": float(row["seconds"]), "rx_status": row.get("rx_status", ""),
            "fields_parsed": fields_parsed,
        })

    return {"status": "success", "log_name": log_name, "total_records": total,
            "sample_size": len(records), "records": records, "question": question}


# ── Subject extractor ────────────────────────────────────────────────
_SUBJECT_PROMPT = """Extract the core technical subject from the user's question.
Return ONLY 1-3 words that name the phenomenon, measurement, or event being asked about.
No sentences. No explanation. Just the subject words.

Examples:
  "do we have spoofing in this file"  → spoofing detection
  "identify interference events"       → interference detection
  "what is the maximum height"         → height maximum
  "show me jamming records"            → jamming detection

Question: {question}"""


def extract_subject(question: str) -> str:
    """Extract the core subject from a user question."""
    try:
        response = get_llm().invoke([HumanMessage(
            content=_SUBJECT_PROMPT.format(question=question)
        )])
        subject = response.content.strip().lower().split("\n")[0].strip("\"'.,")
        print(f"[SUBJECT] '{question}' → '{subject}'")
        return subject
    except Exception as e:
        print(f"[SUBJECT] fallback: {e}")
        filler = {"identify", "find", "show", "list", "check", "detect", "any", "all",
                  "in", "this", "file", "the", "is", "are", "there", "do", "we", "have",
                  "me", "a", "an", "of", "for", "from", "what", "how", "when", "records"}
        words = [w for w in question.lower().split() if w not in filler]
        return " ".join(words[:3]) or question


# ── KB search (pure Python, no agent) ────────────────────────────────
def kb_search(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    t0 = time.time()
    try:
        response = get_kb_client().retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": max_results}},
        )
        elements = []
        for result in response.get("retrievalResults", []):
            content  = result.get("content", {}).get("text", "")
            metadata = result.get("metadata", {})
            elements.append({
                "element_id":       metadata.get("element_id", ""),
                "content_markdown": content,
                "page_number":      int(metadata.get("page_number", 0)),
                "score":            result.get("score", 0.0),
                "source_uri":       metadata.get("x-amz-bedrock-kb-source-uri", ""),
                "csv_source_uri":   metadata.get("csv_source_uri", ""),
            })
        print(f"[KB] query='{query}' results={len(elements)} took={time.time()-t0:.2f}s")
        return elements
    except Exception as e:
        print(f"[KB] error: {e}")
        return []


# ── NovAtel live docs fetcher ─────────────────────────────────────────
import urllib.request
from html.parser import HTMLParser


class _TableTextExtractor(HTMLParser):
    """Extract plain text from HTML, preserving table row structure."""
    def __init__(self):
        super().__init__()
        self.rows: list[str] = []
        self._cell_texts: list[str] = []
        self._current: list[str] = []
        self._in_cell = False
        self._skip_tags = {"script", "style", "nav", "header", "footer"}
        self._skip = False
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True
            self._skip_depth = 0
        if self._skip:
            self._skip_depth += 1
            return
        if tag in ("td", "th"):
            self._in_cell = True
            self._current = []

    def handle_endtag(self, tag):
        if self._skip:
            self._skip_depth -= 1
            if self._skip_depth <= 0:
                self._skip = False
            return
        if tag in ("td", "th"):
            self._in_cell = False
            self._cell_texts.append(" ".join(self._current).strip())
        if tag == "tr":
            if self._cell_texts:
                self.rows.append(" | ".join(self._cell_texts))
            self._cell_texts = []

    def handle_data(self, data):
        if self._skip or not self._in_cell:
            return
        text = data.strip()
        if text:
            self._current.append(text)


_docs_cache: dict[str, str] = {}


def fetch_novatel_log_docs(log_name: str) -> str:
    """Fetch live NovAtel OEM7 documentation page for a log. Cached per session."""
    if log_name in _docs_cache:
        return _docs_cache[log_name]

    url_name = log_name[:-1] if (log_name.upper().endswith("A") and len(log_name) > 4) else log_name
    url = f"https://docs.novatel.com/OEM7/Content/Logs/{url_name}.htm"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 NovAtelAgent/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        parser = _TableTextExtractor()
        parser.feed(html)
        useful = [r for r in parser.rows if r.strip() and len(r) > 10]
        result = "\n".join(useful)
        _docs_cache[log_name] = result
        print(f"[DOCS] Fetched {url_name} docs: {len(useful)} table rows took={time.time()-t0:.2f}s")
        return result
    except Exception as e:
        print(f"[DOCS] Could not fetch {url}: {e}")
        return ""


# ── Param extraction (one LLM call → structured JSON) ─────────────────
_EXTRACT_PROMPT = """You are a NovAtel OEM7 documentation parser with expertise in all receiver logs.

You are given the OFFICIAL NovAtel documentation table for the log, plus supplementary KB excerpts.
Extract the exact field and bit that answers the user's question.
Output ONLY a single JSON object. No explanation. No markdown. No extra text.

JSON fields:
  log_name      — use exactly: {log_name}
  field_index   — the field NUMBER from the left column of the NovAtel field table (integer, 1-based, header=field 1)
  bit_position  — bit number (0=LSB) from the bit table. Use null if not a flag/event question.
  question_type — classify the question as exactly one of:
    "bit_check"   : looking for whether a specific bit is set
    "numeric_stat": asking for min/max/average/range of a MEASURED physical value
    "raw_listing" : everything else

CRITICAL RULES:
1. ALWAYS prefer the OFFICIAL DOCS over KB excerpts.
2. field_index is the exact integer in the leftmost column of the field table (1-based).
3. For bit questions, ALWAYS provide bit_position as an integer, never null.
4. Respond with ONLY valid JSON.

Log: {log_name}
Question: {question}

OFFICIAL NOVATEL DOCUMENTATION:
{official_docs}

SUPPLEMENTARY KB EXCERPTS:
{kb_content}"""


def extract_log_params(question: str, kb_elements: list[dict],
                       log_name: str = None, official_docs: str = "",
                       top_n: int = 8) -> dict | None:
    """One LLM call to extract log/field/bit params."""
    kb_content = "\n\n---\n\n".join(
        f"[Score: {el['score']:.3f}]\n{el['content_markdown']}"
        for el in kb_elements[:top_n]
    ) if kb_elements else "No KB results."

    if official_docs:
        doc_lines = official_docs.split('\n')
        table_lines = [line for line in doc_lines if '|' in line and len(line) > 20]
        docs_excerpt = '\n'.join(table_lines[:150])
        if not docs_excerpt:
            docs_excerpt = official_docs[:4000]
    else:
        docs_excerpt = "Not available — rely on KB excerpts."

    prompt = _EXTRACT_PROMPT.format(
        log_name=log_name or "unknown", question=question,
        official_docs=docs_excerpt, kb_content=kb_content,
    )

    response = None
    try:
        response = get_llm().invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        params = json.loads(raw)
        if log_name and not params.get("log_name"):
            params["log_name"] = log_name
        print(f"[EXTRACT] ✓ log={params.get('log_name')} field={params.get('field_index')} "
              f"bit={params.get('bit_position')} type={params.get('question_type')}")
        return params
    except Exception as e:
        raw_out = response.content[:300] if response else "no response"
        print(f"[EXTRACT] failed: {e} raw={raw_out}")
        return None


# ── FAST DETERMINISTIC FORMATTER (NO LLM) ────────────────────────────
def format_answer_deterministic(question: str, tool_result: dict, intent: dict) -> str:
    """Ultra-fast answer formatting WITHOUT LLM for deterministic queries."""
    analysis_type = intent.get('analysis_type')
    log_name = tool_result.get('log_name', intent.get('log_type', 'unknown'))

    if analysis_type == 'bit_check':
        matches = tool_result.get('matches_found', 0)
        total = tool_result.get('total_checked', 0)
        bit_pos = tool_result.get('bit_position', 0)
        field_idx = tool_result.get('doc_field_index', 0)

        if matches == 0:
            result = f"✅ **No {intent.get('description', 'events')} detected.**\n\n"
            result += f"**Analysis details:**\n"
            result += f"- **Log analyzed:** `{log_name}`\n"
            result += f"- **Field:** {field_idx} (body index {tool_result.get('body_index_used', '?')})\n"
            result += f"- **Bit checked:** {bit_pos} (mask: {tool_result.get('bit_mask_hex', '?')})\n"
            result += f"- **Records checked:** {total:,}\n\n"
            result += "The receiver did not flag this condition during the observation period."
        else:
            records = tool_result.get('records_with_bit_set', [])
            result = f"⚠️ **{intent.get('description', 'Events')} detected in {matches:,} of {total:,} records.**\n\n"
            result += f"**Analysis details:**\n"
            result += f"- **Log analyzed:** `{log_name}`\n"
            result += f"- **Field:** {field_idx} (body index {tool_result.get('body_index_used', '?')})\n"
            result += f"- **Bit checked:** {bit_pos} (mask: {tool_result.get('bit_mask_hex', '?')})\n"
            result += f"- **Records checked:** {total:,}\n"
            if tool_result.get('parse_errors', 0) > 0:
                result += f"- **Parse errors:** {tool_result['parse_errors']}\n"
            result += "\n"
            if matches <= 10:
                result += "**All occurrences:**\n\n"
                for rec in records[:10]:
                    result += f"- {rec.get('utc_time', 'N/A')} (GPS Week {rec.get('gps_week', 0)}, {rec.get('gps_seconds', 0):.1f}s) — value: {rec.get('field_value_hex', '?')}\n"
            else:
                result += f"**Sample occurrences (showing first 10 of {matches}):**\n\n"
                for rec in records[:10]:
                    result += f"- {rec.get('utc_time', 'N/A')} — value: {rec.get('field_value_hex', '?')}\n"
                result += f"\n*...and {matches - 10} more occurrences*\n"
        return result

    elif analysis_type == 'numeric_stat':
        min_val = tool_result.get('min_value', 0)
        max_val = tool_result.get('max_value', 0)
        avg_val = tool_result.get('average_value', 0)
        range_val = tool_result.get('range', 0)
        total = tool_result.get('total_records', 0)
        valid = tool_result.get('valid_values', 0)
        field_idx = tool_result.get('doc_field_index', 0)
        unit = intent.get('unit', '')
        min_time = tool_result.get('min_occurred_at', {}).get('utc_time', 'N/A')
        max_time = tool_result.get('max_occurred_at', {}).get('utc_time', 'N/A')

        result = f"**{intent.get('description', 'Statistics')}**\n\n"
        result += f"**Analysis details:**\n"
        result += f"- **Log analyzed:** `{log_name}`\n"
        result += f"- **Field:** {field_idx} (body index {tool_result.get('body_index_used', '?')})\n"
        result += f"- **Records in file:** {total:,}\n"
        result += f"- **Valid numeric values:** {valid:,}\n\n"
        result += "| Metric | Value | Timestamp (UTC) |\n"
        result += "|--------|-------|----------------|\n"
        result += f"| **Minimum** | {min_val:.3f} {unit} | {min_time} |\n"
        result += f"| **Maximum** | {max_val:.3f} {unit} | {max_time} |\n"
        result += f"| **Average** | {avg_val:.3f} {unit} | - |\n"
        result += f"| **Range** | {range_val:.3f} {unit} | - |\n"
        return result

    else:
        return None  # Signal to use LLM path


# ── FAST INTERFERENCE FORMATTER (NO LLM) ──────────────────────────────
def format_interference_analysis(question: str, tool_result: dict, intent: dict) -> str:
    """Ultra-fast interference analysis formatting WITHOUT LLM."""
    log_name = tool_result.get('log_name', 'ITDETECTSTATUS')
    total_records = tool_result.get('total_records', 0)
    sample_size = tool_result.get('sample_size', 0)
    records = tool_result.get('records', [])

    if total_records == 0:
        return f"✅ **No interference detected.**\n\nNo {log_name} records found in this file."

    interference_count = 0
    rf_paths = {}
    detection_types = {}
    freq_min, freq_max = float('inf'), float('-inf')
    power_min, power_max = float('inf'), float('-inf')
    timestamps = []

    for rec in records:
        fields = rec.get('fields_parsed', [])
        utc_time = rec.get('utc_time', 'N/A')
        if len(fields) > 0:
            try:
                num_entries = int(fields[0]) if fields[0] else 0
                if num_entries > 0:
                    interference_count += 1
                    timestamps.append(utc_time)
                    if len(fields) >= 5:
                        rf_path = fields[1] if len(fields) > 1 else 'unknown'
                        detection_type = fields[2] if len(fields) > 2 else 'unknown'
                        center_freq = float(fields[3]) if len(fields) > 3 and fields[3] else 0
                        power = float(fields[5]) if len(fields) > 5 and fields[5] else 0
                        rf_paths[rf_path] = rf_paths.get(rf_path, 0) + 1
                        detection_types[detection_type] = detection_types.get(detection_type, 0) + 1
                        if center_freq > 0:
                            freq_min = min(freq_min, center_freq)
                            freq_max = max(freq_max, center_freq)
                        if power != 0:
                            power_min = min(power_min, power)
                            power_max = max(power_max, power)
            except (ValueError, IndexError):
                pass

    if interference_count == 0:
        return f"✅ **No interference detected in this file.**\n\nAnalyzed all {total_records:,} {log_name} records."

    pct = (interference_count / sample_size * 100) if sample_size > 0 else 0
    is_full = (sample_size == total_records)

    result = f"⚠️ **Interference detected — {interference_count:,} of {sample_size:,} records ({pct:.0f}%) contain active interference.**\n\n"

    if timestamps:
        result += f"**Time range:** {timestamps[0]} to {timestamps[-1]}\n\n"
    if rf_paths:
        result += "**RF Paths Affected:**\n"
        for path, count in sorted(rf_paths.items(), key=lambda x: -x[1]):
            result += f"- {path}: {count} occurrences\n"
        result += "\n"
    if detection_types:
        result += "**Detection Methods:**\n"
        for dtype, count in sorted(detection_types.items(), key=lambda x: -x[1]):
            result += f"- {dtype}: {count} occurrences\n"
        result += "\n"
    if freq_min != float('inf'):
        result += f"**Frequency Range:** {freq_min:.3f} MHz to {freq_max:.3f} MHz\n"
        if 1575.0 < freq_min < 1576.0:
            result += f"- **Target:** GPS L1 band (~1575.42 MHz)\n"
        result += "\n"
    if power_min != float('inf'):
        result += f"**Signal Power Range:** {power_min:.1f} to {power_max:.1f} dBm\n\n"

    if is_full:
        result += f"*Full file analysis: all {total_records:,} {log_name} records processed.*"
    else:
        result += f"*Analysis based on {sample_size:,} sampled records from {total_records:,} total.*"
    return result


# ── FAST TRACKSTAT C/No FORMATTER (NO LLM) ────────────────────────────
def format_trackstat_cno(question: str, tool_result: dict, intent: dict, handler: str) -> str:
    """Ultra-fast TRACKSTAT C/No analysis formatting WITHOUT LLM."""
    log_name = tool_result.get('log_name', 'TRACKSTAT')
    total_records = tool_result.get('total_records', 0)
    records = tool_result.get('records', [])

    if total_records == 0:
        return f"✅ **No {log_name} records found in this file.**"

    all_cno_values = []
    cno_by_time = {}

    for rec in records:
        fields = rec.get('fields_parsed', [])
        utc_time = rec.get('utc_time', 'N/A')
        if len(fields) < 4:
            continue
        try:
            num_channels = int(float(fields[3])) if fields[3] else 0
            satellite_start = 4
            cno_values_this_record = []
            for sat_idx in range(num_channels):
                cno_field_idx = satellite_start + (sat_idx * 10) + 5
                if cno_field_idx < len(fields):
                    try:
                        cno = float(fields[cno_field_idx])
                        if cno > 0:
                            all_cno_values.append(cno)
                            cno_values_this_record.append(cno)
                    except (ValueError, IndexError):
                        pass
            if cno_values_this_record:
                cno_by_time[utc_time] = cno_values_this_record
        except (ValueError, IndexError):
            continue

    if not all_cno_values:
        return f"⚠️ **No valid C/No values found in {total_records:,} {log_name} records.**"

    min_cno = min(all_cno_values)
    max_cno = max(all_cno_values)
    avg_cno = sum(all_cno_values) / len(all_cno_values)
    range_cno = max_cno - min_cno

    min_time = max_time = None
    for timestamp, cno_list in cno_by_time.items():
        if min_cno in cno_list and not min_time:
            min_time = timestamp
        if max_cno in cno_list and not max_time:
            max_time = timestamp

    result = f"**Signal Quality (C/No) Analysis from TRACKSTAT**\n\n"
    result += "| Metric | Value | Timestamp (UTC) |\n"
    result += "|--------|-------|----------------|\n"
    result += f"| **Minimum** | {min_cno:.1f} dB-Hz | {min_time or 'N/A'} |\n"
    result += f"| **Maximum** | {max_cno:.1f} dB-Hz | {max_time or 'N/A'} |\n"
    result += f"| **Average** | {avg_cno:.1f} dB-Hz | - |\n"
    result += f"| **Range** | {range_cno:.1f} dB-Hz | - |\n\n"
    result += f"*Analyzed {len(all_cno_values):,} C/No values from {len(cno_by_time):,} records.*\n\n"

    # Scintillation assessment
    if handler == 'trackstat_cno_analysis':
        result += "**Scintillation Assessment:**\n\n"
        if range_cno > 15 or min_cno < 25:
            result += "✅ **Yes, indicators of ionospheric scintillation are present.**\n\n"
            if range_cno > 15:
                result += f"- **Signal variation:** C/No range of {range_cno:.1f} dB-Hz indicates amplitude fluctuations\n"
            if min_cno < 25:
                result += f"- **Signal fades:** Minimum C/No of {min_cno:.1f} dB-Hz shows signal degradation\n"
        else:
            result += f"✅ **No significant scintillation detected.** C/No stable (range: {range_cno:.1f} dB-Hz).\n"

    return result


# ── Answer formatter (one LLM call) ───────────────────────────────────
_FORMAT_PROMPT = """You are a NovAtel OEM7 log analyst. Answer the user's question using the tool result and the log documentation below.

User question: {question}

Log documentation (field definitions):
{log_docs}

Tool result (JSON):
{tool_result}

Instructions:
- For bit_check results: State matches_found, list timestamps if > 0
- For numeric_stat results: State min, max, average with units
- For raw_listing results: Use field definitions to interpret fields_parsed arrays
- Be precise and factual - never invent data not present in the tool result
"""


def format_answer(question: str, tool_result: dict, log_docs: str = "") -> str:
    """Format the answer — fast path for bit_check/numeric_stat, LLM for raw_listing."""
    t0 = time.time()

    # Fast path: bit_check
    if tool_result.get("status") == "success" and "records_with_bit_set" in tool_result:
        matches = tool_result.get("matches_found", 0)
        log_name = tool_result.get("log_name", "")
        field_idx = tool_result.get("doc_field_index", "")
        bit_pos = tool_result.get("bit_position", "")
        total_checked = tool_result.get("total_checked", 0)

        q_lower = (question or "").lower()
        subject_map = [("spoofing", "spoofing"), ("spoof", "spoofing"),
                       ("jamming", "jamming"), ("jammer", "jamming"),
                       ("interference", "interference"), ("antenna", "antenna issue")]
        subject = next((label for kw, label in subject_map if kw in q_lower), "event")

        if matches == 0:
            result = (f"### ❌ No {subject} detected in this file.\n\n"
                      f"Checked **{total_checked}** `{log_name}` records "
                      f"(field {field_idx}, bit {bit_pos}) — the {subject} bit was never set.")
        else:
            records = tool_result["records_with_bit_set"]
            timestamps = [r["utc_time"] for r in records if r.get("utc_time")]
            time_range = ""
            if timestamps:
                time_range = f"- **First event:** {timestamps[0]}\n- **Last event:** {timestamps[-1]}\n"
            ts_list = "\n".join(f"- {ts}" for ts in timestamps[:50])
            if len(timestamps) > 50:
                ts_list += f"\n\n*… ({len(timestamps) - 50} more timestamps omitted) …*"
            result = (f"### ✅ Yes, {subject} was detected in this file.\n\n"
                      f"**Summary**\n- **Events:** {matches}\n"
                      f"- **Source log:** `{log_name}` (field {field_idx}, bit {bit_pos})\n"
                      f"- **Records checked:** {total_checked}\n{time_range}\n"
                      f"**Event timestamps (UTC):**\n\n{ts_list}")
        print(f"[FORMAT] fast path took={time.time()-t0:.2f}s")
        return result

    # Fast path: numeric_stat
    if tool_result.get("status") == "success" and "min_value" in tool_result:
        log_name = tool_result.get("log_name", "")
        field_idx = tool_result.get("doc_field_index", "")
        min_val = tool_result.get("min_value")
        max_val = tool_result.get("max_value")
        avg_val = tool_result.get("average_value")
        range_val = tool_result.get("range")
        total = tool_result.get("total_records", 0)
        valid = tool_result.get("valid_values", 0)
        min_time = tool_result.get("min_occurred_at", {}).get("utc_time", "")
        max_time = tool_result.get("max_occurred_at", {}).get("utc_time", "")

        unit = ""
        if "height" in question.lower() or "altitude" in question.lower():
            unit = " m"
        elif "vel" in question.lower() or "speed" in question.lower():
            unit = " m/s"

        result = (f"**Statistics for {log_name} field {field_idx}:**\n\n"
                  f"| Metric | Value | Timestamp (UTC) |\n"
                  f"|--------|-------|----------------|\n"
                  f"| **Minimum** | {min_val:.3f}{unit} | {min_time} |\n"
                  f"| **Maximum** | {max_val:.3f}{unit} | {max_time} |\n"
                  f"| **Average** | {avg_val:.3f}{unit} | - |\n"
                  f"| **Range** | {range_val:.3f}{unit} | - |\n\n"
                  f"Analyzed {valid} valid values from {total} total records.")
        print(f"[FORMAT] fast path (numeric) took={time.time()-t0:.2f}s")
        return result

    # Slow path: LLM for raw_listing
    optimized_result = tool_result.copy()
    if "records" in optimized_result and len(optimized_result.get("records", [])) > 10:
        records = optimized_result["records"]
        optimized_result["records"] = records[:5] + records[-5:]
        optimized_result["_sampling_note"] = f"Showing first 5 and last 5 of {len(records)} records"

    trimmed_docs = log_docs[:800] if log_docs else "Not available."
    prompt = _FORMAT_PROMPT.format(
        question=question,
        tool_result=json.dumps(optimized_result, indent=2),
        log_docs=trimmed_docs,
    )
    try:
        result = get_llm().invoke([HumanMessage(content=prompt)]).content.strip()
        print(f"[FORMAT] LLM path took={time.time()-t0:.2f}s")
        return result
    except Exception as e:
        print(f"[FORMAT] failed: {e}")
        return (f"**Analysis of {tool_result.get('log_name', 'unknown')} log:**\n\n"
                f"Found {tool_result.get('total_records', 0)} records. "
                f"For specific analysis, try asking about specific fields or events.")


# ── Log name selector (uses LLM knowledge + GNSS KB) ──────────────────
_LOG_SELECT_PROMPT = """You are a NovAtel OEM7 expert. Identify which log to query.

Available logs in the uploaded file:
{available_logs}

User question: {question}

GNSS KNOWLEDGE BASE CONTEXT:
{gnss_kb_excerpt}

NOVATEL LOG SELECTION GUIDE:
  - Jamming (receiver status bit) → RXSTATUS
  - Interference (spectrum analysis) → ITDETECTSTATUS
  - Spoofing detection → RXSTATUS
  - Position / height / lat/lon → BESTPOS
  - Velocity / speed / heading → BESTVEL
  - Satellite tracking / C/No → TRACKSTAT
  - Signal types / constellations → CHANCONFIGLIST
  - Receiver status / errors → RXSTATUS

Return ONLY the log name. No explanation."""


def extract_log_name(question: str, available_logs: list[str]) -> str | None:
    """Use LLM to pick the right log from file inventory."""
    logs_str = "\n".join(f"- {l}" for l in available_logs)
    gnss_kb = get_gnss_kb()
    gnss_kb_excerpt = gnss_kb[:20000] if gnss_kb else "No additional context available."

    prompt = _LOG_SELECT_PROMPT.format(
        question=question, available_logs=logs_str, gnss_kb_excerpt=gnss_kb_excerpt
    )
    try:
        response = get_llm().invoke([HumanMessage(content=prompt)])
        log_name = response.content.strip().upper().split()[0].strip(".,\"'-")
        print(f"[LOG_NAME] selected: {log_name}")
        return log_name
    except Exception as e:
        print(f"[LOG_NAME] failed: {e}")
        return None


# ── Documentation agent (pure KB, no log tools) ───────────────────────
@tool
def kb_retriever_tool(query: str, max_results: int = MAX_RESULTS) -> dict:
    """Search the NovAtel OEM7 documentation knowledge base."""
    elements = kb_search(query, max_results)
    payload = {"status": "success", "elements": elements, "total_found": len(elements)}
    _tool_call_log.append({"tool": "kb_retriever", "result": payload})
    return payload


@tool
def context_expander(source_uri: str, element_ids: list = None,
                     page_numbers: list = None,
                     expansion_pages: int = EXPANSION_PAGES) -> dict:
    """Expand context around specific KB elements. Pass csv_source_uri from kb_retriever."""
    t0 = time.time()
    try:
        source_uri = _resolve_data_uri(source_uri)
        df = _download_and_parse(source_uri)
        target_pages: set[int] = set()
        if element_ids:
            for eid in element_ids:
                rows = df[df["element_id"] == eid]
                if not rows.empty:
                    target_pages.update(rows["page_number"].tolist())
        if page_numbers:
            target_pages.update(page_numbers)
        all_pages = {i for p in target_pages
                     for i in range(p - expansion_pages, p + expansion_pages + 1) if i >= 0}
        filtered = df[df["page_number"].isin(all_pages)].copy()
        for col in ["page_number"]:
            if col in filtered.columns:
                filtered[col] = pd.to_numeric(filtered[col], errors="coerce").fillna(0).astype(int)
        for col in [c for c in filtered.columns if c != "page_number"]:
            filtered[col] = filtered[col].fillna("").astype(str)
        available_cols = [c for c in _LLM_COLS if c in filtered.columns]
        slim = filtered[available_cols].to_dict("records") if available_cols else []
        print(f"[EXPANDER] pages={sorted(all_pages)} elements={len(slim)} took={time.time()-t0:.2f}s")
        return {"status": "success", "elements": slim, "total_found": len(slim)}
    except Exception as e:
        print(f"[EXPANDER] error: {e}")
        return {"status": "error", "error": str(e), "elements": [], "total_found": 0}


# ── Agent-based tools (kept for backward compatibility) ───────────────
@tool
def list_log_types() -> dict:
    """List all log types present in the uploaded file with record counts and time range."""
    entry = _get_session_entry()
    if not entry:
        return {"status": "error", "error": "No log file has been uploaded in this session."}
    df = entry["df"]
    if df.empty:
        return {"status": "error", "error": "Uploaded log had no parseable records."}

    log_counts = df.groupby("log_name_raw").size().sort_values(ascending=False).to_dict()
    VALID_TIME = {"FINESTEERING", "FINE", "FINEBACKUPSTEERING", "FINEADJUSTING",
                  "COARSE", "COARSESTEERING", "COARSEADJUSTING", "FREEWHEELING"}
    valid = df[df["time_status"].isin(VALID_TIME) & (df["week"] > 0)]
    if not valid.empty:
        w_start = int(valid.loc[valid["seconds"].idxmin(), "week"])
        w_end   = int(valid.loc[valid["seconds"].idxmax(), "week"])
        s_start = float(valid["seconds"].min())
        s_end   = float(valid["seconds"].max())
        weeks   = sorted(valid["week"].unique().tolist())
        duration = (weeks[-1] - weeks[0]) * 604800 + (s_end - s_start) if len(weeks) > 1 else s_end - s_start
        file_time_info = {
            "utc_start": gps_to_utc_str(w_start, s_start),
            "utc_end":   gps_to_utc_str(w_end, s_end),
            "duration_seconds": round(duration, 3),
        }
    else:
        file_time_info = {"note": "No valid GPS time records in file."}

    return {"status": "success", "filename": entry["filename"],
            "total_records": len(df), "distinct_log_types": len(log_counts),
            "log_counts": log_counts, "file_time_info": file_time_info}


@tool
def query_log(log_name: str = None, time_from: float = None, time_to: float = None,
              field_contains: str = None, limit: int = None) -> dict:
    """Fetch records from the uploaded NovAtel ASCII log file."""
    entry = _get_session_entry()
    if not entry:
        return {"status": "error", "error": "No log file has been uploaded in this session."}
    df = entry["df"]
    if df.empty:
        return {"status": "error", "error": "Uploaded log had no parseable records."}

    filtered = df
    if log_name:
        filtered = filtered[filtered["log_name"].str.upper() == log_name.upper()]
    if time_from is not None:
        filtered = filtered[filtered["seconds"] >= time_from]
    if time_to is not None:
        filtered = filtered[filtered["seconds"] <= time_to]
    if field_contains:
        filtered = filtered[filtered["fields_raw"].str.contains(field_contains, case=False, na=False)]

    total = len(filtered)
    truncated = limit is not None and total > limit
    trimmed = filtered.head(limit) if limit is not None else filtered

    records = []
    for _, row in trimmed.iterrows():
        fields_raw = row.get("fields_raw", "")
        records.append({
            "log_name": row["log_name"], "utc_time": row.get("utc_time", ""),
            "seconds": row["seconds"], "week": int(row["week"]),
            "rx_status": row.get("rx_status", ""),
            "fields_raw": fields_raw,
            "fields_parsed": [f.strip() for f in fields_raw.split(",")],
        })

    return {"status": "success", "total_matching": total, "returned": len(records),
            "truncated": truncated, "records": records}


@tool
def analyze_events(event_type: str) -> dict:
    """Return pre-decoded security/quality events from the uploaded log."""
    entry = _get_session_entry()
    if not entry:
        return {"status": "error", "error": "No log file has been uploaded in this session."}
    events = entry.get("events", {})

    if event_type == "all":
        return {"status": "success", "event_type": "all",
                "summary": {k: len(v) for k, v in events.items()}}

    if event_type == "jamming":
        merged = _merge_jamming_events(events.get("jamming", []), events.get("itdetect_interference", []))
        return {"status": "success", "event_type": "jamming",
                "total_unique_events": len(merged), "events": merged[:50]}

    if event_type == "spoofing":
        merged = _merge_jamming_events(events.get("spoofing", []), events.get("itdetect_interference", []))
        return {"status": "success", "event_type": "spoofing",
                "total_unique_events": len(merged), "events": merged[:50]}

    if event_type not in events:
        return {"status": "error", "error": f"Unknown event_type '{event_type}'."}

    result = events[event_type]
    return {"status": "success", "event_type": event_type,
            "total_events": len(result), "events": result[:50]}


# ── Doc agent ─────────────────────────────────────────────────────────
_DOC_AGENT_PROMPT = """You are a NovAtel OEM7 documentation assistant with deep expertise in GNSS receivers.

BUDGET: 1 kb_retriever_tool call + 1 optional context_expander.

INSTRUCTIONS:
1. Call kb_retriever_tool once with the user's question.
2. If you find relevant information, answer directly and cite the log/command name.
3. Only call context_expander if a result is clearly incomplete.
4. If KB search returns no results, use your GNSS/NovAtel expertise to provide a helpful answer.

Do not call kb_retriever_tool twice. Start directly with the answer."""

_doc_agent = None


def get_doc_agent():
    global _doc_agent
    if _doc_agent is None:
        _doc_agent = create_react_agent(
            model=get_llm(),
            tools=[kb_retriever_tool, context_expander],
        )
    return _doc_agent


def run_doc_agent(prompt: str, history: list, session_id: str = "") -> str:
    t0 = time.time()
    if session_id:
        set_status(session_id, "Searching knowledge base...")
    messages = [SystemMessage(content=_DOC_AGENT_PROMPT)] + history + [HumanMessage(content=prompt)]
    try:
        result = get_doc_agent().invoke(
            {"messages": messages},
            config={"recursion_limit": 8},
        )
        answer = result["messages"][-1].content
        print(f"[DOC_AGENT] took={time.time()-t0:.2f}s")
        if session_id:
            set_status(session_id, "Complete ✓")
        return answer
    except Exception as e:
        print(f"[DOC_AGENT] error: {e}")
        if session_id:
            set_status(session_id, "Error occurred")
        raise


# ── Direct handlers (fully deterministic, zero LLM) ───────────────────
_VALID_TIME_STATUSES = {"FINESTEERING", "FINE", "FINEBACKUPSTEERING", "FINEADJUSTING",
                        "COARSE", "COARSESTEERING", "COARSEADJUSTING", "FREEWHEELING"}


def _direct_list_logs(log_entry: dict) -> dict:
    df = log_entry["df"]
    log_counts = df.groupby("log_name_raw").size().sort_values(ascending=False)
    lines = [f"| {n} | {c} |" for n, c in log_counts.items()]
    table = "| Log Type | Count |\n|---|---|\n" + "\n".join(lines)
    return {"result": f"**{len(log_counts)} log types** in `{log_entry['filename']}` "
                      f"({len(df)} total records):\n\n{table}"}


def _direct_time_range(log_entry: dict) -> dict:
    df = log_entry["df"]
    valid = df[df["time_status"].isin(_VALID_TIME_STATUSES) & (df["week"] > 0)]
    if valid.empty:
        return {"result": "No records with valid GPS time found in this file."}
    w_s = int(valid.loc[valid["seconds"].idxmin(), "week"])
    w_e = int(valid.loc[valid["seconds"].idxmax(), "week"])
    s_s = float(valid["seconds"].min())
    s_e = float(valid["seconds"].max())
    weeks = sorted(valid["week"].unique().tolist())
    dur = (weeks[-1] - weeks[0]) * 604800 + (s_e - s_s) if len(weeks) > 1 else s_e - s_s
    return {"result": (
        f"**File time range for `{log_entry['filename']}`:**\n\n"
        f"| | GPS | UTC |\n|---|---|---|\n"
        f"| Start | Week {w_s}, {s_s:.3f}s | {gps_to_utc_str(w_s, s_s)} |\n"
        f"| End   | Week {w_e}, {s_e:.3f}s | {gps_to_utc_str(w_e, s_e)} |\n\n"
        f"**Duration:** {dur:.3f}s ({dur/60:.2f} min)"
    )}


def _direct_data_gap(log_entry: dict, gap_threshold: float = 2.0) -> dict:
    """Check for time gaps in the file."""
    df = log_entry["df"]
    valid = df[df["time_status"].isin(_VALID_TIME_STATUSES) & (df["week"] > 0)].copy()
    if valid.empty:
        return {"result": "No records with valid GPS time found — cannot check for gaps."}

    most_common_log = valid["log_name_raw"].value_counts().idxmax()
    ref = valid[valid["log_name_raw"] == most_common_log].sort_values("seconds").copy()
    ref["abs_seconds"] = ref["week"] * 604800 + ref["seconds"]
    ref = ref.sort_values("abs_seconds").reset_index(drop=True)
    ref["delta"] = ref["abs_seconds"].diff()
    median_interval = ref["delta"].median()
    effective_threshold = max(gap_threshold, median_interval * 3)
    gaps = ref[ref["delta"] > effective_threshold].copy()

    if gaps.empty:
        total_duration = ref["abs_seconds"].iloc[-1] - ref["abs_seconds"].iloc[0]
        return {"result": (
            f"**No data gaps detected** in `{log_entry['filename']}`.\n\n"
            f"Reference log: `{most_common_log}` ({len(ref)} records)\n"
            f"Nominal interval: {median_interval:.3f}s | "
            f"Total duration: {total_duration:.1f}s ({total_duration/60:.2f} min)\n"
            f"Data appears continuous throughout."
        )}

    lines = []
    for _, row in gaps.iterrows():
        gap_sec = row["delta"]
        gap_start = gps_to_utc_str(int(row["week"]), float(row["seconds"]) - gap_sec)
        gap_end   = gps_to_utc_str(int(row["week"]), float(row["seconds"]))
        lines.append(f"| {gap_start} | {gap_end} | {gap_sec:.2f}s |")

    table = "| Gap Start (UTC) | Gap End (UTC) | Duration |\n|---|---|---|\n" + "\n".join(lines)
    total_duration = ref["abs_seconds"].iloc[-1] - ref["abs_seconds"].iloc[0]
    total_gap = gaps["delta"].sum()

    return {"result": (
        f"**{len(gaps)} data gap(s) detected** in `{log_entry['filename']}`.\n\n"
        f"Reference log: `{most_common_log}` ({len(ref)} records) | "
        f"Nominal interval: {median_interval:.3f}s\n"
        f"Total file duration: {total_duration:.1f}s | "
        f"Total missing time: {total_gap:.1f}s\n\n{table}"
    )}


# ── Binary pre-processor ──────────────────────────────────────────────
_BINARY_EXTENSIONS = ('.gps', '.bin', '.raw', '.nov', '.novb')


def is_binary_log(filename: str, file_bytes: bytes) -> bool:
    if any(filename.lower().endswith(ext) for ext in _BINARY_EXTENSIONS):
        return True
    if len(file_bytes) >= 3 and file_bytes[:3] == b'\xaa\x44\x12':
        return True
    return False


def convert_binary_to_ascii(file_bytes: bytes, filename: str) -> tuple[bytes, str]:
    import novatel_edie as edie
    ascii_lines = []
    skipped = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    fp = None
    try:
        fp = edie.FileParser(tmp_path)
        while True:
            try:
                result = fp.convert(edie.ENCODE_FORMAT.ASCII)
                if isinstance(result, edie.MessageData):
                    line = result.message.decode('utf-8', errors='replace').strip()
                    if line:
                        ascii_lines.append(line)
                else:
                    skipped += 1
            except edie.StreamEmptyException:
                break
            except Exception:
                skipped += 1
                continue
    finally:
        del fp
        try:
            os.remove(tmp_path)
        except Exception as e:
            print(f"[PREPROCESS] Warning: could not delete temp file: {e}")

    ascii_content = '\n'.join(ascii_lines)
    new_filename = os.path.splitext(filename)[0] + '_converted.ascii'
    print(f"[PREPROCESS] '{filename}' → '{new_filename}' ({len(ascii_lines)} messages, {skipped} skipped)")
    return ascii_content.encode('utf-8'), new_filename


def preprocess_file(file_bytes: bytes, filename: str) -> tuple[bytes, str]:
    if is_binary_log(filename, file_bytes):
        print(f"[PREPROCESS] Binary detected: '{filename}', converting via EDIE...")
        return convert_binary_to_ascii(file_bytes, filename)
    print(f"[PREPROCESS] ASCII file: '{filename}', no conversion needed.")
    return file_bytes, filename


# ── S3 helper ─────────────────────────────────────────────────────────
def upload_to_s3(content: bytes, filename: str) -> str:
    key = f"logs/{filename}"
    get_s3_client().put_object(Bucket=S3_BUCKET, Key=key, Body=content)
    return key


# ── Routing triggers ──────────────────────────────────────────────────
_LIST_TRIGGERS = ("list all log", "what log", "all log", "log type", "how many log",
                  "available log", "logs in", "logs are", "logs present", "logs there", "what data")
_TIME_TRIGGERS = ("start time", "end time", "duration", "time range", "start and end",
                  "file time", "gps time", "utc time", "how long", "begin", "finish")
_GAP_TRIGGERS  = ("gap", "missing", "continuous", "every second", "data loss",
                  "time missing", "dropped", "interval")
_EVENT_KEYWORDS = ("when", "occur", "detect", "spoof", "jam", "interfere", "bit", "status",
                   "error", "flag", "max", "min", "average", "height", "position", "velocity",
                   "signal", "drop", "strength", "quality", "tracking", "lock", "loss")


# ── Correlation pipeline (NEW) ─────────────────────────────────────────
def run_correlation_pipeline(question: str, session_id: str) -> str:
    """
    NEW evidence-correlation pipeline:
      1. Domain extraction (fixed ontology, no LLM)
      2. Available log inventory
      3. Evidence planning (deterministic tool selection)
      4. Parallel multi-tool execution
      5. Correlation JSON assembly
      6. LLM reasoning over structured evidence

    This replaces the old single-tool approach with multi-source correlation.
    """
    print(f"[CORRELATION] question={question!r}")
    t0 = time.time()

    # Get available logs from session
    entry = _log_store.get(session_id)
    available_logs = []
    if entry and not entry["df"].empty:
        available_logs = entry["df"]["log_name_raw"].unique().tolist()

    # Step 1-3: Domain extraction + evidence planning
    set_status(session_id, "Identifying evidence requirements...")
    plan = build_execution_plan(question, available_logs)

    print(f"[CORRELATION] domains={plan.top_domains} tools={plan.runnable_tools}")

    if not plan.runnable_tools and plan.has_log_file:
        # All tools skipped — insufficient log types
        set_status(session_id, "Required logs not found — generating suggestions...")
        correlation_json = execute_plan(plan, entry)
        answer = synthesize_response(correlation_json, question, session_id)
        set_status(session_id, "Complete ✓")
        return answer

    if not plan.has_log_file:
        set_status(session_id, "No log file loaded.")
        correlation_json = execute_plan(plan, None)
        answer = synthesize_response(correlation_json, question, session_id)
        set_status(session_id, "Complete ✓")
        return answer

    # Step 4-5: Execute tools + assemble Correlation JSON
    set_status(session_id, f"Running {len(plan.runnable_tools)} analysis tools in parallel...")
    correlation_json = execute_plan(plan, entry)

    # Log events for visibility
    events = correlation_json.get("events", [])
    if events:
        set_status(session_id, f"Found {len(events)} telemetry events — correlating...")
    else:
        set_status(session_id, "Analysis complete — synthesizing response...")

    # Step 6: LLM reasoning
    answer = synthesize_response(correlation_json, question, session_id)
    elapsed = time.time() - t0
    print(f"[CORRELATION] completed in {elapsed:.2f}s")
    set_status(session_id, "Complete ✓")
    return answer


def run_correlation_pipeline_streaming(question: str, session_id: str, chat_history: list = None):
    """
    Streaming variant of the correlation pipeline.
    Returns a generator that yields text chunks for real-time display.

    Phases 1-5 run fully (deterministic, fast).
    Phase 6 (LLM) streams token by token.
    After LLM stream completes, yields the deterministic footer sections.

    Args:
        question:     User's current query
        session_id:   Session identifier
        chat_history: Optional list of (role, text) tuples from streamlit session state
    """
    from src.reasoning_layer import _build_focused_evidence, _format_missing_evidence
    from src.doc_answering import answer_without_file, classify_query, _DOC_SYNTHESIS_PROMPT, _GENERAL_GNSS_PROMPT
    from src.response_formatter import (
        _build_severity_header, _build_diagnostic_cards,
        _build_metrics_table, _build_evidence_footer, _overall_severity,
    )
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

    print(f"[CORRELATION_STREAM] question={question!r}")
    t0 = time.time()

    # Build conversation history for LLM context
    # Prefer local chat_history (always in sync) over external memory
    history_messages = []
    if chat_history:
        for role, text in chat_history[-10:]:  # Last 10 messages (5 Q&A pairs)
            if role == "user":
                history_messages.append(HumanMessage(content=text[:800]))
            elif role == "agent":
                history_messages.append(AIMessage(content=text[:800]))
    elif MEMORY_ID:
        try:
            events = get_memory_client().list_events(
                memory_id=MEMORY_ID, actor_id=ACTOR_ID,
                session_id=session_id, max_results=20,
            )
            for event in events:
                for item in event.get("payload", []):
                    conv = item.get("conversational", {})
                    role = conv.get("role", "")
                    text = conv.get("content", {}).get("text", "")
                    if role == "USER":
                        history_messages.append(HumanMessage(content=text[:800]))
                    elif role == "ASSISTANT":
                        history_messages.append(AIMessage(content=text[:800]))
        except Exception as e:
            print(f"[MEMORY] load error: {e}")
        history_messages = history_messages[-10:]

    # Get available logs from session
    entry = _log_store.get(session_id)
    available_logs = []
    if entry and not entry["df"].empty:
        available_logs = entry["df"]["log_name_raw"].unique().tolist()

    # Step 1-3: Domain extraction + evidence planning
    set_status(session_id, "Identifying evidence requirements...")
    plan = build_execution_plan(question, available_logs)

    # ── Handle: No file loaded ────────────────────────────────────────
    if not plan.has_log_file:
        set_status(session_id, "")
        classification = classify_query(question)
        if classification in ("needs_log", "off_topic"):
            answer = answer_without_file(question, session_id)
            yield answer
            return

        # Stream doc/general answer
        if classification == "documentation":
            set_status(session_id, "Searching NovAtel documentation...")
            kb_results = kb_search(question, max_results=8)
            if kb_results:
                kb_content_parts = []
                for i, el in enumerate(kb_results):
                    content = el.get("content_markdown", "").strip()
                    if not content or el.get("score", 0) < 0.1:
                        continue
                    if len(content) > 1500:
                        content = content[:1500] + "..."
                    kb_content_parts.append(f"--- Reference {i+1} ---\n{content}")
                kb_content = "\n\n".join(kb_content_parts[:6])
                prompt = _DOC_SYNTHESIS_PROMPT.format(question=question, kb_content=kb_content)
            else:
                prompt = _GENERAL_GNSS_PROMPT.format(question=question)
        else:
            prompt = _GENERAL_GNSS_PROMPT.format(question=question)

        set_status(session_id, "Generating answer...")
        messages = history_messages + [HumanMessage(content=prompt)]
        for chunk in get_llm().stream(messages):
            if chunk.content:
                yield chunk.content
        return

    # ── Handle: File loaded but no telemetry domains matched ──────────
    # This means it's either a greeting, documentation question, or
    # general question — NOT a telemetry analysis request.
    if not plan.runnable_tools or not plan.top_domains:
        classification = classify_query(question)

        # Greetings / off-topic — instant response, no KB search
        if classification == "off_topic":
            yield "I'm a NovAtel GNSS log analysis assistant. I can analyze your uploaded file — try asking about positioning, signal quality, interference, satellites, or INS status."
            return
        if classification == "needs_log":
            # File IS loaded, so redirect to what they can ask
            yield "Your log file is loaded and ready. Try asking about:\n- Signal quality and C/No\n- Satellite tracking and constellations\n- Positioning accuracy and fix types\n- Interference or jamming detection\n- INS alignment status\n- Data gaps and time range"
            return

        # Documentation question (file loaded but question isn't about telemetry)
        set_status(session_id, "Searching NovAtel documentation...")
        kb_results = kb_search(question, max_results=8)
        if kb_results:
            kb_content_parts = []
            for i, el in enumerate(kb_results):
                content = el.get("content_markdown", "").strip()
                if not content or el.get("score", 0) < 0.1:
                    continue
                if len(content) > 1500:
                    content = content[:1500] + "..."
                kb_content_parts.append(f"--- Reference {i+1} ---\n{content}")
            kb_content = "\n\n".join(kb_content_parts[:6])
            prompt = _DOC_SYNTHESIS_PROMPT.format(question=question, kb_content=kb_content)
        else:
            prompt = _GENERAL_GNSS_PROMPT.format(question=question)

        set_status(session_id, "Generating answer...")
        messages = history_messages + [HumanMessage(content=prompt)]
        for chunk in get_llm().stream(messages):
            if chunk.content:
                yield chunk.content
        return

    # ── Step 4-5: Execute tools + assemble Correlation JSON ───────────
    set_status(session_id, f"Running {len(plan.runnable_tools)} analysis tools...")
    correlation_json = execute_plan(plan, entry)

    events      = correlation_json.get("events", [])
    diagnostics = correlation_json.get("diagnostics", [])
    metrics     = correlation_json.get("metrics", {})
    unavailable = correlation_json.get("unavailable_evidence", [])
    tools_run   = correlation_json.get("execution_meta", {}).get("tools_run", [])
    evidence    = correlation_json.get("evidence", {})

    # Check if we have usable evidence
    available_tools_ran = [t for t in tools_run if evidence.get(t, {}).get("status") == "ok"]
    if not available_tools_ran:
        # Tools ran but produced no data — fall back to non-streaming
        answer = synthesize_response(correlation_json, question, session_id)
        yield answer
        return

    # ── Yield severity header (deterministic, instant) ────────────────
    overall_severity = _overall_severity(diagnostics, events)
    if overall_severity not in ("nominal", "low", "info"):
        header = _build_severity_header(overall_severity, diagnostics)
        yield header + "\n"

    # ── Stream LLM explanation ────────────────────────────────────────
    set_status(session_id, "Generating analysis...")
    focused = _build_focused_evidence(correlation_json)
    missing_str = _format_missing_evidence(unavailable) if unavailable else "None — all required evidence was available."
    evidence_str = json.dumps(focused, indent=2, default=str)
    if len(evidence_str) > 8000:
        evidence_str = evidence_str[:8000] + "\n... [truncated]"

    from src.reasoning_layer import _REASONING_PROMPT
    prompt = _REASONING_PROMPT.format(
        question=question,
        evidence_json=evidence_str,
        missing_evidence=missing_str,
    )

    for chunk in get_llm().stream([HumanMessage(content=prompt)]):
        if chunk.content:
            yield chunk.content

    # ── Yield deterministic footer sections (after stream) ────────────
    non_nominal = [d for d in diagnostics if d.get("diagnostic_id") != "NOMINAL_OPERATION"]
    if non_nominal:
        yield "\n\n---\n\n"
        yield _build_diagnostic_cards(non_nominal)

    metric_table = _build_metrics_table(metrics, diagnostics)
    if metric_table:
        yield "\n\n" + metric_table

    elapsed = time.time() - t0
    footer = _build_evidence_footer(tools_run, unavailable, elapsed)
    if footer:
        yield "\n\n" + footer

    set_status(session_id, "Complete ✓")
    print(f"[CORRELATION_STREAM] completed in {elapsed:.2f}s")


# ── Scintillation analysis ────────────────────────────────────────────

def run_scintillation_analysis(session_id: str, user_question: str):
    """
    Streaming generator: run the full in-memory scintillation pipeline and
    yield LLM tokens as the response.
    """
    file_bytes = _scint_bytes_store.get(session_id)

    # Large S3 files don't keep bytes in memory — re-fetch on demand
    if not file_bytes:
        s3_key = _scint_s3_key_store.get(session_id)
        if s3_key:
            set_status(session_id, "Re-fetching file from S3 for scintillation analysis...")
            print(f"[SCINTILLATION] Re-fetching from S3: {s3_key}")
            try:
                import io as _io
                obj = get_s3_client().get_object(Bucket=S3_BUCKET, Key=s3_key)
                buf = _io.BytesIO()
                for chunk in obj["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
                    buf.write(chunk)
                file_bytes = buf.getvalue()
                del buf
                print(f"[SCINTILLATION] Re-fetched {len(file_bytes)} bytes from S3")
            except Exception as e:
                yield f"Failed to retrieve file from S3 for scintillation analysis: {e}"
                return
        else:
            yield "No log file found in this session. Please upload a file first."
            return

    set_status(session_id, "Running scintillation pipeline...")
    print(f"[SCINTILLATION] starting analysis session={session_id}")
    t0 = time.time()

    summary = scint_analyse_bytes(file_bytes, environment_type="OPEN_SKY")
    del file_bytes  # free RAM — pipeline has extracted what it needs into summary

    if summary.get("pipeline_error"):
        yield (
            f"⚠️ The scintillation pipeline encountered an error:\n\n"
            f"```\n{summary['pipeline_error']}\n```\n\n"
            "Please check that your file contains RANGEA records."
        )
        set_status(session_id, "Complete ✓")
        return

    print(f"[SCINTILLATION] pipeline done in {time.time()-t0:.2f}s, "
          f"worst_flag={summary.get('worst_flag')} "
          f"confidence={summary.get('confidence_level')}")

    set_status(session_id, "Reasoning over scintillation evidence...")
    prompt = scint_build_prompt(summary, user_question)

    for chunk in get_llm().stream([HumanMessage(content=prompt)]):
        if chunk.content:
            yield chunk.content

    set_status(session_id, "Complete ✓")


# ── Main entrypoint ───────────────────────────────────────────────────
@app.entrypoint
async def invoke(payload):
    if isinstance(payload, dict):
        prompt     = payload.get("prompt", "")
        file_b64   = payload.get("file", None)
        s3_key_in  = payload.get("s3_key", None)
        filename   = payload.get("filename", "log.txt")
        session_id = payload.get("session_id", "default-session")
    else:
        prompt = str(payload)
        file_b64 = s3_key_in = None
        filename = "log.txt"
        session_id = "default-session"

    # ── File ingest ───────────────────────────────────────────────────
    if file_b64:
        try:
            file_bytes = base64.b64decode(file_b64)
            file_bytes, filename = preprocess_file(file_bytes, filename)
            if S3_BUCKET and len(file_bytes) > SIZE_THRESHOLD:
                upload_to_s3(file_bytes, filename)
            info = ingest_log_file(file_bytes, filename, session_id)
            return {
                "result": f"Parsed '{info['filename']}': {info['records']} records across "
                          f"{info['log_types']} log types. Ask me anything about this file.",
                "summary": info["summary"],
            }
        except Exception as e:
            return {"result": f"Error parsing log file: {e}"}

    elif s3_key_in:
        try:
            # Stream from S3 in chunks to avoid holding 315 MB + a copy in RAM simultaneously.
            # boto3 streaming body is an iterator — we read it in 8 MB chunks directly into
            # a bytearray, avoiding a second full copy that obj["Body"].read() would create.
            import io as _io
            print(f"[S3] Streaming {s3_key_in} from bucket {S3_BUCKET}...")
            t0 = time.time()
            obj = get_s3_client().get_object(Bucket=S3_BUCKET, Key=s3_key_in)
            content_length = obj.get("ContentLength", 0)
            buf = _io.BytesIO()
            chunk_size = 8 * 1024 * 1024  # 8 MB chunks
            bytes_read = 0
            for chunk in obj["Body"].iter_chunks(chunk_size=chunk_size):
                buf.write(chunk)
                bytes_read += len(chunk)
            file_bytes = buf.getvalue()
            del buf
            print(f"[S3] Streamed {bytes_read} bytes in {time.time()-t0:.2f}s")

            file_bytes, filename = preprocess_file(file_bytes, filename)
            info = ingest_log_file(file_bytes, filename, session_id)

            # For S3 files, don't keep full bytes in scint_bytes_store — too much RAM.
            # Store the s3_key instead so scintillation analysis can re-fetch on demand.
            _scint_bytes_store[session_id] = None  # clear any bytes
            _scint_s3_key_store[session_id] = s3_key_in  # store key for re-fetch

            del file_bytes  # release RAM — data is now in _log_store as parsed DataFrame
            return {
                "result": f"Parsed '{info['filename']}': {info['records']} records across "
                          f"{info['log_types']} log types. Ask me anything about this file.",
                "summary": info["summary"],
            }
        except Exception as e:
            import traceback
            print(f"[S3] Error: {traceback.format_exc()}")
            return {"result": f"Error reading from S3: {e}"}

    # ── Q&A path ─────────────────────────────────────────────────────
    print(f"[QA] prompt={prompt!r} session_id={session_id!r}")
    try:
        apply_guardrail(prompt, source="INPUT")
    except ValueError as e:
        return {"result": str(e)}

    _current_session_var.set(session_id)
    _tool_call_log.clear()

    # Load memory history
    history = []
    if MEMORY_ID:
        try:
            events = get_memory_client().list_events(
                memory_id=MEMORY_ID, actor_id=ACTOR_ID,
                session_id=session_id, max_results=10,
            )
            for event in events:
                for item in event.get("payload", []):
                    conv = item.get("conversational", {})
                    role = conv.get("role", "")
                    text = conv.get("content", {}).get("text", "")
                    if role == "USER":
                        history.append(HumanMessage(content=text))
                    elif role == "ASSISTANT":
                        history.append(AIMessage(content=text))
        except Exception as e:
            print(f"Memory retrieve error: {e}")

    history = history[-6:]
    history = [
        msg.__class__(content=msg.content[:800] + "…[truncated]")
        if isinstance(msg.content, str) and len(msg.content) > 800 else msg
        for msg in history
    ]

    # ── Routing ───────────────────────────────────────────────────────
    log_entry = _log_store.get(session_id)
    p = prompt.lower()

    # 1. Quick conversational responses
    _SIMPLE_CONVERSATIONAL = (
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "yes", "no",
        "good", "great", "nice", "cool", "awesome", "perfect", "got it",
    )
    is_short_conversational = len(prompt.strip()) < 50 and any(
        p.startswith(phrase) or p == phrase for phrase in _SIMPLE_CONVERSATIONAL
    )
    if is_short_conversational:
        responses = {
            "hi": "Hello! I'm ready to help you analyze NovAtel OEM7 receiver logs.",
            "hello": "Hi! I can help you analyze GNSS receiver logs and answer NovAtel documentation questions.",
            "thanks": "You're welcome! Let me know if you need anything else.",
            "thank you": "Happy to help! Feel free to ask more questions.",
            "ok": "Great! What would you like to analyze next?",
        }
        for key, response in responses.items():
            if key in p:
                return {"result": response}
        return {"result": "I'm here to help! What would you like to know?"}

    # Set initial status immediately so UI always shows something
    set_status(session_id, "Processing your question...")

    # 2. Direct handlers (fully deterministic, no LLM)
    if log_entry:
        is_event = any(kw in p for kw in _EVENT_KEYWORDS)

        # Data gap check
        if any(kw in p for kw in _GAP_TRIGGERS):
            set_status(session_id, "Checking for time gaps in log data...")
            result = _direct_data_gap(log_entry)
            clear_status(session_id)
            return {"result": result["result"]}

        # List logs
        if not is_event and any(kw in p for kw in _LIST_TRIGGERS):
            set_status(session_id, "Retrieving log inventory from file...")
            result = _direct_list_logs(log_entry)
            clear_status(session_id)
            return {"result": result["result"]}

        # Time range
        if not is_event and any(kw in p for kw in _TIME_TRIGGERS):
            set_status(session_id, "Computing file time range from GPS timestamps...")
            result = _direct_time_range(log_entry)
            clear_status(session_id)
            return {"result": result["result"]}

    # 3. Main routing logic
    try:
        if log_entry:
            # Correlation pipeline — multi-tool evidence-based reasoning
            print("[ROUTE] → correlation pipeline")
            output = run_correlation_pipeline(prompt, session_id)
        else:
            # Documentation agent — no file loaded, try correlation pipeline
            # (it will use LLM knowledge fallback via reasoning_layer)
            print("[ROUTE] → correlation pipeline (no file)")
            output = run_correlation_pipeline(prompt, session_id)

    except GraphRecursionError:
        clear_status(session_id)
        return {"result": "Hit the search budget. Please try rephrasing."}
    except Exception as e:
        clear_status(session_id)
        return {"result": f"Error: {e}"}

    # Clear status now that we have the answer
    clear_status(session_id)
    # Get the processing trail to include in response
    trail = get_and_clear_status_trail(session_id)

    try:
        apply_guardrail(output, source="OUTPUT")
    except ValueError as e:
        return {"result": str(e)}

    # Save to memory
    if MEMORY_ID:
        try:
            get_memory_client().create_event(
                memory_id=MEMORY_ID, actor_id=ACTOR_ID, session_id=session_id,
                messages=[(prompt, "USER"), (output, "ASSISTANT")],
            )
        except Exception as e:
            print(f"Memory save error: {e}")

    return {"result": output, "status_trail": trail}


if __name__ == "__main__":
    app.run()
