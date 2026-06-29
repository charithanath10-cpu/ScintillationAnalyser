"""
novatel_processor.py — AWS Lambda function for NovAtel log processing.

Parquet-backed architecture — raw ASCII is parsed ONCE, DataFrames stored
as Parquet on S3. Every subsequent Lambda call reads only the small Parquet
files it needs instead of re-parsing the full 315 MB raw file.

S3 layout:
  logs/{filename}                          ← raw uploaded file (input)
  parsed/{session_id}/main.parquet         ← all parsed log records (Q&A)
  parsed/{session_id}/events.json          ← pre-computed event index
  parsed/{session_id}/rangea.parquet       ← scintillation: RANGEA obs
  parsed/{session_id}/bestpos.parquet      ← scintillation: BESTPOS
  parsed/{session_id}/satvis2.parquet      ← scintillation: SATVIS2
  parsed/{session_id}/meta.json            ← summary + log_types + filename
  results/{session_id}.json                ← final answer (done=True)
  results/{session_id}_status.json         ← live status updates
  results/{session_id}_stream.txt          ← incremental token stream

Modes:
  ingest        — parse raw file, write all Parquet, return summary
  qa            — read main.parquet, run correlation pipeline, stream answer
  scintillation — read rangea/bestpos/satvis2 Parquet, run scintillation, stream

Memory reduction vs re-parsing:
  Raw file:      315 MB → parse in memory → peak ~1.9 GB
  Parquet reads: main.parquet ~15 MB, scint Parquets ~30 MB total

Environment variables:
    S3_BUCKET, BEDROCK_MODEL_ID, AWS_REGION, KB_ID
Lambda config:
    Memory: 3008 MB, Timeout: 900s, Runtime: python3.11
"""

import json, os, sys, io, time, traceback
import boto3
import pandas as pd

sys.path.insert(0, "/var/task")

S3_BUCKET = os.environ["S3_BUCKET"]
REGION    = os.environ.get("AWS_REGION", "us-east-1")
_s3 = boto3.client("s3", region_name=REGION)


# ── S3 I/O helpers ────────────────────────────────────────────────────

def _write_status(session_id: str, status: str, pct: int = 0):
    _s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"results/{session_id}_status.json",
        Body=json.dumps({"status": status, "pct": pct, "done": False}),
        ContentType="application/json",
    )

def _write_result(session_id: str, result: dict):
    _s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"results/{session_id}.json",
        Body=json.dumps(result, default=str),
        ContentType="application/json",
    )

def _read_s3_bytes(key: str) -> bytes:
    obj = _s3.get_object(Bucket=S3_BUCKET, Key=key)
    buf = io.BytesIO()
    for chunk in obj["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
        buf.write(chunk)
    data = buf.getvalue()
    del buf
    return data

def _write_parquet(df: pd.DataFrame, key: str):
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
    _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=buf.getvalue())
    print(f"[PARQUET] wrote {key} ({buf.tell()/1024:.0f} KB, {len(df)} rows)")

def _read_parquet(key: str) -> pd.DataFrame:
    obj = _s3.get_object(Bucket=S3_BUCKET, Key=key)
    buf = io.BytesIO(obj["Body"].read())
    df  = pd.read_parquet(buf, engine="pyarrow")
    print(f"[PARQUET] read {key} ({len(df)} rows)")
    return df

def _parquet_exists(key: str) -> bool:
    try:
        _s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except Exception:
        return False


# ── Streaming writer ──────────────────────────────────────────────────

class _StreamWriter:
    FLUSH_EVERY = 200

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._buf   = ""
        self._total = ""
        self._last  = time.time()

    def write(self, chunk: str):
        self._buf   += chunk
        self._total += chunk
        if len(self._buf) >= self.FLUSH_EVERY or time.time() - self._last > 1.5:
            self._flush()

    def _flush(self):
        if not self._buf:
            return
        _s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"results/{self.session_id}_stream.txt",
            Body=self._total.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )
        self._buf = ""
        self._last = time.time()

    def finish(self) -> str:
        self._flush()
        return self._total


