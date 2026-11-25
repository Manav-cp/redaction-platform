# RedactIQ – Step-by-Step Live Demonstration Guide

Follow this sequence to deliver a flawless live demonstration to evaluators:

## 1. Demonstrate the Live Web Application
1. Open Chrome/Edge and navigate to the live website:
   `http://redactiq-frontend-058264205875.s3-website-us-east-1.amazonaws.com`
2. Show that the portal loads cleanly over HTTP without errors.
3. Register a new user account with a temporary email (or log in with an existing test user).
4. Demonstrate the drag-and-drop uploader by uploading a sample document (`samples/sample-resume.txt` or `sample-invoice.pdf`).
5. Observe the live status change in the document table:
   `PENDING_UPLOAD` -> `PROCESSING` -> `COMPLETED`.
6. Click **Download Redacted Document**. Open the downloaded file to show evaluators that SSN, email, phone, and credit card numbers are masked with `[REDACTED-SSN]`, `[REDACTED-EMAIL]`, etc.
7. Click **Delete Document** to demonstrate data minimization and DynamoDB cleanup.

---

## 2. Demonstrate the AWS Cloud Infrastructure
1. Open AWS Management Console in `us-east-1`:
   - **CloudFormation**: Show stack `doc-redaction` in `UPDATE_COMPLETE` state.
   - **Lambda**: Show `doc-redaction-ApiFunction-...` and `doc-redaction-ProcessorFunction-...` with Python 3.12 runtime.
   - **DynamoDB**: Show table `doc-redaction-DocumentsTable-...` with on-demand capacity and items partitioned by `userId`.
   - **S3**: Show `rawbucket` (lifecycle rule ExpireRawUploads=1 day) and `cleanbucket` (versioning enabled).
   - **Cognito**: Show User Pool `us-east-1_egGeffF99` and verified user accounts.

---

## 3. Demonstrate the CI/CD Pipeline
1. Open GitHub repository in browser:
   `https://github.com/Manav-cp/redactiq/actions`
2. Show the **Continuous Integration** workflow:
   - Point out the 6 concurrent verification stages: Flake8, Pytest (24 tests), cfn-lint, pip-audit, Vitest, npm audit.
   - Show the generated and uploaded build artifacts (`backend-artifacts` and `frontend-artifacts`).
3. Show the **Continuous Deployment** workflow (`cd.yml`):
   - Explain the manual safety guard requiring `confirm_deployment: DEPLOY`.
   - Explain how deployment executes on the self-hosted runner without storing AWS credentials in GitHub Secrets.

---

## 4. Demonstrate Automated Rollback Readiness
In the terminal, run:
```powershell
python scripts/cd_deploy.py --verify-only
```
Show evaluators that all pre-flight health checks pass in real-time. Show the backup snapshot directory in `.build/rollback_backups/` and explain that running `python scripts/rollback.py` restores the previous working state in under 30 seconds.
