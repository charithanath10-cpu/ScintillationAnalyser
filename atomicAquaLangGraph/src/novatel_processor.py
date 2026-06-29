"""
novatel_processor.py — AWS Lambda function for NovAtel log processing.

Three modes triggered by the 'mode' field in the event payload:

  mode='ingest'      — Parse file from S3, write result. No LLM calls.
  mode='qa'          — Re-parse file, run correlation pipeline, stream answer.
  mode='scintillation' — Re-parse file, run scintillation analysis, stream answer.

Streaming design:
  LLM tokens are appended to results/{session_id}_stream.txt on S3.
  Streamlit polls this file every 500ms and appends new content to the display.
  Final result is written to results/{session_id}.json with done=True.

Environment variables required:
    S3_BUCKET        — bucket name
    BEDROCK_MODEL_ID — e.g. us.anthropic.claude-sonnet-4-6
    AWS_REGION       — e.g. us-east-1
    KB_ID            — Bedrock Knowledge Base ID

Lambda config:
    Memory : 3008 MB
    Timeout: 900 s (15 min)
    Runtime: python3.11
"""

import json
import os
import sys
import io
import time
import traceback
import boto3

sys.path.insert(0, "/var/task")

S3_BUCKET = os.environ["S3_BUCKET"]
REGION    = os.environ.get("AWS_REGION", "us-east-1")

_s3 = boto3.client("s3", region_name=REGION)


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


def _append_stream_chunk(session_id: str, chunk: str):
    """Append a token chunk to the stream file on S3.
    Uses get/put since S3 doesn't support true append — but for streaming
    LLM tokens this is fast enough (each chunk is ~20-100 chars).
    We accumulate locally and flush every N chars to reduce S3 calls.
    """
    # This is called via the _StreamWriter helper below
    pass


class _StreamWriter:
    """Buffers LLM tokens and flushes to S3 periodically."""

    FLUSH_EVERY = 200   # flush after this many chars accumulated

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._buf = ""
        self._total = ""
        self._last_flush = time.time()

    def write(self, chunk: str):
        self._buf   += chunk
        self._total += chunk
        # Flush if buffer large enough OR enough time elapsed
        if len(self._buf) >= self.FLUSH_EVERY or (time.time() - self._last_flush) > 1.5:
            self._flush()

    def _flush(self):
        if not self._buf:
            return
        # Write the full accumulated text so Streamlit can just overwrite display
        _s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"results/{self.session_id}_stream.txt",
            Body=self._total.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )
        self._buf = ""
        self._last_flush = time.time()

    def finish(self):
        self._flush()
        return self._total


# ── File reader ───────────────────────────────────────────────────────

def _read_s3_file(s3_key: str) -> bytes:
    obj = _s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
    buf = io.BytesIO()
    for chunk in obj["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
        buf.write(chunk)
    data = buf.getvalue()
    del buf
    return data


# ── Mode handlers ─────────────────────────────────────────────────────

def _handle_ingest(session_id: str, s3_key: str, filename: str):
    """Parse file only — no LLM, no scintillation. Fast and low RAM."""
    from src.main import ingest_log_file

    _write_status(session_id, "📥 Reading file from S3...", 5)
    t0 = time.time()
    file_bytes = _read_s3_file(s3_key)
    print(f"[LAMBDA] Read {len(file_bytes)} bytes in {time.time()-t0:.2f}s")

    _write_status(session_id, "🔍 Parsing log records...", 20)
    t1 = time.time()
    info = ingest_log_file(file_bytes, filename, session_id)
    del file_bytes
    print(f"[LAMBDA] Ingested {info['records']} records in {time.time()-t1:.2f}s")

    _write_result(session_id, {
        "done": True,
        "type": "ingest",
        "result": (
            f"Parsed **{info['filename']}**: {info['records']} records across "
            f"{info['log_types']} log types. Ask me anything about this file."
        ),
        "summary": info["summary"],
        "log_types": info["log_types"],
        "records": info["records"],
        "session_id": session_id,
    })
    return {"statusCode": 200, "body": "ingest complete"}


def _handle_qa(session_id: str, s3_key: str, filename: str, question: str):
    """Re-parse file and answer a question. Streams tokens to S3."""
    from src.main import ingest_log_file, run_correlation_pipeline

    _write_status(session_id, "📥 Loading file data...", 5)
    file_bytes = _read_s3_file(s3_key)
    print(f"[LAMBDA-QA] Read {len(file_bytes)} bytes")

    _write_status(session_id, "🔍 Parsing log records...", 15)
    info = ingest_log_file(file_bytes, filename, session_id)
    del file_bytes
    print(f"[LAMBDA-QA] Ingested {info['records']} records")

    _write_status(session_id, "🧠 Running analysis pipeline...", 40)
    writer = _StreamWriter(session_id)

    # run_correlation_pipeline returns a full string (non-streaming)
    # We write it in chunks to simulate streaming to S3
    answer = run_correlation_pipeline(question, session_id)

    # Write the full answer in chunks to the stream file
    chunk_size = 150
    for i in range(0, len(answer), chunk_size):
        writer.write(answer[i:i + chunk_size])
        time.sleep(0.05)  # small delay so Streamlit can poll incrementally

    final_text = writer.finish()

    _write_result(session_id, {
        "done": True,
        "type": "qa",
        "result": final_text,
        "session_id": session_id,
    })
    return {"statusCode": 200, "body": "qa complete"}


def _handle_scintillation(session_id: str, s3_key: str, filename: str, question: str):
    """Re-fetch file bytes and run scintillation pipeline only.
    Does NOT do full ingest — avoids double-loading 315 MB in RAM."""
    from src.scintillation_handler import (
        analyse_bytes as scint_analyse_bytes,
        build_llm_prompt as scint_build_prompt,
    )
    from src.main import get_llm
    from langchain_core.messages import HumanMessage

    _write_status(session_id, "📥 Loading file for scintillation analysis...", 5)
    file_bytes = _read_s3_file(s3_key)
    print(f"[LAMBDA-SCINT] Read {len(file_bytes)} bytes")

    _write_status(session_id, "🔬 Running scintillation detection pipeline...", 20)
    t0 = time.time()
    summary = scint_analyse_bytes(file_bytes, environment_type="OPEN_SKY")
    del file_bytes  # free RAM before LLM call
    print(f"[LAMBDA-SCINT] Pipeline done in {time.time()-t0:.2f}s")

    if summary.get("pipeline_error"):
        error_text = f"⚠️ Scintillation pipeline error: {summary['pipeline_error']}"
        _write_result(session_id, {"done": True, "type": "scintillation",
                                   "result": error_text, "session_id": session_id})
        return {"statusCode": 200, "body": "scintillation error"}

    _write_status(session_id, "🧠 Generating scintillation report...", 70)
    writer = _StreamWriter(session_id)
    prompt = scint_build_prompt(summary, question)

    # Stream LLM tokens to S3
    for chunk in get_llm().stream([HumanMessage(content=prompt)]):
        if chunk.content:
            writer.write(chunk.content)

    final_text = writer.finish()
    print(f"[LAMBDA-SCINT] Streaming complete, total={len(final_text)} chars")

    _write_result(session_id, {
        "done": True,
        "type": "scintillation",
        "result": final_text,
        "session_id": session_id,
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
            "done": True,
            "type": "error",
            "result": f"Processing failed: {str(e)}\n\n```\n{tb}\n```",
            "session_id": session_id,
        })
        return {"statusCode": 500, "body": str(e)}