# ── Ingest: parse raw file, write Parquet to S3 ───────────────────────

def _handle_ingest(session_id: str, s3_key: str, filename: str):
    from src.main import (
        parse_novatel_ascii, _summarize_log, _build_event_index,
        _log_store, _scint_s3_key_store,
    )
    from src.scintillation_log_decoders import (
        _parse_range_line, _parse_bestpos_line, _parse_satvis2_line,
    )

    _write_status(session_id, "📥 Reading file from S3...", 5)
    t0 = time.time()
    file_bytes = _read_s3_bytes(s3_key)
    print(f"[INGEST] Read {len(file_bytes)} bytes in {time.time()-t0:.2f}s")

    # ── Parse main log DataFrame ──────────────────────────────────────
    _write_status(session_id, "🔍 Parsing log records...", 15)
    t1 = time.time()
    text = file_bytes.decode("utf-8", errors="replace")

    # Parse scintillation-specific logs in the same pass to avoid re-reading
    range_obs, bestpos_obs, satvis2_obs = [], [], []
    lines = text.splitlines()
    del text

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#RANGEA,"):
            obs = _parse_range_line(s)
            if obs: range_obs.extend(obs)
        elif s.startswith("#BESTPOSA,"):
            row = _parse_bestpos_line(s)
            if row: bestpos_obs.append(row)
        elif s.startswith("#SATVIS2A,"):
            from src.scintillation_log_decoders import _parse_satvis2_line
            sats = _parse_satvis2_line(s)
            if sats: satvis2_obs.extend(sats)

    # Parse main DataFrame from the same raw bytes
    main_df = parse_novatel_ascii("\n".join(lines))
    del lines
    del file_bytes

    print(f"[INGEST] Parsed {len(main_df)} records in {time.time()-t1:.2f}s")

    # ── Write main.parquet ────────────────────────────────────────────
    _write_status(session_id, "💾 Saving parsed data to cloud...", 50)
    base = f"parsed/{session_id}"
    _write_parquet(main_df, f"{base}/main.parquet")

    # ── Write scintillation Parquets ──────────────────────────────────
    if range_obs:
        _write_parquet(pd.DataFrame(range_obs),   f"{base}/rangea.parquet")
    if bestpos_obs:
        _write_parquet(pd.DataFrame(bestpos_obs), f"{base}/bestpos.parquet")
    if satvis2_obs:
        _write_parquet(pd.DataFrame(satvis2_obs), f"{base}/satvis2.parquet")
    del range_obs, bestpos_obs, satvis2_obs

    # ── Build event index + summary ───────────────────────────────────
    summary = _summarize_log(main_df, filename)
    events  = _build_event_index(main_df)

    # Store in Lambda memory for this invocation
    _log_store[session_id] = {
        "df": main_df, "summary": summary,
        "filename": filename, "events": events,
    }
    _scint_s3_key_store[session_id] = s3_key

    log_types = int(main_df["log_name"].nunique()) if not main_df.empty else 0
    records   = len(main_df)
    del main_df

    # ── Write meta.json ───────────────────────────────────────────────
    _s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{base}/meta.json",
        Body=json.dumps({
            "filename": filename, "s3_key": s3_key,
            "records": records, "log_types": log_types,
            "summary": summary, "events": events,
        }, default=str),
        ContentType="application/json",
    )

    _write_result(session_id, {
        "done": True, "type": "ingest",
        "result": (
            f"Parsed **{filename}**: {records} records across "
            f"{log_types} log types. Ask me anything about this file."
        ),
        "summary": summary, "log_types": log_types, "records": records,
        "session_id": session_id,
    })
    print(f"[INGEST] Complete in {time.time()-t0:.2f}s")
    return {"statusCode": 200, "body": "ingest complete"}


