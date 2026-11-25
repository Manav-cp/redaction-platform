# RedactIQ – CI/CD Pipeline Architecture & Operations Guide

## 1. Overview & Architecture

RedactIQ implements a modern, secure, two-stage Continuous Integration and Continuous Deployment (CI/CD) pipeline specifically designed for AWS Serverless architectures operating within AWS Academy Learner Lab constraints.

### Pipeline Flow Diagram

```mermaid
flowchart TD
    subgraph Developer["Local Development"]
        Code[Source Code: Python / React / SAM] --> Commit[Git Commit]
        Commit --> Push[Git Push to GitHub]
    end

    subgraph CI["GitHub Actions Continuous Integration (GitHub-Hosted Runners)"]
        Push --> TrigCI[ci.yml Trigger: Push / PR]
        
        subgraph BackendJob["Backend CI (Python 3.12)"]
            Flake8[Flake8 Code Linting]
            Pytest[Pytest Unit & Auth Tests (24 Tests)]
            CFNLint[CloudFormation Linter]
            PipAudit[pip-audit Vulnerability Scan]
            SecretScan[Secret Pattern Detection]
        end
        
        subgraph FrontendJob["Frontend CI (Node.js 20)"]
            NPMTest[Vitest Unit Tests]
            NPMBuild[Vite Production Build]
            NPMAudit[npm audit Security Scan]
        end
        
        subgraph PackageJob["Artifact Packaging"]
            PkgLambda[Build Linux-compatible Lambda Packages]
            PkgFrontend[Package React Distribution]
            UploadArtifacts[Upload Verified Artifacts to GitHub]
        end
        
        TrigCI --> BackendJob
        TrigCI --> FrontendJob
        BackendJob --> PackageJob
        FrontendJob --> PackageJob
    end

    subgraph CD["Continuous Deployment (Manual Dispatch / Approval Gate)"]
        UploadArtifacts -.-> TrigCD[cd.yml Trigger: workflow_dispatch]
        TrigCD --> Gate[Manual Safety Approval: DEPLOY]
        
        subgraph Runner["Deployment Execution (Local Runner / Engine)"]
            StageA[Stage A: Pre-Deployment & Rollback Backup]
            StageB[Stage B: Frontend S3 Deployment (No --delete)]
            StageC[Stage C: Backend Lambda Code Update]
            StageD[Stage D: Post-Deployment Smoke Tests]
            Rollback[Stage E: Automated Rollback Mechanism]
        end
        
        Gate --> StageA
        StageA --> StageC
        StageC --> StageB
        StageB --> StageD
        StageD -. Failure .-> Rollback
    end

    subgraph AWS["AWS Cloud Infrastructure (us-east-1)"]
        StageB --> S3Front[Amazon S3 Frontend Website]
        StageC --> Lambdas[AWS Lambda: Api & Processor]
        StageD --> CheckAPI[Amazon API Gateway HTTP API]
        StageD --> CheckDDB[Amazon DynamoDB Table]
        StageD --> CheckCognito[Amazon Cognito User Pool]
    end
```

---

## 2. CI Pipeline Specifications (`.github/workflows/ci.yml`)

The CI pipeline runs automatically on every `push` and `pull_request` targeting the `main` branch, as well as on manual `workflow_dispatch`.

- **Runner**: `ubuntu-latest` (GitHub-hosted runner).
- **Backend Quality Gates**:
  1. **Python Runtime Parity**: Uses Python 3.12 to match the deployed AWS Lambda execution environment.
  2. **Code Linting**: Flake8 ensures adherence to PEP 8 style standards across `backend` and `scripts`.
  3. **Unit & Authorization Tests**: Pytest runs 24 automated tests verifying PDF text extraction, redaction algorithms, regex pattern matching, cross-user tenancy isolation, and API route handling.
  4. **Infrastructure Validation**: `cfn-lint` validates `infra/template.yaml` for syntax, parameters, and CloudFormation specifications.
  5. **Dependency Vulnerability Audits**: `pip-audit` queries PyPI advisory databases for known CVEs.
  6. **Secret Scanning**: Custom git pattern scanning detects accidental commits of AWS keys, GitHub tokens, or private keys.
- **Frontend Quality Gates**:
  1. **Node Environment**: Node.js 20 with cached `npm` dependencies.
  2. **Automated Testing**: Vitest validates frontend utility functions and token decoders.
  3. **Production Build**: Vite builds optimized static bundles.
  4. **Security Audit**: `npm audit --omit=dev --audit-level=high` verifies zero high/critical vulnerabilities.
- **Artifact Packaging**:
  - Compiles Linux x86_64 compatible packages (`api.zip` and `processor.zip`) with clean dependencies.
  - Generates frontend static distribution.
  - Uploads verified artifacts to GitHub Actions storage with a 14-day retention window.

---

## 3. CD Pipeline Specifications (`.github/workflows/cd.yml`)

The CD workflow provides controlled, zero-downtime, non-destructive deployment.

