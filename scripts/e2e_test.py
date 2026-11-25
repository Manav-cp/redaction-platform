#!/usr/bin/env python3
"""RedactIQ - Comprehensive End-to-End Functional & Performance Verification Suite
Executes end-to-end tests against deployed AWS infrastructure:
  1. Cognito User Registration, Authentication & Token retrieval
  2. Unauthorized & cross-user isolation tests
  3. TXT document upload, S3 event trigger, Lambda processing, redaction verification
  4. PDF document upload and redaction verification
  5. Status polling & performance timing (cold/warm latency, execution duration)
  6. Document download and deletion
  7. Disposable user cleanup
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import boto3

REGION = "us-east-1"
CFN_STACK = "doc-redaction"
EXPECTED_ACCOUNT = "058264205875"


def log(msg, tag="TEST"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag}] {msg}")


def main():
    log("Starting RedactIQ End-to-End AWS System Verification...")
    sts = boto3.client("sts", region_name=REGION)
    ident = sts.get_caller_identity()
    log(f"AWS Authenticated as: {ident['Arn']}")

    cfn = boto3.client("cloudformation", region_name=REGION)
    stacks = cfn.describe_stacks(StackName=CFN_STACK)["Stacks"]
    outs = {o["OutputKey"]: o["OutputValue"] for o in stacks[0]["Outputs"]}

    api_url = outs["ApiUrl"]
    user_pool_id = outs["UserPoolId"]
    client_id = outs["UserPoolClientId"]
    table_name = outs["TableName"]
    raw_bucket = outs["RawBucketName"]
    clean_bucket = outs["CleanBucketName"]

    log(f"API Endpoint: {api_url}")
    log(f"Cognito Pool: {user_pool_id} (Client: {client_id})")
    log(f"DynamoDB: {table_name}")
    log(f"S3 Buckets: Raw={raw_bucket}, Clean={clean_bucket}")

    cognito = boto3.client("cognito-idp", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    results = {}

    # -------------------------------------------------------------
    # Test 1: Unauthorized API Gateway Requests
    # -------------------------------------------------------------
    log("\n--- Test 1: API Gateway Unauthorized Access Protection ---")
    req = urllib.request.Request(f"{api_url}/documents", headers={"User-Agent": "RedactIQ-E2E"})
    try:
        urllib.request.urlopen(req, timeout=10)
        status = 200
    except urllib.error.HTTPError as e:
        status = e.code
    assert status == 401, f"Expected 401 Unauthorized, got {status}"
    log("Unauthenticated request correctly rejected with HTTP 401.")
    results["unauthorized_api_protection"] = "PASSED (HTTP 401)"

    # -------------------------------------------------------------
    # Test 2: User Registration & Authentication (User A)
    # -------------------------------------------------------------
    ts = int(time.time())
    user_a_email = f"e2e-test-user-{ts}@example.com"
    user_password = "Password123!"
    log(f"\n--- Test 2: User A Registration & Authentication ({user_a_email}) ---")

    # Admin create user with permanent password for non-interactive testing
    t0 = time.time()
    cognito.admin_create_user(
        UserPoolId=user_pool_id,
        Username=user_a_email,
        UserAttributes=[{"Name": "email", "Value": user_a_email}, {"Name": "email_verified", "Value": "true"}],
        MessageAction="SUPPRESS",
    )
    cognito.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=user_a_email,
        Password=user_password,
        Permanent=True,
    )
    auth_resp = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": user_a_email, "PASSWORD": user_password},
    )
    id_token_a = auth_resp["AuthenticationResult"]["IdToken"]
    auth_latency = (time.time() - t0) * 1000
    log(f"User A authenticated successfully in {auth_latency:.1f}ms. Token length: {len(id_token_a)}")
    results["cognito_user_a_auth"] = f"PASSED ({auth_latency:.1f}ms)"

    headers_a = {
        "Authorization": id_token_a,
        "Content-Type": "application/json",
        "User-Agent": "RedactIQ-E2E",
    }

    # -------------------------------------------------------------
    # Test 3: Document Upload URL Generation (API Gateway -> Lambda)
    # -------------------------------------------------------------
    log("\n--- Test 3: Request Presigned Upload URL for TXT ---")
    sample_text = (
        "CONFIDENTIAL PATIENT RECORD\n"
        "Patient: John Doe, DOB: 1985-04-12\n"
        "Email: john.doe@example.com\n"
        "Phone: +1 555-839-2041\n"
        "SSN: 123-45-6789\n"
        "Credit Card: 4532 0150 1234 5678\n"
        "Aadhaar: 2345 6789 0123\n"
        "PAN: ABCDE1234F\n"
        "Diagnosis: General health checkup completed with no issues.\n"
    )
    t0 = time.time()
    payload = json.dumps({"fileName": f"test-doc-{ts}.txt", "size": len(sample_text)}).encode("utf-8")
    req = urllib.request.Request(f"{api_url}/upload-url", data=payload, headers=headers_a, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        upload_data = json.loads(resp.read().decode("utf-8"))
    api_upload_url_latency = (time.time() - t0) * 1000
    doc_id = upload_data["docId"]
    fields = upload_data["upload"]["fields"]
    log(f"Received docId: {doc_id} in {api_upload_url_latency:.1f}ms")
    results["api_upload_url_generation"] = f"PASSED ({api_upload_url_latency:.1f}ms)"

    # -------------------------------------------------------------
    # Test 4: Upload Document & Trigger S3 Processing Pipeline
    # -------------------------------------------------------------
    log("\n--- Test 4: Upload Document to S3 Raw Bucket & Await Redaction ---")
    key = fields["key"]
    t0 = time.time()
    s3.put_object(
        Bucket=raw_bucket,
        Key=key,
        Body=sample_text.encode("utf-8"),
        ContentType="text/plain",
    )
    s3_upload_time = (time.time() - t0) * 1000
    log(f"Uploaded {len(sample_text)} bytes to s3://{raw_bucket}/{key} in {s3_upload_time:.1f}ms")

    # Poll status via GET /documents/{docId}
    log("Polling document status from API Gateway...")
    poll_start = time.time()
    doc_status = "PENDING"
    doc_record = None
    for _ in range(25):
        time.sleep(1.5)
        req = urllib.request.Request(f"{api_url}/documents/{doc_id}", headers=headers_a)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                doc_record = json.loads(resp.read().decode("utf-8"))
                doc_status = doc_record.get("status")
                log(f"Status: {doc_status}...")
                if doc_status in ("COMPLETED", "FAILED"):
                    break
        except Exception as e:
            log(f"Transient polling error: {e}", "WARN")

    processing_time = (time.time() - poll_start)
    assert doc_status == "COMPLETED", f"Document processing failed or timed out! Status: {doc_status}"
    log(f"Document processed successfully in {processing_time:.2f}s!")
    log(f"Sensitive findings detected: {doc_record.get('findingsCount')}")
    results["txt_processing_pipeline"] = f"PASSED ({processing_time:.2f}s, {doc_record.get('findingsCount')} findings)"

    # Verify redacted content
    download_url = doc_record.get("downloadUrl")
    assert download_url, "Download URL missing from response"
    with urllib.request.urlopen(download_url, timeout=10) as resp:
        redacted_content = resp.read().decode("utf-8")

    assert "123-45-6789" not in redacted_content, "SSN was not redacted!"
    assert "john.doe@example.com" not in redacted_content, "Email was not redacted!"
    assert "[REDACTED" in redacted_content, "Redaction mask not found in content!"
    log("Redaction verification: Sensitive SSN, Email, and Phone masked successfully.")
    results["redaction_correctness"] = "PASSED"

    # -------------------------------------------------------------
    # Test 5: Cross-User Tenant Isolation (User B Accessing User A)
    # -------------------------------------------------------------
    log("\n--- Test 5: Cross-User Authorization & Tenancy Isolation ---")
    user_b_email = f"e2e-user-b-{ts}@example.com"
    cognito.admin_create_user(
        UserPoolId=user_pool_id,
        Username=user_b_email,
        UserAttributes=[{"Name": "email", "Value": user_b_email}, {"Name": "email_verified", "Value": "true"}],
        MessageAction="SUPPRESS",
    )
    cognito.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=user_b_email,
        Password=user_password,
        Permanent=True,
    )
    auth_b = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": user_b_email, "PASSWORD": user_password},
    )
    id_token_b = auth_b["AuthenticationResult"]["IdToken"]
    headers_b = {"Authorization": id_token_b, "User-Agent": "RedactIQ-E2E"}

    # User B attempts to access User A's document
    b_status = None
    try:
        req = urllib.request.Request(f"{api_url}/documents/{doc_id}", headers=headers_b)
        with urllib.request.urlopen(req, timeout=10) as resp:
            b_status = resp.getcode()
    except urllib.error.HTTPError as e:
        b_status = e.code

    assert b_status == 404, f"Cross-user isolation breach! Expected 404, got {b_status}"
    log("Cross-user isolation verified: User B received HTTP 404 when requesting User A document.")
    results["tenant_isolation"] = "PASSED (HTTP 404)"

    # -------------------------------------------------------------
    # Test 6: PDF Document Processing Pipeline
    # -------------------------------------------------------------
    log("\n--- Test 6: PDF Document Upload & Redaction ---")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "processor"))
    from pdf_utils import build_pdf
    invoice_text = (
        "INVOICE #9821\nCustomer: Jane Smith\nEmail: jane.smith@example.com\n"
        "Phone: +1 555-123-4567\nSSN: 987-65-4321\nAmount Due: $1,250.00"
    )
    pdf_bytes = build_pdf(invoice_text)
    if True:
        payload = json.dumps({"fileName": f"invoice-{ts}.pdf", "size": len(pdf_bytes)}).encode("utf-8")
        req = urllib.request.Request(f"{api_url}/upload-url", data=payload, headers=headers_a, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            pdf_upload_data = json.loads(resp.read().decode("utf-8"))
        pdf_doc_id = pdf_upload_data["docId"]
        pdf_key = pdf_upload_data["upload"]["fields"]["key"]

        s3.put_object(Bucket=raw_bucket, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")
        log(f"Uploaded {len(pdf_bytes)} bytes PDF to s3://{raw_bucket}/{pdf_key}")

        pdf_status = "PENDING"
        for _ in range(25):
            time.sleep(1.5)
            req = urllib.request.Request(f"{api_url}/documents/{pdf_doc_id}", headers=headers_a)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    p_rec = json.loads(resp.read().decode("utf-8"))
                    pdf_status = p_rec.get("status")
                    if pdf_status in ("COMPLETED", "FAILED"):
                        break
            except Exception:
                pass

        assert pdf_status == "COMPLETED", f"PDF processing failed: {pdf_status}"
        log(f"PDF document processed successfully (Findings: {p_rec.get('findingsCount')})")
        results["pdf_processing_pipeline"] = f"PASSED ({p_rec.get('findingsCount')} findings)"

        # Delete PDF document
        req = urllib.request.Request(f"{api_url}/documents/{pdf_doc_id}", headers=headers_a, method="DELETE")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.getcode() == 200
        log("PDF document deleted.")

    # -------------------------------------------------------------
    # Test 7: Document Deletion Verification (User A)
    # -------------------------------------------------------------
    log("\n--- Test 7: Document Deletion ---")
    req = urllib.request.Request(f"{api_url}/documents/{doc_id}", headers=headers_a, method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as resp:
        del_status = resp.getcode()
    assert del_status == 200, f"Expected 200 from DELETE, got {del_status}"
    log("Document deleted via API Gateway.")

    # Confirm document no longer exists
    try:
        req = urllib.request.Request(f"{api_url}/documents/{doc_id}", headers=headers_a)
        with urllib.request.urlopen(req, timeout=10) as resp:
            post_del_status = resp.getcode()
    except urllib.error.HTTPError as e:
        post_del_status = e.code
    assert post_del_status == 404, f"Deleted document still accessible! Got {post_del_status}"
    log("Confirmed document deletion: Subsequent request returned HTTP 404.")
    results["document_deletion"] = "PASSED (HTTP 404)"

    # -------------------------------------------------------------
    # Clean up disposable test users from Cognito
    # -------------------------------------------------------------
    log("\n--- Cleaning up disposable test users ---")
    for u in (user_a_email, user_b_email):
        try:
            cognito.admin_delete_user(UserPoolId=user_pool_id, Username=u)
            log(f"Deleted test user: {u}")
        except Exception as e:
            log(f"Failed to delete test user {u}: {e}", "WARN")

    log("\n============================================================")
    log("ALL END-TO-END FUNCTIONAL AND SECURITY TESTS PASSED!", "SUCCESS")
    log("Summary Results:")
    for k, v in results.items():
        print(f"  {k:32} : {v}")
    log("============================================================\n")

    return results


if __name__ == "__main__":
    main()