# ── Q&A: read main.parquet, run correlation pipeline ─────────────────

def _handle_qa(session_id: str, s3_key: str, filename: str, question: str):
    from src.main import (
        _log_store, _summarize_log, _build_event_index,
        run_correlation_pipeline,
    )
    import json as _json

    _write_status(session_id, "📂 Loading parsed data...", 10)

    base = f"parsed/{session_id}"
    meta_key = f"{base}/meta.json"

    # ── Load from Parquet (fast) or fall back to raw parse ────────────
    if _parquet_exists(f"{base}/main.parquet"):
        print(f"[QA] Loading main.parquet from S3")
        main_df = _read_parquet(f"{base}/main.parquet")

        # Load event index from meta.json
        try:
            meta_obj = _s3.get_object(Bucket=S3_BUCKET, Key=meta_key)
            meta = _json.loads(meta_obj["Body"].read())
            events  = meta.get("events", {})
            summary = meta.get("summary", "")
        except Exception:
            events  = _build_event_index(main_df)
            summary = _summarize_log(main_df, filename)
    else:
        # Parquet not available — fall back to raw parse
        print(f"[QA] Parquet not found, falling back to raw parse")
        _write_status(session_id, "🔍 Parsing log records...", 15)
        file_bytes = _read_s3_bytes(s3_key)
        from src.main import parse_novatel_ascii
        text    = file_bytes.decode("utf-8", errors="replace"); del file_bytes
        main_df = parse_novatel_ascii(text); del text
        events  = _build_event_index(main_df)
        summary = _summarize_log(main_df, filename)

    # Store in Lambda memory for this invocation
    _log_store[session_id] = {
        "df": main_df, "summary": summary,
        "filename": filename, "events": events,
    }
    del main_df

    _write_status(session_id, "🧠 Running analysis pipeline...", 40)
    writer = _StreamWriter(session_id)

    answer = run_correlation_pipeline(question, session_id)

    # Write in chunks for streaming feel
    chunk_size = 150
    for i in range(0, len(answer), chunk_size):
        writer.write(answer[i:i + chunk_size])
        time.sleep(0.04)

    final = writer.finish()
    _write_result(session_id, {
        "done": True, "type": "qa",
        "result": final, "session_id": session_id,
    })
    return {"statusCode": 200, "body": "qa complete"}


# ── Scintillation: read scint Parquets, run pipeline ─────────────────

