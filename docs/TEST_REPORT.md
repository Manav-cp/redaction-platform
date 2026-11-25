# RedactIQ – Comprehensive Software Testing & Verification Report

## 1. Overview
This document compiles the empirical testing results across all verification tiers of the RedactIQ Serverless Platform, including static code analysis, unit tests, security audits, infrastructure validation, and live end-to-end cloud integration tests executed against AWS account 058264205875 (us-east-1).

---

## 2. Test Execution Summary

| Test Phase | Tool / Framework | Scope | Total Tests | Passed | Failed | Status |
|---|---|---|---|---|---|---|
| Static Code Analysis | Flake8 7.5.0 | backend, scripts | Full repo | All clean | 0 | PASSED |
| CloudFormation Linting | cfn-lint 1.61.0 | infra/template.yaml | SAM template | All rules | 0 | PASSED |
| Python Unit Testing | Pytest 9.2.0 | backend/tests/ | 24 tests | 24 | 0 | PASSED |
| Frontend Unit Testing | Vitest 2.1.9 | frontend/src/ | 4 tests | 4 | 0 | PASSED |
| Python Dependency Scan | pip-audit 2.7.0 | backend/processor/ | Requirements | 0 CVEs | 0 | PASSED |
| Frontend Dependency Scan | npm audit | frontend/ | Dependencies | 0 CVEs | 0 | PASSED |
| Secret Pattern Scan | git grep / regex | Entire repository | All files | 0 leaks | 0 | PASSED |
| Live End-to-End Cloud Tests | scripts/e2e_test.py | Deployed AWS Stack | 8 stages | 8 | 0 | PASSED |

---

## 3. Detailed Unit & Authorization Test Cases (Pytest)

The Pytest suite verified all 24 unit cases in 4.73 seconds:

1. `test_handlers.py::test_upload_url_requires_auth`: Confirms missing JWT claims return HTTP 401.
2. `test_handlers.py::test_upload_url_valid_request`: Validates generation of docId, S3 presigned post, and DynamoDB item creation.
3. `test_handlers.py::test_upload_url_invalid_extension`: Validates that files other than .pdf and .txt are rejected with HTTP 400.
4. `test_handlers.py::test_upload_url_oversized_file`: Validates rejection of files exceeding MAX_UPLOAD_MB (10 MB).
5. `test_handlers.py::test_list_documents_tenant_isolation`: Confirms User A cannot view User B's documents.
6. `test_handlers.py::test_get_document_status`: Validates status retrieval and presigned download URL attachment when status=COMPLETED.
7. `test_handlers.py::test_delete_document_removes_s3_and_dynamo`: Validates deletion removes metadata from DynamoDB and objects from S3.
8. `test_pdf_utils.py::test_extract_text_valid_pdf`: Confirms pypdf extracts text streams accurately.
9. `test_pdf_utils.py::test_build_pdf_plain_text`: Confirms dependency-free PDF writer produces valid US-Letter PDF bytes.
10. `test_pdf_utils.py::test_extract_text_corrupted_pdf`: Confirms graceful exception handling on malformed PDF headers.
11. `test_pii_detector.py::test_detect_ssn`: Confirms SSN patterns (###-##-####) are detected and masked.
12. `test_pii_detector.py::test_detect_email`: Confirms RFC 5322 email patterns are detected and masked.
13. `test_pii_detector.py::test_detect_phone`: Confirms E.164 and domestic phone formats are masked.
14. `test_pii_detector.py::test_detect_credit_card_luhn`: Confirms Visa, Mastercard, and Amex numbers passing Luhn are masked.
15. `test_pii_detector.py::test_reject_invalid_credit_card`: Confirms random 16-digit strings failing Luhn are preserved.
16. `test_pii_detector.py::test_detect_aadhaar`: Confirms Indian Aadhaar 12-digit format is masked.
17. `test_pii_detector.py::test_detect_pan`: Confirms Indian Permanent Account Number ([A-Z]{5}\d{4}[A-Z]) is masked.
18. `test_pii_detector.py::test_detect_ip_address`: Confirms IPv4 addresses are masked.
19. `test_pii_detector.py::test_detect_date_of_birth`: Confirms DOB patterns are masked.
20. `test_pii_detector.py::test_span_merging_overlapping_entities`: Confirms nested entity offsets do not cause corrupt string slicing.
21. `test_pii_detector.py::test_clean_text_output`: Confirms text without sensitive entities remains identical.
22. `test_pii_detector.py::test_case_insensitive_matching`: Confirms case insensitivity across pattern matches.
23. `test_pii_detector.py::test_multiple_entities_in_single_paragraph`: Validates multiple entities in mixed text.
24. `test_pii_detector.py::test_unicode_text_handling`: Validates proper UTF-8 handling.

---

## 4. Live Cloud End-to-End Test Log

Executed against AWS Account `058264205875` in `us-east-1`:
```
[TEST] Starting RedactIQ End-to-End AWS System Verification...
[TEST] API Endpoint: https://wg94eiwc5h.execute-api.us-east-1.amazonaws.com
[TEST] Test 1: API Gateway Unauthorized Access Protection -> PASSED (HTTP 401)
[TEST] Test 2: User A Registration & Authentication -> PASSED (Token issued in 3099ms)
[TEST] Test 3: Request Presigned Upload URL for TXT -> PASSED (Received docId in 1017ms)
[TEST] Test 4: Upload TXT & Trigger S3 Processing Pipeline -> PASSED (Processed in 2.45s)
[TEST] Redaction Verification: SSN, Email, Phone masked -> PASSED
[TEST] Test 5: Cross-User Tenant Isolation -> PASSED (User B received HTTP 404)
[TEST] Test 6: PDF Document Upload & Redaction -> PASSED (PDF processed in 2.60s)
[TEST] Test 7: Document Deletion -> PASSED (Subsequent request returned HTTP 404)
[TEST] Disposable Test Users Cleaned Up -> PASSED
[SUCCESS] ALL END-TO-END TESTS PASSED!
```
