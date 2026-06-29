"""
novatel_processor.py — AWS Lambda function for heavy NovAtel log processing.

Triggered by Streamlit via direct Lambda invocation (not S3 event).
Reads the log file from S3, runs full parse + analysis, writes result JSON
back to S3 at results/{session_id}.json.

Streamlit polls S3 for results/{session_id}.json every few seconds.

Environment variables required:
    S3_BUCKET          — bucket name (same as Streamlit app)
    BEDROCK_MODEL_ID   — e.g. us.anthropic.claude-sonnet-4-6
    AWS_REGION         — e.g. us-east-1
    KB_ID              — Bedrock Knowledge Base ID

Lambda config recommended:
    Memory : 3008 MB  (parsing 300 MB file needs ~600 MB headroom)
    Timeout: 900 s    (15 minutes)
    Runtime: python3.11
"""

import json
import os
import sys
import time
import traceback
import boto3

# ── bootstrap src/ onto path so we can reuse existing modules ────────
# Lambda expects the zip to contain lambda/novatel_processor.py + src/
sys.path.insert(0, "/var/task")

S3_BUCKET = os.environ["S3_BUCKET"]
REGION    = os.environ.get("AWS_REGION", "us-east-1")

_s3 = boto3.client("s3", region_name=REGION)


def _write_status(session_id: str, status: str, pct: int = 0):
    """Write a lightweight status JSON to S3 so Streamlit can poll it."""
    key = f"results/{session_id}_status.json"
    _s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps({"status": status, "pct": pct, "done": False}),
        ContentType="application/json",
    )


def _write_result(session_id: str, result: dict):
    """Write the final result JSON to S3."""
    key = f"results/{session_id}.json"
    _s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(result, default=str),
        ContentType="application/json",
    )


def handler(event, context):
    """
    Lambda entry point.

    Event payload:
    {
        "s3_key":     "logs/myfile.ASCII",
        "filename":   "myfile.ASCII",
        "session_id": "session-abc123",
        "question":   ""   # empty string for file ingest; question text for Q&A
    }
    """
    session_id = event.get("session_id", "unknown")
    s3_key     = event.get("s3_key", "")
    filename   = event.get("filename", "log.txt")
    question   = event.get("question", "")

    print(f"[LAMBDA] session={session_id} s3_key={s3_key} filename={filename}")

    try:
        # ── Step 1: Read file from S3 ─────────────────────────────────
        _write_status(session_id, "📥 Reading file from S3...", 5)
        t0 = time.time()

        import io
        obj = _s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        buf = io.BytesIO()
        for chunk in obj["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
            buf.write(chunk)
        file_bytes = buf.getvalue()
        del buf
        print(f"[LAMBDA] Read {len(file_bytes)} bytes in {time.time()-t0:.2f}s")

        # ── Step 2: Import processing modules ────────────────────────
        _write_status(session_id, "🔍 Parsing log records...", 20)
        from src.main import (
            ingest_log_file,
            run_correlation_pipeline,
            _log_store,
        )

        # ── Step 3: Parse + ingest ────────────────────────────────────
        t1 = time.time()
        info = ingest_log_file(file_bytes, filename, session_id)
        del file_bytes  # free RAM
        print(f"[LAMBDA] Ingested {info['records']} records in {time.time()-t1:.2f}s")

        if not question:
            # Pure file ingest — return summary
            _write_status(session_id, "✅ File parsed successfully", 100)
            _write_result(session_id, {
                "done": True,
                "type": "ingest",
                "result": (
                    f"Parsed **{info['filename']}**: {info['records']} records across "
                    f"{info['log_types']} log types. Ask me anything about this file."
                ),
                "summary": info["summary"],
                "session_id": session_id,
            })
            return {"statusCode": 200, "body": "ingest complete"}

        # ── Step 4: Run Q&A pipeline ──────────────────────────────────
        _write_status(session_id, "🧠 Running analysis pipeline...", 60)
        t2 = time.time()
        answer = run_correlation_pipeline(question, session_id)
        print(f"[LAMBDA] Pipeline complete in {time.time()-t2:.2f}s")

        _write_result(session_id, {
            "done": True,
            "type": "qa",
            "result": answer,
            "session_id": session_id,
        })
        return {"statusCode": 200, "body": "qa complete"}

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