- **Trigger**: Manual dispatch (`workflow_dispatch`) only.
- **Safety Gate**: Requires typing `DEPLOY` in the `confirm_deployment` input.
- **Target Branch**: Strictly restricted to `main`.
- **Target Component**: Selectable between `all`, `frontend`, or `backend`.

### Deployment Stages:

1. **Stage A – Pre-Deployment Verification**:
   - Asserts active AWS STS caller identity matching Account ID `058264205875` and region `us-east-1`.
   - Validates CloudFormation stack `doc-redaction` is in `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
   - Dynamically discovers physical Lambda IDs (`doc-redaction-ApiFunction-...` and `doc-redaction-ProcessorFunction-...`).
   - Downloads live Lambda zip codes and S3 `index.html`/`config.json` into a timestamped rollback snapshot `.build/rollback_backups/<timestamp>/`.
2. **Stage B – Frontend Deployment**:
   - Uploads new static hashed assets (`assets/*`) first with immutable 1-year cache headers.
   - Uploads root config and metadata.
   - Uploads `index.html` last with `no-cache` header.
   - **Strictly avoids `aws s3 sync --delete`** to prevent data loss and preserve rollback assets.
3. **Stage C – Backend Deployment**:
   - Updates Lambda function code directly using `aws lambda update-function-code`.
   - Uses AWS Lambda waiters (`function_updated`) to ensure clean state transitions.
   - Zero modifications to CloudFormation, IAM roles, DynamoDB tables, or Cognito settings.
4. **Stage D – Post-Deployment Verification**:
   - HTTP 200 checks on website index and assets.
   - Dynamic validation of `config.json` parameters.
   - Verification that unauthenticated API Gateway requests receive HTTP 401 Unauthorized.
   - Health checks verifying Lambda functions, DynamoDB tables, and Cognito user pools.

---

## 4. AWS Authentication in Learner Lab

### Why GitHub Secrets / AWS OIDC Are Not Used:
- **AWS Academy Learner Lab Constraints**:
  - Learner Lab provides temporary session tokens that expire after ~4 hours.
  - IAM permissions are restricted to the pre-created `LabRole`. Students cannot create or modify IAM Identity Providers (`iam:CreateOpenIDConnectProvider`), making GitHub Actions AWS OIDC technically impossible.
  - Pasting session tokens repeatedly into GitHub repository secrets exposes security risks and introduces constant manual toil.

### Recommended Approaches:

#### Option A: Local Deployment Engine (Fastest & Most Reliable)
Because your workstation already possesses the active AWS CLI credentials in `~/.aws/credentials`, you can execute the deployment engine locally:
```powershell
python scripts/cd_deploy.py --component all
```
This runs the exact same pre-flight verification, rollback backup, deployment, and post-flight smoke tests without storing any credentials in GitHub.

#### Option B: GitHub Self-Hosted Runner (For GitHub Actions CD)
If you wish to trigger deployment directly from the GitHub Actions UI:
1. Navigate to: `https://github.com/Manav-cp/redactiq/settings/actions/runners/new`
2. Obtain a fresh registration token.
3. In `C:\actions-runner`, run:
   ```cmd
   .\config.cmd --url https://github.com/Manav-cp/redactiq --token <FRESH_TOKEN>
   .\run.cmd
   ```
4. Test Runner Connectivity: In GitHub Actions, navigate to **Actions > Test Self-Hosted Runner Connectivity > Run workflow** to run a harmless, read-only verification.
5. Run the **Continuous Deployment** workflow in GitHub Actions with `component: frontend` and `confirm_deployment: DEPLOY`.
6. Once deployment completes, stop the runner (`Ctrl+C`). Never leave the runner running unattended.

---

## 5. Rollback Procedure

If any issue occurs during or after deployment, RedactIQ provides a one-command automated rollback engine:

```powershell
python scripts/rollback.py
```

### What Rollback Does:
1. Identifies the latest snapshot from `.build/rollback_backups/`.
2. Re-uploads the previous Lambda function packages to AWS Lambda.
3. Re-uploads the previous `index.html` and `config.json` to Amazon S3.
4. Executes the full post-deployment verification suite to confirm complete recovery.

---

## 6. Learner Lab Limitations & Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| `ExpiredToken` / `InvalidClientTokenId` | Learner Lab 4-hour session expired | Restart Learner Lab from AWS Academy, click **AWS Details > AWS CLI**, copy new credentials into `~/.aws/credentials`. |
| `AccessDenied` on CloudFront | Learner Lab forbids CloudFront | Frontend is hosted directly via S3 Static Website Hosting. |
| `AccessDenied` on IAM Role Creation | Learner Lab forbids IAM role creation | CloudFormation and Lambda are configured to use the pre-created `LabRole`. |
| Runner Offline in GitHub Actions | Self-hosted runner process not active | Start `C:\actions-runner\run.cmd` or deploy locally using `python scripts/cd_deploy.py`. |
