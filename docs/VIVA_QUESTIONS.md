# RedactIQ – Academic Viva & Technical Defense Preparation

## Q1: Why did you choose an event-driven S3 architecture instead of uploading files through API Gateway?
**Answer**: API Gateway has a strict payload size limit of 10 MB (and 6 MB on Lambda synchronous payloads) and charges for API data transfer. Uploading large PDF files through API Gateway ties up Lambda compute while the bytes are transmitted. By using presigned S3 URLs, the client uploads directly to S3 storage. Once the upload finishes, S3 triggers the Processor Lambda asynchronously. This achieves zero compute cost during file transfer, eliminates API payload bottlenecks, and separates ingestion from processing.

## Q2: How does RedactIQ prevent cross-tenant document tampering?
**Answer**: RedactIQ implements Defense-in-Depth:
1. API Perimeter: API Gateway validates the Cognito JWT token.
2. In-Code Authorization: The Lambda handler extracts the caller's identity strictly from `event['requestContext']['authorizer']['jwt']['claims']['sub']`. It never trusts user IDs passed in query parameters or request bodies.
3. Database Tier: DynamoDB uses a composite primary key with `userId` as the Partition Key (PK) and `docId` as the Sort Key (SK). Queries are strictly scoped to `PK = :userId`. If User B attempts to access User A's `docId`, DynamoDB returns null, and the API returns HTTP 404.

## Q3: How do you detect credit cards without generating false positives on random 16-digit numbers?
**Answer**: We combine regular expressions with algorithmic verification. First, regex identifies candidate numeric sequences matching 13 to 19 digits with optional hyphens or spaces. Next, candidate numbers are passed to a Python implementation of the **Luhn Algorithm (mod-10 checksum)**. Only sequences that satisfy the checksum are classified as credit cards and masked.

## Q4: Why didn't you use GitHub Actions AWS OIDC or store credentials in GitHub Secrets?
**Answer**: In AWS Academy Learner Lab:
1. `iam:CreateOpenIDConnectProvider` is explicitly denied by Vocareum security boundaries. Therefore, GitHub OIDC trust cannot be established.
2. Storing credentials in GitHub Secrets is insecure and impractical because Learner Lab session tokens expire every 4 hours.
We resolved this by using a self-hosted runner and deployment engine on the local workstation where AWS CLI credentials already reside. This satisfies all Learner Lab boundaries while keeping zero secrets in GitHub.

## Q5: How does your rollback mechanism work?
**Answer**: Before altering any live resource, `scripts/cd_deploy.py` queries AWS Lambda (`get_function`) to download the active Lambda zip codes and downloads `index.html` and `config.json` from S3 into `.build/rollback_backups/<timestamp>/`. If deployment fails, `scripts/rollback.py` re-uploads the backed-up zips to Lambda and restores S3 files in under 30 seconds.

## Q6: Why is CloudFront disabled in your architecture?
**Answer**: CloudFront creation is restricted by AWS Academy Learner Lab IAM policies. To maintain compliance without violating sandbox restrictions, the frontend is hosted directly via S3 Static Website Hosting with appropriate CORS configurations.
