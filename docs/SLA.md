# Service Level Agreement – RedactIQ Cloud-Based Document Redaction Platform

## 1. Service Overview & Scope

This Service Level Agreement (SLA) defines the operational service commitments, performance targets, and support parameters for the RedactIQ Serverless Document Processing and Sensitive Data Redaction Platform. RedactIQ provides automated detection and masking of sensitive Personally Identifiable Information (PII) from PDF and TXT documents. This agreement specifies measurable Service Level Indicators (SLIs), Service Level Objectives (SLOs), incident classifications, monitoring parameters, and disaster recovery procedures.

Scope of Services Covered:
• User authentication, session management, and JWT issuance via Amazon Cognito.
• RESTful API endpoint routing and presigned URL generation via Amazon API Gateway.
• Event-driven document text extraction, PII detection, and redaction via AWS Lambda.
• Document metadata storage and lifecycle query handling via Amazon DynamoDB.
• Static web portal availability via Amazon S3 Website Hosting.

## 2. Service Level Indicators (SLIs) & Service Level Objectives (SLOs)

The following table defines the proposed SLOs alongside actual measured results obtained during live cloud verification in AWS account 058264205875:

| Service Metric / Indicator | Proposed SLO Target | Measurement Method | Actual Measured Result | Compliance Status |
| --- | --- | --- | --- | --- |
| Application Web Availability | 99.9% Uptime | Automated HTTP 200 health probe | 100% (HTTP 200) | COMPLIANT |
| API Gateway Availability | 99.9% Uptime | CloudWatch 5XX error rate probe | 100% (0 errors) | COMPLIANT |
| API Response Time (Upload URL) | < 2000 ms | API Gateway IntegrationLatency | 1017.4 ms | COMPLIANT |
| Document Processing Time (TXT) | < 5.0 seconds | DynamoDB timestamp delta | 2.45 seconds | COMPLIANT |
| Document Processing Time (PDF) | < 6.0 seconds | DynamoDB timestamp delta | 2.60 seconds | COMPLIANT |
| Document Processing Success Rate | > 99.0% | Status = COMPLETED / Invocations | 100% success | COMPLIANT |
| API Error Rate | < 0.1% | CloudWatch 5XX count / Total calls | 0.00% | COMPLIANT |
| Lambda Error Rate | < 0.1% | CloudWatch Lambda Errors metric | 0.00% | COMPLIANT |
| Authentication Availability | 99.9% Uptime | Cognito InitiateAuth success probe | 100% (3004ms) | COMPLIANT |
| Cross-Tenant Isolation | 100% (Zero Leakage) | Unauthorized access test (HTTP 404) | 100% isolated | COMPLIANT |
| Deployment Success Rate | > 95.0% | Automated CI/CD smoke test check | 100% (2/2 deploys) | COMPLIANT |
| Recovery Time Objective (RTO) | < 5.0 minutes | Automated rollback script execution | 30.0 seconds | COMPLIANT |
| Recovery Point Objective (RPO) | < 1.0 minute | DynamoDB PITR / Snapshot frequency | Verified snapshots | COMPLIANT |

## 3. Availability Calculation & Downtime Exclusions

Availability is calculated on a monthly evaluation period using the standard industry formula:
Availability (%) = ((Total Scheduled Minutes - Unplanned Downtime Minutes) / Total Scheduled Minutes) * 100

Downtime Exclusions:
The following events are excluded from downtime calculations:
1. Scheduled Maintenance: Communicated at least 24 hours in advance.
2. AWS Academy Learner Lab Session Expiration: Automatic termination after 4-hour lab duration.
3. Upstream AWS Outages: Disruptions in core AWS infrastructure affecting us-east-1.
4. Client-Side Errors: Network disruptions, invalid document payloads, or expired JWT tokens.

## 4. Incident Management & Severity Levels

Incidents are categorized by operational impact:

| Severity Level | Definition & Impact | Target Response | Target Resolution | Escalation Action |
| --- | --- | --- | --- | --- |
| P1 - Critical | Complete outage of API Gateway, Cognito, or S3 Web portal. | < 15 minutes | < 2 hours | Automatic rollback & DevOps lead alert |
| P2 - High | Document processing failure affecting > 25% of jobs. | < 30 minutes | < 4 hours | Lambda log analysis & queue inspection |
| P3 - Medium | Degraded performance (processing latency > 8.0 seconds). | < 2 hours | < 8 hours | Concurrency review & memory scaling |
| P4 - Low | Minor cosmetic portal defects or non-blocking log warnings. | < 8 hours | < 24 hours | Scheduled sprint release update |

## 5. Security, Privacy & Data Retention Commitments

• Data Minimization: Raw uploaded documents are stored in s3://doc-redaction-rawbucket/... and automatically deleted after 1 day via S3 Lifecycle rule ExpireRawUploads.
• Output Retention: Redacted clean documents in s3://doc-redaction-cleanbucket/... are retained for 30 days and then purged.
• Encryption: All data at rest is encrypted using AES-256 Server-Side Encryption (SSE-S3). All API and web communications enforce TLS 1.2+.
• Tenant Isolation: Documents are strictly partitioned by Cognito user ID at both storage and API layers.

## 6. Disaster Recovery & Rollback Strategy

• Rollback Automation: Every deployment generates a pre-flight snapshot in .build/rollback_backups/<timestamp>/. In the event of a deployment fault, running python scripts/rollback.py restores working Lambda code and frontend assets within 30 seconds.
• Zero Delete Policy: Deployments never pass --delete to S3, ensuring rollback assets remain cached and available for active sessions.

## 7. SLA Limitations & Educational Disclaimer

This Service Level Agreement represents an academic, application-level operational benchmark designed for an M.Tech project operating within the AWS Academy Learner Lab sandbox environment. It does not constitute a legally binding commercial contract. All cloud services are subject to the AWS Academy Learner Lab terms of service and sandbox permission boundaries.

