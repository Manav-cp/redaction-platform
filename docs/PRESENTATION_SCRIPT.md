# RedactIQ – M.Tech Project Presentation Script

## Slide 1: Title & Introduction (1 Minute)
"Good morning, esteemed committee members. Today, I am proud to present **RedactIQ**, an enterprise-grade Serverless Document Processing and Sensitive Data Redaction Platform built on Amazon Web Services with a complete, secure GitHub CI/CD pipeline."

## Slide 2: Motivation & Problem Statement (1 Minute)
"With regulations like GDPR, HIPAA, and the Digital Personal Data Protection Act, organizations cannot legally store or distribute unredacted documents containing PII. Existing systems require expensive, 24/7 dedicated servers that fail to scale during burst loads. RedactIQ solves this with a 100% serverless, event-driven architecture that scales to zero when idle."

## Slide 3: Architecture & AWS Services (2 Minutes)
"Our architecture is completely decoupled:
1. Frontend: React 18 SPA hosted on Amazon S3.
2. Identity: Amazon Cognito User Pools issuing standard JWT tokens.
3. Routing: Amazon API Gateway HTTP API enforcing JWT authorizer verification at the perimeter.
4. Ingestion: Direct-to-S3 ingestion using short-lived presigned URLs, bypassing API compute.
5. Processing: AWS Lambda triggered by S3 ObjectCreated events, extracting text with pypdf and executing regex and Luhn algorithm checks.
6. Database: Amazon DynamoDB tracking document lifecycles with single-digit millisecond latency."

## Slide 4: CI/CD Pipeline & Educational Sandbox Innovations (2 Minutes)
"Deploying into an AWS Academy Learner Lab presented unique engineering hurdles: Learner Lab restricts IAM role creation, forbids CloudFront, and issues temporary 4-hour credentials. 
Instead of storing fragile session tokens in GitHub Secrets, we engineered a modular two-tier pipeline:
- CI runs automatically on GitHub-hosted runners, executing Flake8, 24 Pytest tests, cfn-lint, pip-audit, and Vitest.
- CD operates through a dedicated local deployment engine and self-hosted runner, leveraging the developer's active AWS CLI session with zero credentials in GitHub.
- Every deployment creates automated rollback snapshots and uses an assets-first S3 upload strategy without the destructive --delete flag."

## Slide 5: Live Verification & Results (1.5 Minutes)
"In live testing against AWS account 058264205875:
- Document redaction executed in 2.45 seconds.
- Tenant isolation verified with HTTP 404 on cross-user queries.
- Rollback restored live functions in under 30 seconds.
- Total operational cost: $0.00."

## Slide 6: Conclusion (30 Seconds)
"RedactIQ demonstrates that enterprise-grade security, rapid processing, and automated DevOps can be achieved completely within serverless cloud primitives. Thank you. I am now open to your questions."
