"""
lambda_client.py — Helpers for invoking Lambda async and polling S3 for results.

Used by streamlit_app.py to offload all heavy processing to Lambda,
keeping Streamlit's process RAM under control.

Lambda details (hardcoded — no env var needed):
    ARN    : arn:aws:lambda:ap-south-1:767398019214:function:novatel_processor
    Region : ap-south-1
    S3     : naspocuser-s3  (ap-south-1)
"""

from __future__ import annotations

import json
import os
import time
import boto3
from botocore.config import Config as BotocoreConfig

# ── Hardcoded Lambda + S3 config ──────────────────────────────────────
LAMBDA_ARN     = "arn:aws:lambda:ap-south-1:767398019214:function:novatel_processor"
LAMBDA_REGION  = "ap-south-1"
S3_BUCKET      = os.environ.get("S3_BUCKET", "naspocuser-s3")
S3_REGION      = "ap-south-1"

POLL_INTERVAL  = 3    # seconds between S3 polls
MAX_WAIT       = 600  # 10 minutes max

_s3_client     = None
_lambda_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=S3_REGION,
            config=BotocoreConfig(read_timeout=30),
        )
    return _s3_client


def _lambda():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client(
            "lambda",
            region_name=LAMBDA_REGION,
            config=BotocoreConfig(read_timeout=30),
        )
    return _lambda_client


def invoke_processor_async(s3_key: str, filename: str,
                           session_id: str, question: str = "") -> bool:
    """
    Invoke the Lambda processor asynchronously (Event invocation — returns 202
    immediately). Lambda writes the result to S3 at results/{session_id}.json.
    Streamlit polls that S3 key every POLL_INTERVAL seconds.
    """
    payload = {
        "s3_key":     s3_key,
        "filename":   filename,
        "session_id": session_id,
        "question":   question,
    }
    try:
        resp = _lambda().invoke(
            FunctionName=LAMBDA_ARN,          # use full ARN — no env var needed
            InvocationType="Event",           # async
            Payload=json.dumps(payload).encode(),
        )
        status = resp.get("StatusCode", 0)
        print(f"[LAMBDA_CLIENT] Invoked Lambda async → HTTP {status}")
        return status == 202
    except Exception as e:
        print(f"[LAMBDA_CLIENT] Invoke failed: {e}")
        return False


def poll_status(session_id: str) -> dict | None:
    """Poll S3 for live status updates written by Lambda."""
    key = f"results/{session_id}_status.json"
    try:
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except Exception:
        return None


def poll_result(session_id: str) -> dict | None:
    """Poll S3 for the final result JSON written by Lambda."""
    key = f"results/{session_id}.json"
    try:
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except Exception:
        return None


def wait_for_result(session_id: str, status_callback=None) -> dict:
    """
    Block until Lambda writes results/{session_id}.json.
    Calls status_callback(msg) on every status update so the UI stays alive.
    Returns the result dict, or an error dict on timeout.
    """
    start = time.time()
    last_status = ""

    while time.time() - start < MAX_WAIT:
        result = poll_result(session_id)
        if result and result.get("done"):
            return result

        status = poll_status(session_id)
        if status:
            msg = status.get("status", "Processing...")
            if msg != last_status:
                last_status = msg
                if status_callback:
                    status_callback(msg)

        time.sleep(POLL_INTERVAL)

    return {
        "done": True,
        "type": "error",
        "result": "Processing timed out after 10 minutes. The file may be too large — try a smaller file.",
    }


def cleanup_result(session_id: str):
    """Delete result + status files from S3 after they've been consumed."""
    for key in [f"results/{session_id}.json",
                f"results/{session_id}_status.json"]:
        try:
            _s3().delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception:
            pass
