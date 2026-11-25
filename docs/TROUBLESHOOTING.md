# RedactIQ – Troubleshooting & Operational Incident Guide

## 1. Common Operational Issues

### Issue 1: `ExpiredToken` or `InvalidClientTokenId`
- **Cause**: AWS Academy Learner Lab credentials expire after 4 hours.
- **Remediation**:
  1. Open AWS Academy > Learner Lab.
  2. Click **Start Lab** (wait for green dot).
  3. Click **AWS Details > AWS CLI: Show**.
  4. Copy credentials block into `C:\Users\manav\.aws\credentials`.
  5. Verify: `aws sts get-caller-identity`.

### Issue 2: `AccessDeniedException` on IAM Role Creation
- **Cause**: AWS Academy Learner Lab forbids `iam:CreateRole` and `iam:CreateOpenIDConnectProvider`.
- **Remediation**:
  - Do not attempt to create IAM roles.
  - RedactIQ is pre-configured to utilize the pre-created `LabRole` (`arn:aws:iam::058264205875:role/LabRole`).

### Issue 3: GitHub Self-Hosted Runner Shows Offline
- **Cause**: The interactive runner process `run.cmd` is not active.
- **Remediation**:
  1. Open PowerShell on laptop.
  2. Run: `cd C:\actions-runner; .\run.cmd`.
  3. Check console for `Listening for Jobs`.

### Issue 4: S3 Website Shows Blank Screen
- **Cause**: Missing or malformed `config.json` in root of website bucket.
- **Remediation**:
  1. Check browser console for 404 on `config.json`.
  2. Run `python scripts/cd_deploy.py --component frontend` to regenerate and re-upload `config.json`.

### Issue 5: Document Stays in `PROCESSING` State
- **Cause**: Lambda timeout or memory exhaustion on large documents.
- **Remediation**:
  1. Inspect CloudWatch Log Group: `/aws/lambda/doc-redaction-ProcessorFunction-...`.
  2. Verify document file size is under 10 MB limit.
  3. Verify document is valid non-encrypted PDF or UTF-8 TXT.
