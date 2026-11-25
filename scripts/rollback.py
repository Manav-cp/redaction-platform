#!/usr/bin/env python3
"""RedactIQ - Automated Rollback Engine
Restores previous verified versions of Lambda functions and Frontend assets.
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is required. Run 'pip install boto3'")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".build"
BACKUPS = BUILD / "rollback_backups"
DEFAULT_REGION = "us-east-1"
EXPECTED_ACCOUNT = "058264205875"
DEFAULT_FRONTEND_BUCKET = f"redactiq-frontend-{EXPECTED_ACCOUNT}"


def log(msg, tag="INFO"):
    print(f"[{time.strftime('%H:%M:%S')}] [{tag}] {msg}")


def get_latest_snapshot():
    if not BACKUPS.exists():
        return None
    snapshots = sorted([d for d in BACKUPS.iterdir() if d.is_dir()], key=lambda d: d.name, reverse=True)
    return snapshots[0] if snapshots else None


def main():
    parser = argparse.ArgumentParser(description="RedactIQ Automated Rollback Engine")
    parser.add_argument("--snapshot", help="Specific snapshot timestamp directory to restore")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS Region (default: us-east-1)")
    args = parser.parse_args()

    log("Starting RedactIQ Rollback Engine...")

    if args.snapshot:
        snapshot_dir = BACKUPS / args.snapshot
    else:
        snapshot_dir = get_latest_snapshot()

    if not snapshot_dir or not snapshot_dir.exists():
        log(f"No rollback snapshot found at {snapshot_dir}", "FATAL")
        sys.exit(1)

    manifest_file = snapshot_dir / "manifest.json"
    if not manifest_file.exists():
        log(f"Snapshot manifest missing at {manifest_file}", "FATAL")
        sys.exit(1)

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    log(f"Loaded rollback snapshot from: {snapshot_dir.name} (created {manifest.get('timestamp')})")

    # Verify AWS Identity
    sts = boto3.client("sts", region_name=args.region)
    ident = sts.get_caller_identity()
    account = ident.get("Account")
    if account != EXPECTED_ACCOUNT:
        log(f"Account mismatch: expected {EXPECTED_ACCOUNT}, got {account}", "FATAL")
        sys.exit(1)

    # 1. Restore Lambda Functions
    lambda_client = boto3.client("lambda", region_name=args.region)
    for logical_id, info in manifest.get("lambdas", {}).items():
        phys_id = info["physical_id"]
        backup_zip = snapshot_dir / info["backup_file"]
        if not backup_zip.exists():
            log(f"Backup file for {logical_id} not found: {backup_zip}", "WARN")
            continue

        log(f"Rolling back {logical_id} ({phys_id}) from {backup_zip.name}...")
        with open(backup_zip, "rb") as f:
            zip_bytes = f.read()

        lambda_client.update_function_code(FunctionName=phys_id, ZipFile=zip_bytes)
        waiter = lambda_client.get_waiter("function_updated")
        waiter.wait(FunctionName=phys_id)
        log(f"Lambda {logical_id} rollback complete.")

    # 2. Restore Frontend Assets
    s3_client = boto3.client("s3", region_name=args.region)
    bucket = DEFAULT_FRONTEND_BUCKET
    for key, filename in manifest.get("frontend", {}).items():
        backup_file = snapshot_dir / filename
        if not backup_file.exists():
            log(f"Backup file for frontend {key} not found: {backup_file}", "WARN")
            continue

        log(f"Rolling back s3://{bucket}/{key} from {backup_file.name}...")
        ctype = "text/html; charset=utf-8" if key.endswith(".html") else "application/json; charset=utf-8"
        with open(backup_file, "rb") as data:
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=ctype,
                CacheControl="no-cache, no-store, must-revalidate",
            )
        log(f"Frontend {key} restored.")

    log("Rollback completed! Running verification...", "SUCCESS")
    # Run verification
    from cd_deploy import check_prerequisites, post_deployment_verification
    context = check_prerequisites(region=args.region)
    post_deployment_verification(context)
    log("System successfully rolled back and verified healthy!", "SUCCESS")


if __name__ == "__main__":
    main()
