"""
novatel_processor.py — AWS Lambda function for NovAtel log processing.

SQLite-backed architecture:
  Ingest: parse raw ASCII → stream rows into SQLite → upload .db to S3
  Q&A: download .db from S3 → load main table → run correlation pipeline
  Scintillation: download .db → load rangea/bestpos/satvis2 → run pipeline

SQLite lives in /tmp (Lambda ephemeral storage, 512 MB).
No pyarrow, no JSON blobs — just standard library sqlite3.

S3 layout:
  logs/{filename}                 ← raw uploaded file
  parsed/{session_id}.db          ← SQLite database
  results/{session_id}.json       ← final answer
  results/{session_id}_status.json
  results/{session_id}_stream.txt ← incremental token stream

Tables in SQLite .db:
  main_log   — all parsed log records (for Q&A correlation pipeline)
  rangea     — RANGEA observations (for scintillation)
  bestpos    — BESTPOS records (for scintillation)
  satvis2    — SATVIS2 records (for scintillation)
  meta       — single-row: filename, s3_key, records, log_types, summary

Lambda config: Memory 3008 MB, Timeout 900s, Runtime python3.11
"""

import json, os, sys, io, time, traceback, sqlite3, tempfile
import boto3
import pandas as pd

sys.path.insert(0, "/var/task")

S3_BUCKET = os.environ["S3_BUCKET"]
REGION    = os.environ.get("AWS_REGION", "us-east-1")
_s3 = boto3.client("s3", region_name=REGION)

_TMP_DB_DIR = "/tmp"  # Lambda ephemeral storage


# ── S3 helpers ────────────────────────────────────────────────────────

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

def _db_key(session_id: str) -> str:
    return f"parsed/{session_id}.db"

def _db_local_path(session_id: str) -> str:
    return f"{_TMP_DB_DIR}/{session_id}.db"

def _db_exists_on_s3(session_id: str) -> bool:
    try:
        _s3.head_object(Bucket=S3_BUCKET, Key=_db_key(session_id))
        return True
    except Exception:
        return False

def _upload_db(session_id: str):
    """Upload the local SQLite file to S3."""
    local = _db_local_path(session_id)
    _s3.upload_file(local, S3_BUCKET, _db_key(session_id))
    size_mb = os.path.getsize(local) / 1024 / 1024
    print(f"[DB] Uploaded {_db_key(session_id)} ({size_mb:.1f} MB)")

def _download_db(session_id: str) -> str:
    """Download SQLite .db from S3 to /tmp. Returns local path."""
    local = _db_local_path(session_id)
    if os.path.exists(local):
        print(f"[DB] Using cached {local}")
        return local
    print(f"[DB] Downloading {_db_key(session_id)}...")
    t0 = time.time()
    _s3.download_file(S3_BUCKET, _db_key(session_id), local)
    print(f"[DB] Downloaded in {time.time()-t0:.2f}s ({os.path.getsize(local)/1024/1024:.1f} MB)")
    return local


# ── Streaming writer ──────────────────────────────────────────────────

class _StreamWriter:
    FLUSH_EVERY = 200
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._buf = ""; self._total = ""; self._last = time.time()
    def write(self, chunk: str):
        self._buf += chunk; self._total += chunk
        if len(self._buf) >= self.FLUSH_EVERY or time.time() - self._last > 1.5:
            self._flush()
    def _flush(self):
        if not self._buf: return
        _s3.put_object(Bucket=S3_BUCKET,
            Key=f"results/{self.session_id}_stream.txt",
            Body=self._total.encode("utf-8"),
            ContentType="text/plain; charset=utf-8")
        self._buf = ""; self._last = time.time()
    def finish(self) -> str:
        self._flush(); return self._total


# ── Ingest: parse raw file, write SQLite to S3 ───────────────────────

