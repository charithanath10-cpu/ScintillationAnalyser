"""
novatel_processor.py — AWS Lambda for NovAtel log processing.

SQLite-backed. Scintillation flags computed INLINE during parse —
epoch_health rows written to DB as parsing proceeds.
No 2.5M row DataFrame ever loaded for scintillation.

Tables:
  main_log      — all parsed records (for Q&A)
  epoch_health  — pre-computed scint flags per epoch (~4k rows)
  bestpos       — BESTPOS records (~40k rows)
  satvis2       — satellite visibility (~400k rows)
  meta          — summary, events, filename
"""

import json, os, sys, io, time, traceback, sqlite3
import boto3
import pandas as pd
import numpy as np

sys.path.insert(0, "/var/task")

S3_BUCKET = os.environ["S3_BUCKET"]
REGION    = os.environ.get("AWS_REGION", "us-east-1")
_s3       = boto3.client("s3", region_name=REGION)
_TMP      = "/tmp"

# ── S3 helpers ────────────────────────────────────────────────────────

def _write_status(sid, status, pct=0):
    _s3.put_object(Bucket=S3_BUCKET, Key=f"results/{sid}_status.json",
        Body=json.dumps({"status": status, "pct": pct, "done": False}),
        ContentType="application/json")

def _write_result(sid, result):
    _s3.put_object(Bucket=S3_BUCKET, Key=f"results/{sid}.json",
        Body=json.dumps(result, default=str), ContentType="application/json")

def _read_s3_bytes(key):
    obj = _s3.get_object(Bucket=S3_BUCKET, Key=key)
    buf = io.BytesIO()
    for chunk in obj["Body"].iter_chunks(chunk_size=8*1024*1024):
        buf.write(chunk)
    data = buf.getvalue(); del buf
    return data

def _db_key(sid):        return f"parsed/{sid}.db"
def _db_path(sid):       return f"{_TMP}/{sid}.db"

def _db_on_s3(sid):
    try: _s3.head_object(Bucket=S3_BUCKET, Key=_db_key(sid)); return True
    except: return False

def _upload_db(sid):
    local = _db_path(sid)
    _s3.upload_file(local, S3_BUCKET, _db_key(sid))
    print(f"[DB] Uploaded {_db_key(sid)} ({os.path.getsize(local)/1024/1024:.1f} MB)")

def _download_db(sid):
    local = _db_path(sid)
    if os.path.exists(local):
        print(f"[DB] Cached {local}"); return local
    t0 = time.time()
    _s3.download_file(S3_BUCKET, _db_key(sid), local)
    print(f"[DB] Downloaded in {time.time()-t0:.2f}s ({os.path.getsize(local)/1024/1024:.1f} MB)")
    return local

# ── Stream writer ─────────────────────────────────────────────────────

class _SW:
    FLUSH = 200
    def __init__(self, sid):
        self.sid = sid; self._b = ""; self._t = ""; self._ts = time.time()
    def write(self, c):
        self._b += c; self._t += c
        if len(self._b) >= self.FLUSH or time.time()-self._ts > 1.5: self._fl()
    def _fl(self):
        if not self._b: return
        _s3.put_object(Bucket=S3_BUCKET, Key=f"results/{self.sid}_stream.txt",
            Body=self._t.encode(), ContentType="text/plain; charset=utf-8")
        self._b = ""; self._ts = time.time()
    def finish(self): self._fl(); return self._t


# ── Inline scintillation flag computation ────────────────────────────
# Tracks per-signal last values to compute diffs without holding all rows.

