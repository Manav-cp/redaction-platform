# Cloud Security Concerns and Mitigations

| Threat | Mitigation in this project | Where |
|---|---|---|
| **Unauthorized access to files** | All 3 buckets have *Block Public Access* + *BucketOwnerEnforced*. Uploads/downloads only via pre-signed URLs valid **5 minutes**, bound to a single object key. Frontend bucket readable **only** by our CloudFront distribution (OAC + `AWS:SourceArn` condition). | `template.yaml` buckets & policies, `api/handler.py` |
| **Broken authentication / IDOR** | Cognito user pool with strong password policy, email verification, optional TOTP MFA. API Gateway JWT authorizer rejects requests without a valid token *before* Lambda runs. User ID is taken only from the verified token `sub`, and every DynamoDB key includes it, so user A can never read user B's documents (covered by unit test `test_upload_then_get_and_delete`). | `UserPool`, `HttpApi.Auth`, `api/handler.py` |
| **Privilege escalation** | Each function has exactly the permissions in `iam-policies/*.json` (prefix-scoped S3, single table). *Learner Lab note:* role creation is blocked, so the stack uses `LabRole`; the least-privilege policies are provided for production. | `iam-policies/` |
| **Data at rest** | S3 SSE (AES-256) default encryption on all buckets, DynamoDB encryption at rest (SSE enabled). Can switch to SSE-KMS with a customer-managed key in a normal account. | `BucketEncryption`, `SSESpecification` |
| **Data in transit** | CloudFront `redirect-to-https`, TLS 1.2+/1.3 on all AWS endpoints, bucket policies **deny any non-TLS request** (`aws:SecureTransport=false`). | bucket policies, `Distribution` |
| **Data minimisation / retention** | Raw uploads (containing PII) auto-expire after **1 day**; redacted outputs after 30 days; user can delete immediately. | `LifecycleConfiguration`, `DELETE /documents/{id}` |
| **Malicious / oversized uploads** | Extension allow-list (.pdf/.txt), file names sanitised, size enforced **by S3 itself** via `content-length-range` in the pre-signed POST policy, content type locked. | `api/handler.py` |
| **Denial of service / abuse** | API Gateway throttling (10 req/s, burst 20). Optional AWS WAF on CloudFront: 100 requests / 5 min per IP + AWS Managed Common Rule Set (SQLi, XSS, bad bots). | `DefaultRouteSettings`, `WebAcl` |
| **Browser attacks (XSS, clickjacking)** | CloudFront managed *SecurityHeadersPolicy* adds HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy. React escapes output by default. CORS restricted to the CloudFront origin (+ localhost for dev). | `Distribution`, `CorsConfiguration` |
| **Supply chain** | CI runs `pip-audit` and `npm audit`; dependencies pinned. | `.github/workflows/deploy.yml` |
| **Detection & response** | CloudWatch alarms on processor errors, throttles, duration, API 5xx and latency; structured JSON logs (no document text is logged). | `template.yaml` monitoring section |