def _handle_ingest(session_id: str, s3_key: str, filename: str):
    from src.main import (
        _parse_line, _summarize_log, _build_event_index, _log_store,
    )
    from src.scintillation_log_decoders import (
        _parse_range_line, _parse_bestpos_line, _parse_satvis2_line,
    )

    _write_status(session_id, "📥 Reading file from S3...", 5)
    t0 = time.time()
    file_bytes = _read_s3_bytes(s3_key)
    print(f"[INGEST] Read {len(file_bytes)} bytes in {time.time()-t0:.2f}s")

    _write_status(session_id, "🔍 Parsing and storing log records...", 15)
    t1 = time.time()
    text  = file_bytes.decode("utf-8", errors="replace"); del file_bytes
    lines = text.splitlines(); del text

    # ── Create SQLite DB in /tmp ──────────────────────────────────────
    db_path = _db_local_path(session_id)
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64 MB cache

    # Create tables
    conn.execute("""CREATE TABLE main_log (
        log_name TEXT, log_name_raw TEXT, port TEXT, seq INTEGER,
        idle_pct REAL, time_status TEXT, week INTEGER, seconds REAL,
        utc_time TEXT, rx_status TEXT, fields_raw TEXT
    )""")
    conn.execute("""CREATE TABLE rangea (
        gps_week INTEGER, gps_seconds REAL, prn INTEGER,
        constellation TEXT, signal TEXT, adr_std REAL, cn0 REAL, locktime REAL
    )""")
    conn.execute("""CREATE TABLE bestpos (
        gps_week INTEGER, gps_seconds REAL, sol_status TEXT, pos_type TEXT,
        latitude REAL, longitude REAL, height REAL, lat_std REAL, lon_std REAL,
        hgt_std REAL, diff_age REAL, num_svs INTEGER, num_sol_svs INTEGER
    )""")
    conn.execute("""CREATE TABLE satvis2 (
        gps_week INTEGER, gps_seconds REAL, constellation TEXT,
        prn INTEGER, elevation REAL, azimuth REAL
    )""")
    conn.execute("""CREATE TABLE meta (
        filename TEXT, s3_key TEXT, records INTEGER,
        log_types INTEGER, summary TEXT, events_json TEXT
    )""")

    # ── Single pass: stream rows directly into SQLite ─────────────────
    BATCH = 5000
    main_buf, range_buf, bestpos_buf, satvis2_buf = [], [], [], []
    main_count = 0

    def _flush_main():
        if main_buf:
            conn.executemany(
                "INSERT INTO main_log VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(r["log_name"], r["log_name_raw"], r["port"], r["seq"],
                  r["idle_pct"], r["time_status"], r["week"], r["seconds"],
                  r["utc_time"], r["rx_status"], r["fields_raw"])
                 for r in main_buf])
            main_buf.clear()

    def _flush_range():
        if range_buf:
            conn.executemany(
                "INSERT INTO rangea VALUES (?,?,?,?,?,?,?,?)",
                [(r["gps_week"], r["gps_seconds"], r["prn"],
                  r["constellation"], r["signal"], r["adr_std"],
                  r["cn0"], r["locktime"]) for r in range_buf])
            range_buf.clear()

    def _flush_bestpos():
        if bestpos_buf:
            conn.executemany(
                "INSERT INTO bestpos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(r["gps_week"], r["gps_seconds"], r["sol_status"],
                  r["pos_type"], r.get("latitude"), r.get("longitude"),
                  r.get("height"), r.get("lat_std"), r.get("lon_std"),
                  r.get("hgt_std"), r.get("diff_age"), r.get("num_svs"),
                  r.get("num_sol_svs")) for r in bestpos_buf])
            bestpos_buf.clear()

    def _flush_satvis2():
        if satvis2_buf:
            conn.executemany(
                "INSERT INTO satvis2 VALUES (?,?,?,?,?,?)",
                [(r["gps_week"], r["gps_seconds"], r["constellation"],
                  r["prn"], r.get("elevation"), r.get("azimuth"))
                 for r in satvis2_buf])
            satvis2_buf.clear()

    for line in lines:
        s = line.strip()
        if not s:
            continue

        rec = _parse_line(s)
        if rec:
            main_buf.append(rec)
            main_count += 1
            if len(main_buf) >= BATCH:
                _flush_main()
                conn.commit()

        if s.startswith("#RANGEA,"):
            obs = _parse_range_line(s)
            if obs:
                range_buf.extend(obs)
                if len(range_buf) >= BATCH:
                    _flush_range()
        elif s.startswith("#BESTPOSA,"):
            row = _parse_bestpos_line(s)
            if row:
                bestpos_buf.append(row)
                if len(bestpos_buf) >= BATCH:
                    _flush_bestpos()
        elif s.startswith("#SATVIS2A,"):
            sats = _parse_satvis2_line(s)
            if sats:
                satvis2_buf.extend(sats)
                if len(satvis2_buf) >= BATCH:
                    _flush_satvis2()

    del lines
    _flush_main(); _flush_range(); _flush_bestpos(); _flush_satvis2()
    conn.commit()

    print(f"[INGEST] Streamed {main_count} records to SQLite in {time.time()-t1:.2f}s")
    _write_status(session_id, "📊 Building indices...", 60)

    # ── Indexes for fast queries ──────────────────────────────────────
    conn.execute("CREATE INDEX idx_main_log_name ON main_log(log_name)")
    conn.execute("CREATE INDEX idx_main_week_sec ON main_log(week, seconds)")
    conn.execute("CREATE INDEX idx_range_prn ON rangea(gps_week, gps_seconds, prn)")
    conn.execute("CREATE INDEX idx_bestpos_time ON bestpos(gps_week, gps_seconds)")
    conn.commit()

    # ── Build summary using pandas (load main_log once) ───────────────
    _write_status(session_id, "📈 Computing summary...", 70)
    main_df = pd.read_sql("SELECT * FROM main_log", conn)
    summary = _summarize_log(main_df, filename)
    events  = _build_event_index(main_df)
    log_types = int(main_df["log_name"].nunique()) if not main_df.empty else 0
    del main_df

    # Write meta
    conn.execute("INSERT INTO meta VALUES (?,?,?,?,?,?)",
                 (filename, s3_key, main_count, log_types,
                  summary, json.dumps(events, default=str)))
    conn.commit()
    conn.close()

    # ── Upload .db to S3 ──────────────────────────────────────────────
    _write_status(session_id, "☁️ Uploading parsed database to cloud...", 80)
    _upload_db(session_id)

    _write_result(session_id, {
        "done": True, "type": "ingest",
        "result": (
            f"Parsed **{filename}**: {main_count} records across "
            f"{log_types} log types. Ask me anything about this file."
        ),
        "summary": summary, "log_types": log_types, "records": main_count,
        "session_id": session_id,
    })
    print(f"[INGEST] Complete in {time.time()-t0:.2f}s")
    return {"statusCode": 200, "body": "ingest complete"}