class _ScintTracker:
    """
    Computes epoch_health rows inline as RANGEA lines are parsed.
    Call add_obs(obs_list) for each RANGEA epoch.
    Call flush_epoch() when a new GPS second starts.
    Call get_epoch_rows() to get all accumulated epoch_health rows.
    """
    # Thresholds matching scintillation_detector.py
    CNO_WARN   = 5.0
    CNO_STRONG = 8.0
    ADR_EARLY  = 0.02
    ADR_STRONG = 0.05
    ADR_SEVERE = 0.10

    def __init__(self):
        # (constellation, signal, prn) -> (last_cn0, last_locktime)
        self._last: dict = {}
        self._epoch_obs: list = []   # current epoch buffer
        self._current_ts: tuple = None  # (gps_week, gps_seconds)
        self._epoch_rows: list = []  # accumulated results

    def add_obs(self, obs_list: list):
        """Feed one RANGEA line's observations (all share same timestamp)."""
        if not obs_list:
            return
        ts = (obs_list[0]["gps_week"], obs_list[0]["gps_seconds"])
        if ts != self._current_ts:
            if self._epoch_obs:
                self._compute_epoch()
            self._epoch_obs = list(obs_list)
            self._current_ts = ts
        else:
            self._epoch_obs.extend(obs_list)

    def _compute_epoch(self):
        """Compute flags for buffered epoch and add to results."""
        obs  = self._epoch_obs
        week = obs[0]["gps_week"]
        secs = obs[0]["gps_seconds"]
        n    = len(obs)

        n_cno = n_adr = n_lock = 0
        any_cno_true = any_adr_strong = any_adr_severe = False
        any_combined_true = any_combined_strong = any_lock = False

        for o in obs:
            key = (o.get("constellation",""), o.get("signal",""), o.get("prn",0))
            cn0      = o.get("cn0")   or 0.0
            adr      = o.get("adr_std") or 0.0
            locktime = o.get("locktime") or 0.0

            last = self._last.get(key)
            self._last[key] = (cn0, locktime)

            # cno_flag
            if last is not None:
                drop = last[0] - cn0
                if drop >= self.CNO_STRONG:
                    cno_f = "STRONG"; n_cno += 1; any_cno_true = True
                elif drop >= self.CNO_WARN:
                    cno_f = "WARN";   n_cno += 1; any_cno_true = True
                else:
                    cno_f = "NONE"
            else:
                cno_f = "NONE"

            # adr_flag
            if adr > self.ADR_SEVERE:
                adr_f = "SEVERE"; n_adr += 1; any_adr_severe = True; any_adr_strong = True
            elif adr > self.ADR_STRONG:
                adr_f = "STRONG"; n_adr += 1; any_adr_strong = True
            elif adr > self.ADR_EARLY:
                adr_f = "EARLY";  n_adr += 1
            else:
                adr_f = "NONE"

            # lock_flag
            lock_f = False
            if last is not None and locktime < last[1]:
                lock_f = True; n_lock += 1; any_lock = True

            # combined_flag
            cno_w = cno_f in ("WARN", "STRONG")
            adr_e = adr_f in ("EARLY", "STRONG", "SEVERE")
            if cno_f == "STRONG" and adr_f in ("STRONG", "SEVERE"):
                any_combined_strong = True; any_combined_true = True
            elif cno_w and adr_e:
                any_combined_true = True

        self._epoch_rows.append((
            week, secs,
            n, n_cno, n_adr, n_lock,
            int(any_cno_true), int(any_adr_strong), int(any_adr_severe),
            int(any_combined_true), int(any_combined_strong), int(any_lock),
        ))
        self._epoch_obs = []

    def finalize(self):
        """Flush last epoch."""
        if self._epoch_obs:
            self._compute_epoch()

    def get_rows(self):
        return self._epoch_rows


# ── Ingest ────────────────────────────────────────────────────────────

