# Costing & Budgeting (monthly estimate, us-east-1)

Assumed workload: **50 users, 2,000 documents / month**, average 5 pages (~15,000 characters, 300 KB).

| Service | Usage | Free tier | Est. cost |
|---|---|---|---|
| AWS Lambda | ~2,000 processor runs × 1 s × 1 GB + ~40,000 API calls × 100 ms × 256 MB ≈ 3,000 GB-s, 42k requests | 1M requests + 400,000 GB-s / month (always free) | **$0.00** |
| Amazon S3 | < 1 GB stored (raw expires daily), ~10k PUT/GET | 5 GB + 20k GET + 2k PUT (12 months) | **$0.00** |
| DynamoDB | 5 RCU / 5 WCU provisioned, < 10 MB | 25 RCU/WCU + 25 GB (always free) | **$0.00** |
| DynamoDB PITR | < 10 MB | — | ~$0.01 |
| API Gateway HTTP API | ~40,000 requests | 1M requests (12 months) | **$0.00** (after: $0.04) |
| Cognito | 50 MAU | 10,000 MAU (Lite tier) | **$0.00** |
| CloudFront | < 5 GB transfer, < 100k requests | 1 TB + 10M requests (always free) | **$0.00** |
| CloudWatch | 5 alarms, 1 dashboard, < 1 GB logs | 10 alarms, 3 dashboards, 5 GB logs | **$0.00** |
| **Subtotal (core)** | | | **≈ $0.01** |
| Amazon Comprehend PII (optional AI layer) | 2,000 docs × 150 units (100 chars each) = 300k units × $0.0001 | 50k units / month (12 months) | ~$25 → **~$30 without free tier** |
| AWS WAF (optional) | 1 web ACL + 2 rules + requests | none | ~$7 / month (prorated hourly – a 3-hour demo costs ≈ $0.03) |

## Cost optimisation decisions
* **Direct-to-S3 uploads** with pre-signed POST: Lambda never streams file bytes (saves duration and API payload limits).
* **Lifecycle rules** delete raw PII files after 1 day and outputs after 30 days → storage never grows.
* **Provisioned DynamoDB 5/5** stays inside the always-free 25/25 instead of on-demand.
* **HTTP API** instead of REST API (≈ 70 % cheaper per request).
* **Comprehend is a switch** (`--use-comprehend false`) → regex-only mode costs $0.
* CloudWatch log retention set to 14 days.
* Tags/stack name allow per-project cost tracking in Cost Explorer.

## AWS Academy Learner Lab budget
Learner Lab accounts don't receive the normal Free Tier; usage is deducted from the lab credit (typically $50–$100). Running this project for testing and the demo normally uses **well under $2**. Run `python scripts/destroy.py` when finished.

*Figures are approximate list prices; free-tier terms differ for accounts created after July 2025 (credit-based free plan). Re-check each line in the AWS Pricing Calculator (https://calculator.aws) before submission and attach the calculator export to your report.*