# ── Q&A: load main_log from SQLite, run correlation pipeline ──────────

def _handle_qa(session_id: str, s3_key: str, filename: str, question: str):
    from src.main import (
        _log_store, _summarize_log, _build_event_index,
        run_correlation_pipeline,
    )

    _write_status(session_id, "📂 Loading parsed database...", 10)

    if _db_exists_on_s3(session_id):
        db_path = _download_db(session_id)
        conn = sqlite3.connect(db_path)

        main_df = pd.read_sql("SELECT * FROM main_log", conn)

        # Load event index and summary from meta table
        meta_row = conn.execute("SELECT summary, events_json FROM meta").fetchone()
        conn.close()

        if meta_row:
            summary     = meta_row[0]
            events      = json.loads(meta_row[1])
        else:
            summary = _summarize_log(main_df, filename)
            events  = _build_event_index(main_df)
    else:
        # Fallback: raw parse
        print(f"[QA] DB not found, falling back to raw parse")
        _write_status(session_id, "🔍 Parsing log records...", 15)
        file_bytes = _read_s3_bytes(s3_key)
        from src.main import parse_novatel_ascii
        text    = file_bytes.decode("utf-8", errors="replace"); del file_bytes
        main_df = parse_novatel_ascii(text); del text
        events  = _build_event_index(main_df)
        summary = _summarize_log(main_df, filename)

    _log_store[session_id] = {
        "df": main_df, "summary": summary,
        "filename": filename, "events": events,
    }
    del main_df

    _write_status(session_id, "🧠 Running analysis pipeline...", 40)
    writer = _StreamWriter(session_id)
    answer = run_correlation_pipeline(question, session_id)

    for i in range(0, len(answer), 150):
        writer.write(answer[i:i + 150])
        time.sleep(0.04)

    final = writer.finish()
    _write_result(session_id, {
        "done": True, "type": "qa",
        "result": final, "session_id": session_id,
    })
    return {"statusCode": 200, "body": "qa complete"}