def _handle_ingest(session_id: str, s3_key: str, filename: str):
    from src.main import (_parse_line, _summarize_log,
                          _build_event_index, _log_store)
    from src.scintillation_log_decoders import (
        _parse_range_line, _parse_bestpos_line, _parse_satvis2_line)

    _write_status(session_id, "Reading file from S3...", 5)
    t0 = time.time()
    raw = _read_s3_bytes(s3_key)
    print(f"[INGEST] Read {len(raw)} bytes in {time.time()-t0:.2f}s")

    _write_status(session_id, "Parsing and building database...", 15)
    t1    = time.time()
    text  = raw.decode("utf-8", errors="replace"); del raw
    lines = text.splitlines(); del text

    db = _db_path(session_id)
    if os.path.exists(db): os.remove(db)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-32000")

    conn.execute("""CREATE TABLE main_log(
        log_name TEXT, log_name_raw TEXT, port TEXT, seq INTEGER,
        idle_pct REAL, time_status TEXT, week INTEGER, seconds REAL,
        utc_time TEXT, rx_status TEXT, fields_raw TEXT)""")
    conn.execute("""CREATE TABLE epoch_health(
        gps_week INTEGER, gps_seconds REAL,
        n_signals INTEGER, n_cno_flagged INTEGER,
        n_adr_flagged INTEGER, n_lock_flagged INTEGER,
        any_cno_true INTEGER, any_adr_strong INTEGER, any_adr_severe INTEGER,
        any_combined_true INTEGER, any_combined_strong INTEGER, any_lock_true INTEGER)""")
    conn.execute("""CREATE TABLE bestpos(
        gps_week REAL, gps_seconds REAL, sol_status TEXT, pos_type TEXT,
        latitude REAL, longitude REAL, height REAL,
        lat_std REAL, lon_std REAL, hgt_std REAL,
        diff_age REAL, num_svs REAL, num_sol_svs REAL)""")
    conn.execute("""CREATE TABLE satvis2(
        gps_week REAL, gps_seconds REAL, constellation TEXT,
        prn REAL, elevation REAL, azimuth REAL)""")
    conn.execute("""CREATE TABLE meta(
        filename TEXT, s3_key TEXT, records INTEGER,
        log_types INTEGER, summary TEXT, events_json TEXT)""")

    BATCH = 5000
    main_buf, bestpos_buf, satvis2_buf = [], [], []
    main_count = 0
    tracker = _ScintTracker()

    def _fl_main():
        if main_buf:
            conn.executemany("INSERT INTO main_log VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                [(r["log_name"],r["log_name_raw"],r["port"],r["seq"],
                  r["idle_pct"],r["time_status"],r["week"],r["seconds"],
                  r["utc_time"],r["rx_status"],r["fields_raw"]) for r in main_buf])
            main_buf.clear()

    def _fl_bestpos():
        if bestpos_buf:
            conn.executemany("INSERT INTO bestpos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(r["gps_week"],r["gps_seconds"],r.get("sol_status",""),
                  r.get("pos_type",""),r.get("latitude"),r.get("longitude"),
                  r.get("height"),r.get("lat_std"),r.get("lon_std"),
                  r.get("hgt_std"),r.get("diff_age"),r.get("num_svs"),
                  r.get("num_sol_svs")) for r in bestpos_buf])
            bestpos_buf.clear()

    def _fl_satvis2():
        if satvis2_buf:
            conn.executemany("INSERT INTO satvis2 VALUES(?,?,?,?,?,?)",
                [(r["gps_week"],r["gps_seconds"],r["constellation"],
                  r.get("prn"),r.get("elevation"),r.get("azimuth"))
                 for r in satvis2_buf])
            satvis2_buf.clear()

    eh_buf = []
    def _fl_epoch_health():
        if eh_buf:
            conn.executemany("INSERT INTO epoch_health VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                             eh_buf)
            eh_buf.clear()

    for line in lines:
        s = line.strip()
        if not s: continue

        rec = _parse_line(s)
        if rec:
            main_buf.append(rec); main_count += 1
            if len(main_buf) >= BATCH: _fl_main(); conn.commit()

        if s.startswith("#RANGEA,"):
            obs = _parse_range_line(s)
            if obs:
                tracker.add_obs(obs)
                # Every add_obs may complete a previous epoch — drain it immediately
                rows = tracker._epoch_rows
                if rows:
                    eh_buf.extend(rows)
                    tracker._epoch_rows = []
                    if len(eh_buf) >= BATCH:
                        _fl_epoch_health()
                        conn.commit()
        elif s.startswith("#BESTPOSA,"):
            row = _parse_bestpos_line(s)
            if row:
                bestpos_buf.append(row)
                if len(bestpos_buf) >= BATCH: _fl_bestpos()
        elif s.startswith("#SATVIS2A,"):
            sats = _parse_satvis2_line(s)
            if sats:
                satvis2_buf.extend(sats)
                if len(satvis2_buf) >= BATCH: _fl_satvis2()

    del lines
    tracker.finalize()
    eh_buf.extend(tracker._epoch_rows); tracker._epoch_rows = []
    _fl_main(); _fl_bestpos(); _fl_satvis2(); _fl_epoch_health()
    conn.commit()
    eh_count = conn.execute("SELECT COUNT(*) FROM epoch_health").fetchone()[0]
    print(f"[INGEST] Streamed {main_count} records + {eh_count} epoch_health rows in {time.time()-t1:.2f}s")

    _write_status(session_id, "Computing summary...", 70)
    main_df   = pd.read_sql("SELECT * FROM main_log", conn)
    for col in ["week","seconds","idle_pct","seq"]:
        if col in main_df.columns:
            main_df[col] = pd.to_numeric(main_df[col], errors="coerce")
    summary   = _summarize_log(main_df, filename)
    events    = _build_event_index(main_df)
    log_types = int(main_df["log_name"].nunique()) if not main_df.empty else 0
    del main_df

    conn.execute("INSERT INTO meta VALUES(?,?,?,?,?,?)",
        (filename, s3_key, main_count, log_types,
         summary, json.dumps(events, default=str)))
    conn.commit(); conn.close()

    _write_status(session_id, "Uploading database to cloud...", 85)
    _upload_db(session_id)

    _write_result(session_id, {
        "done": True, "type": "ingest",
        "result": (f"Parsed **{filename}**: {main_count} records across "
                   f"{log_types} log types. Ask me anything about this file."),
        "summary": summary, "log_types": log_types,
        "records": main_count, "session_id": session_id,
    })
    print(f"[INGEST] Complete in {time.time()-t0:.2f}s")
    return {"statusCode": 200, "body": "ingest complete"}


# ── Q&A ───────────────────────────────────────────────────────────────

def _handle_qa(session_id: str, s3_key: str, filename: str, question: str):
    from src.main import (_log_store, _summarize_log,
                          _build_event_index, run_correlation_pipeline)
    _write_status(session_id, "Loading parsed database...", 10)

    if _db_on_s3(session_id):
        db = _download_db(session_id)
        conn = sqlite3.connect(db)
        main_df = pd.read_sql("SELECT * FROM main_log", conn)
        for col in ["week","seconds","idle_pct","seq"]:
            if col in main_df.columns:
                main_df[col] = pd.to_numeric(main_df[col], errors="coerce")
        meta = conn.execute("SELECT summary, events_json FROM meta").fetchone()
        conn.close()
        summary = meta[0] if meta else _summarize_log(main_df, filename)
        events  = json.loads(meta[1]) if meta else _build_event_index(main_df)
    else:
        _write_status(session_id, "Parsing log records...", 15)
        raw = _read_s3_bytes(s3_key)
        from src.main import parse_novatel_ascii
        text    = raw.decode("utf-8", errors="replace"); del raw
        main_df = parse_novatel_ascii(text); del text
        events  = _build_event_index(main_df)
        summary = _summarize_log(main_df, filename)

    _log_store[session_id] = {"df": main_df, "summary": summary,
                               "filename": filename, "events": events}
    del main_df
    _write_status(session_id, "Running analysis pipeline...", 40)
    writer = _SW(session_id)
    answer = run_correlation_pipeline(question, session_id)
    for i in range(0, len(answer), 150):
        writer.write(answer[i:i+150]); time.sleep(0.04)
    final = writer.finish()
    _write_result(session_id, {"done": True, "type": "qa",
                                "result": final, "session_id": session_id})
    return {"statusCode": 200, "body": "qa complete"}


# ── Scintillation ─────────────────────────────────────────────────────

def _handle_scintillation(session_id: str, s3_key: str,
                          filename: str, question: str):
    from src.scintillation_handler import build_llm_prompt as scint_prompt
    from src.scintillation_detector import (
        enrich_bestpos_df, detect_scintillation, summarise_results,
        compute_file_level_rates,
    )
    from src.main import get_llm
    from langchain_core.messages import HumanMessage

    _write_status(session_id, "Loading scintillation data from cloud...", 10)

    if _db_on_s3(session_id):
        db = _download_db(session_id)
        conn = sqlite3.connect(db)
        print("[SCINT] Loading epoch_health + bestpos from SQLite")

        # epoch_health: ~4000 rows — tiny
        eh_df = pd.read_sql("SELECT * FROM epoch_health", conn)
        bp_df = pd.read_sql(
            "SELECT gps_week, gps_seconds, latitude, longitude, sol_status, "
            "pos_type, diff_age, num_svs FROM bestpos", conn)
        conn.close()

        for df in [eh_df, bp_df]:
            for col in ["gps_week", "gps_seconds"]:
                if col in df.columns:
                    df[col] = df[col].astype(float)

        # Rename epoch_health columns to match what detect_scintillation expects
        eh_df = eh_df.rename(columns={
            "any_lock_true": "any_lock_true",
        })
        # Add required columns that detect_scintillation uses
        eh_df["high_elev_lock_flag"] = False   # no elevation data path
        eh_df["n_high_elev_lock"]    = 0

    else:
        # Fallback: parse scint logs from raw file
        _write_status(session_id, "Parsing scintillation logs...", 15)
        raw   = _read_s3_bytes(s3_key)
        text  = raw.decode("utf-8", errors="replace"); del raw
        lines = text.splitlines(); del text
        from src.scintillation_log_decoders import (
            _parse_range_line, _parse_bestpos_line)
        from src.scintillation_detector import (enrich_range_df, epoch_health)
        range_obs, bestpos_obs = [], []
        for line in lines:
            s = line.strip()
            if s.startswith("#RANGEA,"):
                obs = _parse_range_line(s)
                if obs: range_obs.extend(obs)
            elif s.startswith("#BESTPOSA,"):
                row = _parse_bestpos_line(s)
                if row: bestpos_obs.append(row)
        del lines
        range_df = pd.DataFrame(range_obs); del range_obs
        bp_df    = pd.DataFrame(bestpos_obs); del bestpos_obs
        range_df = enrich_range_df(range_df)
        eh_df    = epoch_health(range_df); del range_df

    _write_status(session_id, "Running scintillation detection...", 35)
    t0 = time.time()

    bp_df    = enrich_bestpos_df(bp_df)
    scint_df = detect_scintillation(eh_df, bp_df, environment_type="OPEN_SKY")
    # Need a minimal range_df for summarise_results — create empty placeholder
    empty_range = pd.DataFrame(columns=["gps_week","gps_seconds","prn",
                                        "constellation","signal","cn0",
                                        "adr_std","locktime"])
    summary  = summarise_results(scint_df, eh_df, bp_df, empty_range)
    del eh_df, bp_df, scint_df
    print(f"[SCINT] Pipeline done in {time.time()-t0:.2f}s")

    if summary.get("pipeline_error"):
        _write_result(session_id, {"done": True, "type": "scintillation",
            "result": f"Pipeline error: {summary['pipeline_error']}",
            "session_id": session_id})
        return {"statusCode": 200, "body": "error"}

    _write_status(session_id, "Generating scintillation report...", 70)
    writer = _SW(session_id)
    prompt = scint_prompt(summary, question)
    for chunk in get_llm().stream([HumanMessage(content=prompt)]):
        if chunk.content: writer.write(chunk.content)
    final = writer.finish()
    _write_result(session_id, {"done": True, "type": "scintillation",
                                "result": final, "session_id": session_id})
    return {"statusCode": 200, "body": "scintillation complete"}


# ── Handler ───────────────────────────────────────────────────────────

def handler(event, context):
    sid      = event.get("session_id", "unknown")
    s3_key   = event.get("s3_key", "")
    filename = event.get("filename", "log.txt")
    question = event.get("question", "")
    mode     = event.get("mode", "ingest" if not question else "qa")
    print(f"[LAMBDA] mode={mode} session={sid} s3_key={s3_key}")
    try:
        if mode == "ingest":
            return _handle_ingest(sid, s3_key, filename)
        elif mode == "scintillation":
            return _handle_scintillation(sid, s3_key, filename, question)
        else:
            return _handle_qa(sid, s3_key, filename, question)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[LAMBDA][ERROR] {tb}")
        _write_result(sid, {"done": True, "type": "error",
            "result": f"Processing failed: {str(e)}\n```\n{tb}\n```",
            "session_id": sid})
        return {"statusCode": 500, "body": str(e)}