def _handle_scintillation(session_id: str, s3_key: str,
                          filename: str, question: str):
    from src.scintillation_handler import build_llm_prompt as scint_build_prompt
    from src.scintillation_detector import (
        enrich_range_df, enrich_range_with_elevation, epoch_health,
        enrich_bestpos_df, detect_scintillation, summarise_results,
    )
    from src.main import get_llm
    from langchain_core.messages import HumanMessage

    _write_status(session_id, "📂 Loading scintillation data from cloud...", 10)

    base = f"parsed/{session_id}"
    environment_type = "OPEN_SKY"

    # ── Load Parquets (fast) or fall back to raw parse ────────────────
    if _parquet_exists(f"{base}/rangea.parquet"):
        print("[SCINT] Loading Parquet files from S3")
        range_df   = _read_parquet(f"{base}/rangea.parquet")
        bestpos_df = _read_parquet(f"{base}/bestpos.parquet") \
                     if _parquet_exists(f"{base}/bestpos.parquet") else pd.DataFrame()
        satvis2_df = _read_parquet(f"{base}/satvis2.parquet") \
                     if _parquet_exists(f"{base}/satvis2.parquet") else pd.DataFrame()
    else:
        # Fall back: parse raw file but only extract scintillation logs
        print("[SCINT] Parquet not found, parsing raw file (scint logs only)")
        _write_status(session_id, "🔍 Parsing scintillation logs...", 15)
        file_bytes = _read_s3_bytes(s3_key)
        text  = file_bytes.decode("utf-8", errors="replace"); del file_bytes
        lines = text.splitlines(); del text

        from src.scintillation_log_decoders import (
            _parse_range_line, _parse_bestpos_line, _parse_satvis2_line,
        )
        range_obs, bestpos_obs, satvis2_obs = [], [], []
        for line in lines:
            s = line.strip()
            if s.startswith("#RANGEA,"):
                obs = _parse_range_line(s)
                if obs: range_obs.extend(obs)
            elif s.startswith("#BESTPOSA,"):
                row = _parse_bestpos_line(s)
                if row: bestpos_obs.append(row)
            elif s.startswith("#SATVIS2A,"):
                sats = _parse_satvis2_line(s)
                if sats: satvis2_obs.extend(sats)
        del lines
        range_df   = pd.DataFrame(range_obs);   del range_obs
        bestpos_df = pd.DataFrame(bestpos_obs); del bestpos_obs
        satvis2_df = pd.DataFrame(satvis2_obs); del satvis2_obs

    # ── Run scintillation pipeline on DataFrames ──────────────────────
    _write_status(session_id, "🔬 Running scintillation detection...", 30)
    t0 = time.time()

    range_df   = enrich_range_df(range_df)
    range_df   = enrich_range_with_elevation(range_df, satvis2_df,
                                             environment_type=environment_type)
    del satvis2_df

    epoch_health_df = epoch_health(range_df)
    bestpos_df      = enrich_bestpos_df(bestpos_df)
    scintillation_df = detect_scintillation(epoch_health_df, bestpos_df,
                                            environment_type=environment_type)

    summary = summarise_results(scintillation_df, epoch_health_df,
                                bestpos_df, range_df)
    del range_df, bestpos_df, epoch_health_df, scintillation_df
    print(f"[SCINT] Pipeline done in {time.time()-t0:.2f}s")

    summary["parsed_log_counts"] = {"note": "loaded from Parquet"}
    summary["environment_type"]  = environment_type

    if summary.get("pipeline_error"):
        error_text = f"⚠️ Scintillation pipeline error: {summary['pipeline_error']}"
        _write_result(session_id, {"done": True, "type": "scintillation",
                                   "result": error_text, "session_id": session_id})
        return {"statusCode": 200, "body": "scintillation error"}

    # ── Stream LLM answer ─────────────────────────────────────────────
    _write_status(session_id, "🧠 Generating scintillation report...", 70)
    writer = _StreamWriter(session_id)
    prompt = scint_build_prompt(summary, question)

    for chunk in get_llm().stream([HumanMessage(content=prompt)]):
        if chunk.content:
            writer.write(chunk.content)

    final = writer.finish()
    print(f"[SCINT] Complete, total={len(final)} chars")

    _write_result(session_id, {
        "done": True, "type": "scintillation",
        "result": final, "session_id": session_id,
    })
    return {"statusCode": 200, "body": "scintillation complete"}


# ── Main handler ──────────────────────────────────────────────────────

def handler(event, context):
    session_id = event.get("session_id", "unknown")
    s3_key     = event.get("s3_key", "")
    filename   = event.get("filename", "log.txt")
    question   = event.get("question", "")
    mode       = event.get("mode", "ingest" if not question else "qa")

    print(f"[LAMBDA] mode={mode} session={session_id} s3_key={s3_key}")

    try:
        if mode == "ingest":
            return _handle_ingest(session_id, s3_key, filename)
        elif mode == "scintillation":
            return _handle_scintillation(session_id, s3_key, filename, question)
        else:
            return _handle_qa(session_id, s3_key, filename, question)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[LAMBDA][ERROR] {tb}")
        _write_result(session_id, {
            "done": True, "type": "error",
            "result": f"Processing failed: {str(e)}\n\n```\n{tb}\n```",
            "session_id": session_id,
        })
        return {"statusCode": 500, "body": str(e)}