# ── Scintillation: load scint tables from SQLite ──────────────────────

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

    if _db_exists_on_s3(session_id):
        db_path = _download_db(session_id)
        conn = sqlite3.connect(db_path)
        print("[SCINT] Loading from SQLite")
        range_df   = pd.read_sql("SELECT * FROM rangea",  conn)
        bestpos_df = pd.read_sql("SELECT * FROM bestpos", conn)
        satvis2_df = pd.read_sql("SELECT * FROM satvis2", conn)
        conn.close()
    else:
        # Fallback: parse raw file for scint logs only
        print("[SCINT] DB not found, parsing raw file")
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

    _write_status(session_id, "🔬 Running scintillation detection...", 30)
    t0 = time.time()

    range_df   = enrich_range_df(range_df)
    range_df   = enrich_range_with_elevation(range_df, satvis2_df,
                                             environment_type="OPEN_SKY")
    del satvis2_df
    epoch_health_df  = epoch_health(range_df)
    bestpos_df       = enrich_bestpos_df(bestpos_df)
    scintillation_df = detect_scintillation(epoch_health_df, bestpos_df,
                                            environment_type="OPEN_SKY")
    summary = summarise_results(scintillation_df, epoch_health_df,
                                bestpos_df, range_df)
    del range_df, bestpos_df, epoch_health_df, scintillation_df
    print(f"[SCINT] Pipeline done in {time.time()-t0:.2f}s")

    if summary.get("pipeline_error"):
        _write_result(session_id, {"done": True, "type": "scintillation",
                                   "result": f"⚠️ Error: {summary['pipeline_error']}",
                                   "session_id": session_id})
        return {"statusCode": 200, "body": "scintillation error"}

    _write_status(session_id, "🧠 Generating scintillation report...", 70)
    writer = _StreamWriter(session_id)
    prompt = scint_build_prompt(summary, question)

    for chunk in get_llm().stream([HumanMessage(content=prompt)]):
        if chunk.content:
            writer.write(chunk.content)

    final = writer.finish()
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
    """Write DataFrame as gzipped JSON — no pyarrow needed, fits in Lambda zip."""
    import gzip
    buf = gzip.compress(df.to_json(orient="records").encode("utf-8"), compresslevel=1)
    _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=buf)
    print(f"[STORE] wrote {key} ({len(buf)/1024:.0f} KB, {len(df)} rows)")

def _read_parquet(key: str) -> pd.DataFrame:
    """Read DataFrame from gzipped JSON."""
    import gzip
    obj = _s3.get_object(Bucket=S3_BUCKET, Key=key)
    buf = gzip.decompress(obj["Body"].read())
    df  = pd.read_json(buf, orient="records")
    print(f"[STORE] read {key} ({len(df)} rows)")
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

