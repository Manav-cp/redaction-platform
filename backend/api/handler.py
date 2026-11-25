"""REST handler Lambda behind API Gateway (HTTP API, Cognito JWT authorizer).

Routes
  POST   /upload-url            -> create document record + pre-signed S3 POST
  GET    /documents             -> list caller's documents
  GET    /documents/{docId}     -> status (+ pre-signed download URL when done)
  DELETE /documents/{docId}     -> delete record and stored files

The caller's identity comes ONLY from the verified JWT ("sub" claim), so a user
can never read or write another user's documents.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "documents"))
RAW_BUCKET = os.environ.get("RAW_BUCKET", "")
CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET", "")
MAX_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "10")) * 1024 * 1024
URL_TTL = int(os.environ.get("URL_TTL_SECONDS", "300"))  # 5 minutes
ALLOWED_EXT = (".pdf", ".txt")


class _Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        return super().default(o)


def _resp(status: int, body) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, cls=_Enc),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sanitize_filename(name: str) -> str:
    name = os.path.basename(name or "").strip()
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")[:80] or "document"
    ext = re.sub(r"[^A-Za-z0-9]", "", ext).lower()[:5]
    return f"{stem}.{ext}" if ext else stem


def _user_id(event) -> str:
    claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    return claims["sub"]


def create_upload(user_id: str, body: dict):
    file_name = sanitize_filename(body.get("fileName", ""))
    if not file_name.lower().endswith(ALLOWED_EXT):
        return _resp(400, {"message": "Only .pdf and .txt files are allowed"})
    size = int(body.get("size") or 0)
    if size <= 0 or size > MAX_BYTES:
        return _resp(400, {"message": f"File size must be between 1 byte and {MAX_BYTES // (1024 * 1024)} MB"})

    doc_id = str(uuid.uuid4())
    key = f"uploads/{user_id}/{doc_id}/{file_name}"
    content_type = "application/pdf" if file_name.lower().endswith(".pdf") else "text/plain"

    table.put_item(Item={
        "userId": user_id,
        "docId": doc_id,
        "fileName": file_name,
        "sizeBytes": size,
        "status": "PENDING_UPLOAD",
        "rawKey": key,
        "createdAt": _now(),
        "updatedAt": _now(),
    })

    post = s3.generate_presigned_post(
        Bucket=RAW_BUCKET,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, MAX_BYTES],
        ],
        ExpiresIn=URL_TTL,
    )
    return _resp(201, {"docId": doc_id, "fileName": file_name, "upload": post, "expiresIn": URL_TTL})


def list_documents(user_id: str):
    items, kwargs = [], {"KeyConditionExpression": Key("userId").eq(user_id)}
    while True:
        page = table.query(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page or len(items) >= 500:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    for it in items:
        it.pop("rawKey", None)
        it.pop("redactedKey", None)
    items.sort(key=lambda i: i.get("createdAt", ""), reverse=True)
    return _resp(200, {"documents": items})


def get_document(user_id: str, doc_id: str):
    item = table.get_item(Key={"userId": user_id, "docId": doc_id}).get("Item")
    if not item:
        return _resp(404, {"message": "Document not found"})
    if item.get("status") == "COMPLETED" and item.get("redactedKey"):
        item["downloadUrl"] = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": CLEAN_BUCKET,
                "Key": item["redactedKey"],
                "ResponseContentDisposition": f'attachment; filename="{item.get("redactedFileName", "redacted")}"',
            },
            ExpiresIn=URL_TTL,
        )
    item.pop("rawKey", None)
    item.pop("redactedKey", None)
    return _resp(200, item)


def delete_document(user_id: str, doc_id: str):
    item = table.get_item(Key={"userId": user_id, "docId": doc_id}).get("Item")
    if not item:
        return _resp(404, {"message": "Document not found"})
    if item.get("rawKey"):
        s3.delete_object(Bucket=RAW_BUCKET, Key=item["rawKey"])
    if item.get("redactedKey"):
        s3.delete_object(Bucket=CLEAN_BUCKET, Key=item["redactedKey"])
    table.delete_item(Key={"userId": user_id, "docId": doc_id})
    return _resp(200, {"deleted": doc_id})


def lambda_handler(event, context):
    try:
        route = event.get("routeKey", "")
        user_id = _user_id(event)
        params = event.get("pathParameters") or {}

        if route == "POST /upload-url":
            body = json.loads(event.get("body") or "{}")
            return create_upload(user_id, body)
        if route == "GET /documents":
            return list_documents(user_id)
        if route == "GET /documents/{docId}":
            return get_document(user_id, params["docId"])
        if route == "DELETE /documents/{docId}":
            return delete_document(user_id, params["docId"])
        return _resp(404, {"message": f"Unknown route {route}"})
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Bad request: %s", exc)
        return _resp(400, {"message": "Bad request"})
    except Exception:
        logger.exception("Unhandled error")
        return _resp(500, {"message": "Internal server error"})
