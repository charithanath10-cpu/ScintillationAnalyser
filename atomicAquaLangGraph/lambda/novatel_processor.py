"""
novatel_processor.py — AWS Lambda function for heavy NovAtel log processing.

Invoked SYNCHRONOUSLY (RequestResponse) by Streamlit so the result is
returned directly — no S3 polling required.

Payload:
    {
        "s3_key":     "logs/myfile.ASCII",
        "filename":   "myfile.ASCII",
        "session_id": "session-abc123",
        "question":   ""   # empty = file ingest only; non-empty = file ingest + Q&A
    }

Response body (JSON-encoded string inside Lambda response):
    {
        "done":       true,
        "type":       "ingest" | "qa" | "error",
        "result":     "<markdown text>",
        "summary":    "<file summary string>",    # ingest only
        "session_id": "..."
    }

Lambda config recommended:
    Memory : 3008 MB
    Timeout: 900 s (15 minutes)
    Runtime: python3.11
    Handler: novatel_processor.handler
"""

import json
import os
import sys
import time
import traceback
import boto3

# ── bootstrap /var/task so src.* imports resolve ──────────────────────
sys.path.insert(0, "/var/task")

S3_BUCKET = os.environ.get("S3_BUCKET", "naspocuser-s3")
REGION    = os.environ.get("AWS_REGION", "ap-south-1")

_s3 = boto3.client("s3", region_name=REGION)


def handler(event, context):
    """
    Lambda entry point.  Returns result directly (sync invocation).
    """
    session_id = event.get("session_id", "unknown")
    s3_key     = event.get("s3_key", "")
    filename   = event.get("filename", "log.txt")
    question   = event.get("question", "")

    print(f"[LAMBDA] START session={session_id} s3_key={s3_key} filename={filename} question={question!r}")

    try:
        # ── Step 1: Read file from S3 (chunked, avoids double-copy) ──
        t0 = time.time()
        import io
        obj = _s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        buf = io.BytesIO()
        for chunk in obj["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
            buf.write(chunk)
        file_bytes = buf.getvalue()
        del buf
        print(f"[LAMBDA] Read {len(file_bytes)} bytes in {time.time()-t0:.2f}s")

        # ── Step 2: Import src modules (lazy — first call only) ───────
        from src.main import (          # noqa: E402
            ingest_log_file,
            preprocess_file,
            run_correlation_pipeline,
        )

        # ── Step 3: Pre-process (binary → ASCII conversion if needed) ─
        file_bytes, filename = preprocess_file(file_bytes, filename)

        # ── Step 4: Parse + ingest ────────────────────────────────────
        t1 = time.time()
        info = ingest_log_file(file_bytes, filename, session_id)
        del file_bytes  # free RAM — DataFrame is in _log_store now
        print(f"[LAMBDA] Ingested {info['records']} records in {time.time()-t1:.2f}s")

        if not question:
            # Pure file ingest — return summary immediately
            result_payload = {
                "done":       True,
                "type":       "ingest",
                "result": (
                    f"Parsed **{info['filename']}**: {info['records']} records across "
                    f"{info['log_types']} log types. Ask me anything about this file."
                ),
                "summary":    info["summary"],
                "session_id": session_id,
            }
            print(f"[LAMBDA] ingest complete in {time.time()-t0:.2f}s")
            return {"statusCode": 200, "body": json.dumps(result_payload, default=str)}

        # ── Step 5: Run Q&A pipeline (ingest already populates _log_store) ──
        t2 = time.time()
        answer = run_correlation_pipeline(question, session_id)
        print(f"[LAMBDA] Q&A pipeline complete in {time.time()-t2:.2f}s")

        result_payload = {
            "done":       True,
            "type":       "qa",
            "result":     answer,
            "session_id": session_id,
        }
        return {"statusCode": 200, "body": json.dumps(result_payload, default=str)}

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[LAMBDA][ERROR] {tb}")
        error_payload = {
            "done":       True,
            "type":       "error",
            "result":     f"Processing failed: {str(e)}\n\n```\n{tb}\n```",
            "session_id": session_id,
        }
        return {"statusCode": 500, "body": json.dumps(error_payload, default=str)}
