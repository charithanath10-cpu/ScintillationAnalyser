"""
lambda_client.py — Synchronous Lambda invocation for heavy NovAtel log processing.

Invokes Lambda with RequestResponse (sync) — Lambda parses the file and returns
the result directly in the HTTP response.  No S3 polling required.

Lambda details:
    ARN    : arn:aws:lambda:ap-south-1:767398019214:function:novatel_processor
    Region : ap-south-1

The caller (streamlit_app.py) runs this in a background thread so the
heartbeat loop can keep the WebSocket alive while waiting.
"""

from __future__ import annotations

import json
import os
import boto3
from botocore.config import Config as BotocoreConfig

# ── Hardcoded Lambda config ───────────────────────────────────────────
LAMBDA_ARN    = "arn:aws:lambda:ap-south-1:767398019214:function:novatel_processor"
LAMBDA_REGION = "ap-south-1"

# Lambda can take up to 15 min — set read_timeout to 900s
_lambda_client = None


def _lambda():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client(
            "lambda",
            region_name=LAMBDA_REGION,
            config=BotocoreConfig(
                read_timeout=910,          # slightly above Lambda max timeout
                connect_timeout=10,
                retries={"max_attempts": 0},  # no retries — Streamlit handles failure
            ),
        )
    return _lambda_client


def invoke_processor(s3_key: str, filename: str,
                     session_id: str, question: str = "") -> dict:
    """
    Invoke Lambda SYNCHRONOUSLY (RequestResponse).  Blocks until Lambda
    returns or times out.

    Returns the parsed result dict from Lambda, e.g.:
        {"done": True, "type": "ingest", "result": "...", "summary": "..."}

    On error, raises an exception so the caller can show an error message.
    """
    payload = {
        "s3_key":     s3_key,
        "filename":   filename,
        "session_id": session_id,
        "question":   question,
    }

    print(f"[LAMBDA_CLIENT] Invoking {LAMBDA_ARN} sync s3_key={s3_key}")

    resp = _lambda().invoke(
        FunctionName=LAMBDA_ARN,
        InvocationType="RequestResponse",   # SYNC — wait for result
        Payload=json.dumps(payload).encode(),
    )

    # Lambda returns HTTP 200 for success (even if handler returned 500)
    status_code = resp.get("StatusCode", 0)
    func_error  = resp.get("FunctionError")      # "Handled" or "Unhandled" if Lambda crashed
    raw_body    = resp["Payload"].read()

    print(f"[LAMBDA_CLIENT] HTTP {status_code} FunctionError={func_error} "
          f"body_len={len(raw_body)}")

    if func_error:
        # Lambda itself crashed (out of memory, timeout, unhandled exception)
        raise RuntimeError(f"Lambda function error ({func_error}): {raw_body.decode()[:500]}")

    # Our handler always returns {"statusCode": ..., "body": "<json string>"}
    outer = json.loads(raw_body)
    body  = outer.get("body", "{}")
    result = json.loads(body) if isinstance(body, str) else body
    return result
