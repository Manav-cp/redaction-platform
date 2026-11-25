# RedactIQ – Disaster Recovery & Rollback Guide

## 1. Automated Snapshot Mechanism
Every deployment performed by `scripts/cd_deploy.py` automatically generates a complete pre-deployment rollback snapshot in `.build/rollback_backups/<timestamp>/` before altering any live cloud resource.

Each snapshot contains:
- `ApiFunction_<physicalId>.zip`: Active Lambda code archive downloaded directly from AWS Lambda.
- `ProcessorFunction_<physicalId>.zip`: Active Processor Lambda code archive.
- `index.html`: Active frontend entrypoint from S3.
- `config.json`: Active environment configuration from S3.
- `manifest.json`: JSON document recording code SHA256 checksums, stack name, and timestamps.

---

## 2. Executing an Automated Rollback

If any post-deployment anomaly is detected, execute the one-command rollback engine:

```powershell
python scripts/rollback.py
```

### Rollback Process:
1. Discovers the latest snapshot directory in `.build/rollback_backups/`.
2. Validates snapshot integrity via `manifest.json`.
3. Calls `aws lambda update-function-code` to restore previous Lambda packages.
4. Waits for Lambda update completion via AWS Lambda waiters.
5. Uploads the backed-up `index.html` and `config.json` to S3 frontend bucket.
6. Executes post-deployment smoke tests to confirm healthy state recovery.

---

## 3. Restoring a Specific Historical Snapshot
To restore a specific timestamped snapshot:
```powershell
python scripts/rollback.py --snapshot 20261125_221335
```

---

## 4. Emergency Manual Rollback Procedure
If Python execution is unavailable:
1. **Lambda Rollback**:
   In AWS Console > Lambda > Select Function > **Upload from > .zip file** > select the backup zip from `.build/rollback_backups/<timestamp>/`.
2. **Frontend Rollback**:
   In AWS Console > S3 > `redactiq-frontend-058264205875` > Upload `index.html` from the backup snapshot folder.
