# RedactIQ – Production Deployment Guide

## 1. Prerequisites
- Development Machine: Windows 11 / macOS / Linux with Python 3.11+, Node.js 20 LTS, Git, and AWS CLI v2.
- AWS Account: Active AWS Academy Learner Lab session in region `us-east-1`.
- AWS Credentials: Loaded in `~/.aws/credentials` (`[default]` profile with `aws_session_token`).

---

## 2. Architecture Overview
RedactIQ separates continuous integration and continuous deployment:
1. **Continuous Integration**: Runs on GitHub-hosted `ubuntu-latest` runners. Validates code, executes 28 automated tests, checks templates, runs dependency audits, and uploads verified build artifacts.
2. **Continuous Deployment**: Triggered manually from `main` branch. Executes via local deployment engine or GitHub self-hosted runner, avoiding any requirement to store temporary AWS credentials in GitHub Secrets.

---

## 3. Step-by-Step Deployment Instructions

### Step 1: Pre-Flight Environment Verification
Before deploying, execute the read-only verification probe:
```powershell
python scripts/cd_deploy.py --verify-only
```
This verifies your active AWS session, account ID (`058264205875`), CloudFormation stack (`doc-redaction`), S3 website, and API Gateway connectivity.

### Step 2: Deploy Frontend Application
Deploy the tested React frontend single-page application to Amazon S3:
```powershell
python scripts/cd_deploy.py --component frontend
```
* Builds production React assets using Vite.
* Injects active API Gateway and Cognito configuration into `dist/config.json`.
* Uploads hashed static assets (`assets/*`) first with immutable 1-year cache headers.
* Uploads `index.html` last with `no-cache` header.
* **Strictly avoids `--delete` flag** to preserve rollback assets.

### Step 3: Deploy Backend Application Code
Deploy Lambda function code packages to AWS Lambda:
```powershell
python scripts/cd_deploy.py --component backend
```
* Compiles Linux `manylinux2014_x86_64` wheels for Python 3.12 runtime.
* Packages `api.zip` and `processor.zip`.
* Updates `doc-redaction-ApiFunction-...` and `doc-redaction-ProcessorFunction-...` via `aws lambda update-function-code`.
* Waits for AWS Lambda function update waiters (`function_updated`).
* Automatically runs post-deployment smoke tests.

### Step 4: Full Deployment
To deploy both frontend and backend in one sequence:
```powershell
python scripts/cd_deploy.py --component all
```

---

## 4. Triggering Deployment via GitHub Actions
If demonstrating through the GitHub Actions dashboard:
1. Start the runner in `C:\actions-runner`:
   ```powershell
   cd C:\actions-runner
   .\run.cmd
   ```
2. Navigate to your GitHub repository: **Actions > Continuous Deployment > Run workflow**.
3. Select `component: frontend` (or `all`) and enter `DEPLOY` in the confirmation box.
4. Click **Run workflow**.
