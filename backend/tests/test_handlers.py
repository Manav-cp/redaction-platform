import json

import pytest


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[(Item["userId"], Item["docId"])] = Item

    def get_item(self, Key):
        item = self.items.get((Key["userId"], Key["docId"]))
        return {"Item": dict(item)} if item else {}

    def delete_item(self, Key):
        self.items.pop((Key["userId"], Key["docId"]), None)

    def query(self, **_):
        return {"Items": [dict(v) for v in self.items.values()]}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues):
        item = self.items.setdefault((Key["userId"], Key["docId"]), dict(Key))
        for part in UpdateExpression[4:].split(", "):
            n, v = part.split(" = ")
            item[ExpressionAttributeNames[n]] = ExpressionAttributeValues[v]


class FakeS3:
    def __init__(self):
        self.objects = {}

    def generate_presigned_post(self, Bucket, Key, **_):
        return {"url": f"https://{Bucket}.s3.amazonaws.com/", "fields": {"key": Key}}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://signed/{Params['Key']}"

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)

    def put_object(self, Bucket, Key, Body, **_):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        import io
        body = self.objects[(Bucket, Key)]
        return {"ContentLength": len(body), "Body": io.BytesIO(body)}


def _event(route, body=None, doc_id=None, sub="user-1"):
    return {
        "routeKey": route,
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": {"docId": doc_id} if doc_id else None,
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": sub}}}},
    }


@pytest.fixture
def api(api_module, monkeypatch):
    monkeypatch.setattr(api_module, "table", FakeTable())
    monkeypatch.setattr(api_module, "s3", FakeS3())
    return api_module


def test_sanitize_filename(api_module):
    assert api_module.sanitize_filename("../../etc/My Résumé (1).PDF") == "My_R_sum_1.pdf"
    assert api_module.sanitize_filename("") == "document"


def test_upload_rejects_bad_extension(api):
    r = api.lambda_handler(_event("POST /upload-url", {"fileName": "x.exe", "size": 10}), None)
    assert r["statusCode"] == 400


def test_upload_rejects_too_large(api):
    r = api.lambda_handler(_event("POST /upload-url", {"fileName": "x.pdf", "size": 50 * 1024 * 1024}), None)
    assert r["statusCode"] == 400


def test_upload_then_get_and_delete(api):
    r = api.lambda_handler(_event("POST /upload-url", {"fileName": "cv.pdf", "size": 1000}), None)
    assert r["statusCode"] == 201
    body = json.loads(r["body"])
    doc_id = body["docId"]
    assert body["upload"]["fields"]["key"] == f"uploads/user-1/{doc_id}/cv.pdf"

    listed = json.loads(api.lambda_handler(_event("GET /documents"), None)["body"])
    assert listed["documents"][0]["status"] == "PENDING_UPLOAD"
    assert "rawKey" not in listed["documents"][0]

    # other users cannot see it
    r = api.lambda_handler(_event("GET /documents/{docId}", doc_id=doc_id, sub="intruder"), None)
    assert r["statusCode"] == 404

    r = api.lambda_handler(_event("DELETE /documents/{docId}", doc_id=doc_id), None)
    assert r["statusCode"] == 200


def test_processor_end_to_end(processor_module, monkeypatch):
    from pdf_utils import build_pdf, extract_text
    table, s3 = FakeTable(), FakeS3()
    monkeypatch.setattr(processor_module, "table", table)
    monkeypatch.setattr(processor_module, "s3", s3)
    monkeypatch.setattr(processor_module, "CLEAN_BUCKET", "clean")

    key = "uploads/u1/d1/resume.pdf"
    s3.objects[("raw", key)] = build_pdf("Email: a.b@corp.com Phone: +91 98765 43210")
    event = {"Records": [{"s3": {"bucket": {"name": "raw"}, "object": {"key": key}}}]}
    processor_module.lambda_handler(event, None)

    item = table.items[("u1", "d1")]
    assert item["status"] == "COMPLETED"
    assert item["piiCounts"] == {"EMAIL": 1, "PHONE": 1}
    out = extract_text(s3.objects[("clean", "redacted/u1/d1/redacted_resume.pdf")])
    assert "a.b@corp.com" not in out and "[REDACTED:EMAIL]" in out


def test_processor_marks_bad_file_failed(processor_module, monkeypatch):
    table, s3 = FakeTable(), FakeS3()
    monkeypatch.setattr(processor_module, "table", table)
    monkeypatch.setattr(processor_module, "s3", s3)
    key = "uploads/u1/d2/bad.pdf"
    s3.objects[("raw", key)] = b"garbage"
    processor_module.lambda_handler(
        {"Records": [{"s3": {"bucket": {"name": "raw"}, "object": {"key": key}}}]}, None)
    assert table.items[("u1", "d2")]["status"] == "FAILED"


def test_cross_user_delete_rejected(api):
    # User A creates a document
    r = api.lambda_handler(
        _event("POST /upload-url",
               {"fileName": "private.pdf", "size": 1000},
               sub="user-A"), None)

    assert r["statusCode"] == 201
    doc_id = json.loads(r["body"])["docId"]

    # User B attempts to delete User A's document
    r = api.lambda_handler(
        _event("DELETE /documents/{docId}",
               doc_id=doc_id, sub="user-B"), None)

    assert r["statusCode"] == 404

    # Verify User A's document still exists
    r = api.lambda_handler(
        _event("GET /documents/{docId}",
               doc_id=doc_id, sub="user-A"), None)

    assert r["statusCode"] == 200
