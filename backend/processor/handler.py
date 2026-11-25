"""Processing engine Lambda.

Trigger : S3 ObjectCreated on the raw-uploads bucket (prefix "uploads/").
Key form: uploads/<userId>/<docId>/<original file name>
Output  : redacted file in the clean bucket at redacted/<userId>/<docId>/...
State   : DynamoDB item (userId, docId) moves PROCESSING -> COMPLETED | FAILED
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3

from pdf_utils import build_pdf, extract_text
from pii_detector import detect_and_redact

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "documents"))
CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET", "")
USE_COMPREHEND = os.environ.get("USE_COMPREHEND", "false").lower() == "true"
MAX_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "10")) * 1024 * 1024

_comprehend = boto3.client("comprehend") if USE_COMPREHEND else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _set_status(user_id: str, doc_id: str, status: str, **extra):
    names = {"#s": "status", "#u": "updatedAt"}
    values = {":s": status, ":u": _now()}
    sets = ["#s = :s", "#u = :u"]
    for i, (k, v) in enumerate(extra.items()):
        names[f"#k{i}"] = k
        values[f":v{i}"] = v
        sets.append(f"#k{i} = :v{i}")
    table.update_item(
        Key={"userId": user_id, "docId": doc_id},
        UpdateExpression="SET " + ", ".join(sets),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def parse_key(key: str):
    parts = key.split("/", 3)
    if len(parts) != 4 or parts[0] != "uploads":
        raise ValueError(f"Unexpected object key: {key}")
    _, user_id, doc_id, file_name = parts
    return user_id, doc_id, file_name


def process_object(bucket: str, key: str):
    user_id, doc_id, file_name = parse_key(key)
    started = time.time()
    _set_status(user_id, doc_id, "PROCESSING")
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        if obj["ContentLength"] > MAX_BYTES:
            raise ValueError("File exceeds maximum allowed size")
        body = obj["Body"].read()
        lower = file_name.lower()

        if lower.endswith(".pdf"):
            text = extract_text(body)
        elif lower.endswith(".txt"):
            text = body.decode("utf-8", errors="replace")
        else:
            raise ValueError("Only .pdf and .txt files are supported")

        if not text.strip():
            raise ValueError("No extractable text found (scanned image PDFs are not supported)")

        redacted, counts, engine = detect_and_redact(text, _comprehend)
        base = file_name.rsplit(".", 1)[0]

        if lower.endswith(".pdf"):
            out_name = f"redacted_{base}.pdf"
            out_body = build_pdf(redacted, title=f"Redacted copy of {file_name}")
            content_type = "application/pdf"
        else:
            out_name = f"redacted_{base}.txt"
            out_body = redacted.encode("utf-8")
            content_type = "text/plain; charset=utf-8"

        out_key = f"redacted/{user_id}/{doc_id}/{out_name}"
        s3.put_object(
            Bucket=CLEAN_BUCKET,
            Key=out_key,
            Body=out_body,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

        elapsed_ms = int((time.time() - started) * 1000)
        _set_status(
            user_id, doc_id, "COMPLETED",
            redactedKey=out_key,
            redactedFileName=out_name,
            piiCounts={k: int(v) for k, v in counts.items()},
            piiTotal=int(sum(counts.values())),
            engine=engine,
            processingMs=elapsed_ms,
        )
        logger.info(json.dumps({"event": "processed", "docId": doc_id, "piiTotal": sum(counts.values()),
                                "engine": engine, "ms": elapsed_ms}))
    except ValueError as exc:
        # Bad input: mark failed, do not raise (retrying will not help)
        logger.warning("Rejected %s: %s", key, exc)
        _set_status(user_id, doc_id, "FAILED", errorMessage=str(exc)[:500])
    except Exception as exc:
        # Unexpected error: mark failed and raise so Lambda retries + alarm fires
        logger.exception("Processing failed for %s", key)
        _set_status(user_id, doc_id, "FAILED", errorMessage=str(exc)[:500])
        raise


def lambda_handler(event, context):
    records = event.get("Records", [])
    for record in records:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        process_object(bucket, key)
    return {"processed": len(records)}
