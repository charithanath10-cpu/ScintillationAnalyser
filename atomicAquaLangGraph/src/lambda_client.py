"""
lambda_client.py — Helpers for invoking Lambda async and polling S3 for results.

Used by streamlit_app.py to offload all heavy processing to Lambda,
keeping Streamlit's process RAM under control.
"""

from __future__ import annotations

import json
import os
import time
import boto3
from botocore.config import Config as BotocoreConfig

S3_BUCKET      = os.environ.get("S3_BUCKET", "naspocuser-s3")
REGION         = os.environ.get("AWS_REGION", "ap-south-1")
LAMBDA_ARN     = "arn:aws:lambda:ap-south-1:767398019214:function:novatel_processor"
LAMBDA_REGION  = "ap-south-1"
POLL_INTERVAL  = 3    # seconds between S3 polls
MAX_WAIT       = 600  # 10 minutes max

_s3_client     = None
_lambda_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=REGION,
                                  config=BotocoreConfig(read_timeout=30))
    return _s3_client


def _lambda():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda", region_name=LAMBDA_REGION,
                                      config=BotocoreConfig(read_timeout=30))
    return _lambda_client


def get_presigned_upload_url(filename: str, session_id: str) -> tuple[str, str]:
    """
    Generate a presigned S3 PUT URL so the browser can upload directly to S3,
    bypassing Streamlit's server entirely.

    Returns (presigned_url, s3_key).
    Note: presigned PUT requires the frontend to do a direct HTTP PUT —
    use this with a custom JS component or handle via Streamlit's st.components.
    For now this is used server-side to prepare the key before upload.
    """
    s3_key = f"logs/{session_id}/{filename}"
    url = _s3().generate_presigned_url(
        "put_object",
        Params={"Bucket": S3_BUCKET, "Key": s3_key},
        ExpiresIn=3600,
    )
    return url, s3_key


def invoke_processor_async(s3_key: str, filename: str,
                           session_id: str, question: str = "") -> bool:
    """
    Invoke the Lambda processor asynchronously (Event invocation type).
    Returns True if invocation succeeded, False otherwise.
    """
    payload = {
        "s3_key":     s3_key,
        "filename":   filename,
        "session_id": session_id,
        "question":   question,
    }
    try:
        resp = _lambda().invoke(
            FunctionName=LAMBDA_ARN,
            InvocationType="Event",   # async — returns 202 immediately
            Payload=json.dumps(payload).encode(),
        )
        status = resp.get("StatusCode", 0)
        print(f"[LAMBDA_CLIENT] Invoked {LAMBDA_ARN} async, status={status}")
        return status == 202
    except Exception as e:
        print(f"[LAMBDA_CLIENT] Invoke failed: {e}")
        return False


def poll_status(session_id: str) -> dict | None:
    """
    Poll S3 for the status file results/{session_id}_status.json.
    Returns the status dict or None if not yet written.
    """
    key = f"results/{session_id}_status.json"
    try:
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except _s3().exceptions.NoSuchKey:
        return None
    except Exception:
        return None


def poll_result(session_id: str) -> dict | None:
    """
    Poll S3 for the final result file results/{session_id}.json.
    Returns the result dict or None if not yet written.
    """
    key = f"results/{session_id}.json"
    try:
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except Exception:
        return None


def wait_for_result(session_id: str, status_callback=None) -> dict:
    """
    Block until Lambda writes results/{session_id}.json, calling
    status_callback(status_str) every POLL_INTERVAL seconds.

    Returns the result dict. On timeout returns an error dict.
    """
    start = time.time()
    last_status = ""

    while time.time() - start < MAX_WAIT:
        # Check for final result first
        result = poll_result(session_id)
        if result and result.get("done"):
            return result

        # Check for status update
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
        "result": "Processing timed out after 10 minutes. Try a smaller file.",
    }


def cleanup_result(session_id: str):
    """Delete the result and status files from S3 after consumption."""
    for key in [f"results/{session_id}.json",
                f"results/{session_id}_status.json"]:
        try:
            _s3().delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception:
            pass
