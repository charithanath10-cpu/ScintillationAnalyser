"""
lambda_client.py — Helpers for invoking Lambda and polling S3 for results/stream.
"""

from __future__ import annotations

import json
import os
import time
import boto3
from botocore.config import Config as BotocoreConfig

S3_BUCKET     = os.environ.get("S3_BUCKET", "naspocuser-s3")
REGION        = os.environ.get("AWS_REGION", "ap-south-1")
LAMBDA_ARN    = "arn:aws:lambda:ap-south-1:767398019214:function:novatel_processor"
LAMBDA_REGION = "ap-south-1"
POLL_INTERVAL = 0.5   # seconds between stream polls
MAX_WAIT      = 600   # 10 minutes max

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


def invoke_processor_async(s3_key: str, filename: str,
                           session_id: str, question: str = "",
                           mode: str = None) -> bool:
    """
    Invoke Lambda asynchronously (Event type — returns 202 immediately).
    mode: 'ingest' | 'qa' | 'scintillation' — auto-detected if not specified.
    """
    if mode is None:
        mode = "ingest" if not question else "qa"

    payload = {
        "s3_key":     s3_key,
        "filename":   filename,
        "session_id": session_id,
        "question":   question,
        "mode":       mode,
    }
    try:
        resp = _lambda().invoke(
            FunctionName=LAMBDA_ARN,
            InvocationType="Event",
            Payload=json.dumps(payload).encode(),
        )
        status = resp.get("StatusCode", 0)
        print(f"[LAMBDA_CLIENT] Invoked mode={mode} status={status} session={session_id}")
        return status == 202
    except Exception as e:
        print(f"[LAMBDA_CLIENT] Invoke failed: {e}")
        return False


def poll_status(session_id: str) -> dict | None:
    try:
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=f"results/{session_id}_status.json")
        return json.loads(obj["Body"].read())
    except Exception:
        return None


def poll_result(session_id: str) -> dict | None:
    try:
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=f"results/{session_id}.json")
        return json.loads(obj["Body"].read())
    except Exception:
        return None


def poll_stream(session_id: str) -> str | None:
    """Poll the stream file — returns full text written so far, or None."""
    try:
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=f"results/{session_id}_stream.txt")
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return None


def stream_result(session_id: str, on_chunk=None) -> str:
    """
    Poll S3 stream file until Lambda writes the final result.
    Calls on_chunk(new_text) whenever new content appears.
    Returns the full final text.
    """
    start      = time.time()
    last_len   = 0
    full_text  = ""

    while time.time() - start < MAX_WAIT:
        time.sleep(POLL_INTERVAL)

        # Check if done
        result = poll_result(session_id)
        if result and result.get("done"):
            # Get final text from result (most complete)
            final = result.get("result", full_text)
            # Deliver any remaining new content
            if on_chunk and len(final) > last_len:
                on_chunk(final[last_len:])
            return final

        # Poll stream for incremental content
        stream_text = poll_stream(session_id)
        if stream_text and len(stream_text) > last_len:
            new_content = stream_text[last_len:]
            last_len = len(stream_text)
            full_text = stream_text
            if on_chunk:
                on_chunk(new_content)

    return full_text or "⚠️ Processing timed out after 10 minutes."


def cleanup_result(session_id: str):
    """Delete result, status, and stream files from S3."""
    for key in [
        f"results/{session_id}.json",
        f"results/{session_id}_status.json",
        f"results/{session_id}_stream.txt",
    ]:
        try:
            _s3().delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception:
            pass
