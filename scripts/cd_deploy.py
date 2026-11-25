#!/usr/bin/env python3
"""RedactIQ - Production Continuous Deployment (CD) Engine
Safe, zero-downtime, non-destructive deployment for AWS Academy Learner Lab.

Stages:
  Stage A: Pre-deployment verification & rollback backup creation
  Stage B: Frontend deployment (S3 website, assets first, no-delete, cache control)
  Stage C: Backend deployment (Lambda code update, runtime verified, zero stack churn)
  Stage D: Post-deployment verification (Smoke tests & health checks)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is required. Run 'pip install boto3'")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".build"
BACKUPS = BUILD / "rollback_backups"
EXPECTED_ACCOUNT = "058264205875"
DEFAULT_REGION = "us-east-1"
DEFAULT_STACK = "doc-redaction"
DEFAULT_FRONTEND_BUCKET = f"redactiq-frontend-{EXPECTED_ACCOUNT}"


def log(msg, tag="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag}] {msg}")


def check_prerequisites(region=DEFAULT_REGION):
    """Stage A: Pre-deployment verification."""
    log("=== Stage A: Pre-Deployment Verification ===")
    sts = boto3.client("sts", region_name=region)
    try:
        ident = sts.get_caller_identity()
    except Exception as e:
        log(f"AWS session inactive or credentials expired: {e}", "FATAL")
        log("Please start/refresh AWS Academy Learner Lab credentials.", "FATAL")
        sys.exit(1)

    account = ident.get("Account")
    arn = ident.get("Arn")
    log(f"Active caller ARN: {arn}")
    log(f"AWS Account ID: {account}")

    if account != EXPECTED_ACCOUNT:
        log(f"Account mismatch! Expected {EXPECTED_ACCOUNT}, got {account}", "FATAL")
        sys.exit(1)

    cfn = boto3.client("cloudformation", region_name=region)
    try:
        stacks = cfn.describe_stacks(StackName=DEFAULT_STACK)["Stacks"]
        stack = stacks[0]
        status = stack["StackStatus"]
        log(f"CloudFormation stack '{DEFAULT_STACK}' status: {status}")
        if status not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
            log(f"Stack is not in a healthy state ({status})", "FATAL")
            sys.exit(1)
    except Exception as e:
        log(f"Failed to query CloudFormation stack '{DEFAULT_STACK}': {e}", "FATAL")
        sys.exit(1)

    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
    log(f"Discovered stack outputs: {list(outputs.keys())}")

    # Discover Lambda functions dynamically
    resources = cfn.list_stack_resources(StackName=DEFAULT_STACK)["StackResourceSummaries"]
    lambdas = {}
    for r in resources:
        if r["ResourceType"] == "AWS::Lambda::Function":
            lambdas[r["LogicalResourceId"]] = r["PhysicalResourceId"]
    log(f"Discovered Lambda resources: {lambdas}")

    if "ApiFunction" not in lambdas or "ProcessorFunction" not in lambdas:
        log("Required Lambda functions not found in stack resources", "FATAL")
        sys.exit(1)

    # Check S3 Buckets
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=DEFAULT_FRONTEND_BUCKET)
        log(f"Frontend bucket verified: s3://{DEFAULT_FRONTEND_BUCKET}")
    except Exception as e:
        log(f"Cannot access frontend bucket '{DEFAULT_FRONTEND_BUCKET}': {e}", "FATAL")
        sys.exit(1)

    # Verify existing live site & API
    website_url = f"http://{DEFAULT_FRONTEND_BUCKET}.s3-website-{region}.amazonaws.com"
    log(f"Checking existing website availability: {website_url}")
    try:
        req = urllib.request.Request(f"{website_url}/config.json", headers={"User-Agent": "RedactIQ-CD"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            cfg = json.loads(resp.read().decode("utf-8"))
            log(f"Existing live config.json is healthy: {cfg}")
    except Exception as e:
        log(f"Warning: could not retrieve live config.json (may be initial deploy or transient): {e}", "WARN")

    return {
        "account": account,
        "region": region,
        "outputs": outputs,
        "lambdas": lambdas,
        "frontend_bucket": DEFAULT_FRONTEND_BUCKET,
        "website_url": website_url,
    }


def create_rollback_backup(context):
    """Creates a local snapshot of current Lambda code and frontend configuration."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUPS / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    log(f"Creating rollback snapshot at: {backup_dir}")

    region = context["region"]
    lambda_client = boto3.client("lambda", region_name=region)
    s3_client = boto3.client("s3", region_name=region)

    manifest = {
        "timestamp": timestamp,
        "stack": DEFAULT_STACK,
        "region": region,
        "lambdas": {},
        "frontend": {},
    }

    # Backup Lambda function code packages
    for logical_id, phys_id in context["lambdas"].items():
        try:
            fn_info = lambda_client.get_function(FunctionName=phys_id)
            code_url = fn_info["Code"]["Location"]
            dest_zip = backup_dir / f"{logical_id}_{phys_id}.zip"
            urllib.request.urlretrieve(code_url, str(dest_zip))
            log(f"Backed up {logical_id} code ({dest_zip.stat().st_size} bytes)")
            manifest["lambdas"][logical_id] = {
                "physical_id": phys_id,
                "backup_file": str(dest_zip.name),
                "code_sha256": fn_info["Configuration"]["CodeSha256"],
            }
        except Exception as e:
            log(f"Failed to backup Lambda {logical_id} ({phys_id}): {e}", "WARN")

    # Backup live index.html and config.json from frontend S3
    bucket = context["frontend_bucket"]
    for key in ["index.html", "config.json"]:
        try:
            dest_file = backup_dir / key
            s3_client.download_file(bucket, key, str(dest_file))
            log(f"Backed up frontend s3://{bucket}/{key}")
            manifest["frontend"][key] = str(dest_file.name)
        except Exception as e:
            log(f"Could not download s3://{bucket}/{key} for backup: {e}", "WARN")

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log("Rollback snapshot created successfully.")
    return backup_dir


def build_backend_packages(use_ci_artifacts=True):
    """Builds or extracts Lambda deployment zip archives."""
    log("=== Stage C1: Preparing Backend Deployment Packages ===")
    dist_dir = BUILD / "dist_artifacts"
    api_zip = dist_dir / "api.zip"
    processor_zip = dist_dir / "processor.zip"

    if use_ci_artifacts and api_zip.exists() and processor_zip.exists():
        log(f"Using verified CI artifacts: {api_zip.name}, {processor_zip.name}")
        return api_zip, processor_zip

    log("Building fresh Lambda deployment packages locally...")
    dist_dir.mkdir(parents=True, exist_ok=True)
    api_build = BUILD / "api_stage"
    proc_build = BUILD / "proc_stage"
    shutil.rmtree(api_build, ignore_errors=True)
    shutil.rmtree(proc_build, ignore_errors=True)
    api_build.mkdir(parents=True)
    proc_build.mkdir(parents=True)

    # API Lambda package
    shutil.copy(ROOT / "backend" / "api" / "handler.py", api_build)
    shutil.make_archive(str(dist_dir / "api"), "zip", api_build)

    # Processor Lambda package
    for f in (ROOT / "backend" / "processor").glob("*.py"):
        shutil.copy(f, proc_build)

    # Install Linux-compatible dependencies for Lambda Python 3.12 runtime
    pip_cmd = [
        sys.executable, "-m", "pip", "install",
        "-r", str(ROOT / "backend" / "processor" / "requirements.txt"),
        "-t", str(proc_build),
        "--platform", "manylinux2014_x86_64",
        "--implementation", "cp",
        "--python-version", "3.12",
        "--only-binary=:all:",
        "--upgrade", "--quiet",
    ]
    subprocess.check_call(pip_cmd)

    # Clean __pycache__ and dist-info
    for d in proc_build.glob("**/__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    for d in proc_build.glob("**/*.dist-info"):
        shutil.rmtree(d, ignore_errors=True)

    shutil.make_archive(str(dist_dir / "processor"), "zip", proc_build)
    log(f"Built packages: api.zip ({api_zip.stat().st_size} B), processor.zip ({processor_zip.stat().st_size} B)")
    return api_zip, processor_zip


def deploy_backend(context, api_zip, processor_zip):
    """Deploys Lambda code updates using direct API calls (zero stack churn)."""
    log("=== Stage C2: Updating Lambda Function Code ===")
    region = context["region"]
    lambda_client = boto3.client("lambda", region_name=region)

    packages = {
        "ApiFunction": api_zip,
        "ProcessorFunction": processor_zip,
    }

    for logical_id, zip_path in packages.items():
        phys_id = context["lambdas"][logical_id]
        log(f"Deploying {logical_id} ({phys_id}) from {zip_path.name}...")
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        lambda_client.update_function_code(
            FunctionName=phys_id,
            ZipFile=zip_bytes,
        )

        log(f"Waiting for {logical_id} update to complete...")
        waiter = lambda_client.get_waiter("function_updated")
        waiter.wait(FunctionName=phys_id)

        cfg = lambda_client.get_function_configuration(FunctionName=phys_id)
        log(f"{logical_id} successfully updated! State: {cfg.get('State')}, LastUpdate: {cfg.get('LastUpdateStatus')}")


def build_and_deploy_frontend(context):
    """Deploys frontend to S3 website bucket with safe sequencing and zero delete."""
    log("=== Stage B: Deploying React Frontend to S3 Website ===")
    dist = ROOT / "frontend" / "dist"
    if not dist.exists() or not (dist / "index.html").exists():
        log("frontend/dist not found. Running npm run build...")
        subprocess.check_call(["npm", "run", "build"], cwd=str(ROOT / "frontend"), shell=(os.name == "nt"))

    # Generate and write config.json in dist
    outputs = context["outputs"]
    config = {
        "region": outputs.get("Region", context["region"]),
        "apiUrl": outputs["ApiUrl"],
        "userPoolId": outputs["UserPoolId"],
        "userPoolClientId": outputs["UserPoolClientId"],
    }
    config_file = dist / "config.json"
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    log(f"Generated {config_file} with stack parameters.")

    s3 = boto3.client("s3", region_name=context["region"])
    bucket = context["frontend_bucket"]

    # Content type mapping
    content_types = {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".txt": "text/plain; charset=utf-8",
    }

    # Step 1: Upload assets first (with long immutable cache headers)
    assets_dir = dist / "assets"
    if assets_dir.exists():
        for f in assets_dir.glob("*"):
            if f.is_file():
                s3_key = f"assets/{f.name}"
                ext = f.suffix.lower()
                ctype = content_types.get(ext, "application/octet-stream")
                log(f"Uploading asset: {s3_key} ({ctype})")
                with open(f, "rb") as data:
                    s3.put_object(
                        Bucket=bucket,
                        Key=s3_key,
                        Body=data,
                        ContentType=ctype,
                        CacheControl="public, max-age=31536000, immutable",
                    )

    # Step 2: Upload root files (except index.html)
    for f in dist.glob("*"):
        if f.is_file() and f.name != "index.html":
            s3_key = f.name
            ext = f.suffix.lower()
            ctype = content_types.get(ext, "application/octet-stream")
            log(f"Uploading root file: {s3_key} ({ctype})")
            with open(f, "rb") as data:
                s3.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=data,
                    ContentType=ctype,
                    CacheControl="no-cache",
                )

    # Step 3: Upload index.html last (ensures atomic update of client entry point)
    index_file = dist / "index.html"
    log("Uploading index.html (entrypoint) with no-cache header...")
    with open(index_file, "rb") as data:
        s3.put_object(
            Bucket=bucket,
            Key="index.html",
            Body=data,
            ContentType="text/html; charset=utf-8",
            CacheControl="no-cache, no-store, must-revalidate",
        )
    log("Frontend files uploaded safely (no --delete used).")


def post_deployment_verification(context):
    """Stage D: Post-deployment verification smoke tests."""
    log("=== Stage D: Post-Deployment Smoke Tests ===")
    website_url = context["website_url"]
    api_url = context["outputs"]["ApiUrl"]
    log(f"Verifying Website URL: {website_url}")
    log(f"Verifying API URL: {api_url}")

    # 1. Verify index.html HTTP 200
    req = urllib.request.Request(f"{website_url}/", headers={"User-Agent": "RedactIQ-SmokeTest"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        html_code = resp.getcode()
        html_content = resp.read().decode("utf-8")
        assert html_code == 200, f"Expected 200 from website index, got {html_code}"
        log(f"Website index.html check passed (HTTP {html_code})")

    # 2. Verify config.json
    req = urllib.request.Request(f"{website_url}/config.json", headers={"User-Agent": "RedactIQ-SmokeTest"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        cfg_code = resp.getcode()
        cfg_data = json.loads(resp.read().decode("utf-8"))
        assert cfg_code == 200, f"Expected 200 from config.json, got {cfg_code}"
        for k in ("region", "apiUrl", "userPoolId", "userPoolClientId"):
            assert k in cfg_data and cfg_data[k], f"Missing key {k} in config.json"
        log("config.json schema & parameters verified.")

    # 3. Verify assets referenced in index.html load correctly
    asset_matches = re.findall(r'src=["\']([^"\']+)["\']|href=["\']([^"\']+\.css)["\']', html_content)
    for m in asset_matches:
        asset_rel = m[0] or m[1]
        if asset_rel.startswith("/"):
            asset_rel = asset_rel[1:]
        asset_url = f"{website_url}/{asset_rel}"
        req = urllib.request.Request(asset_url, headers={"User-Agent": "RedactIQ-SmokeTest"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.getcode() == 200, f"Asset {asset_url} returned HTTP {resp.getcode()}"
        log(f"Verified asset: {asset_rel} (HTTP 200)")

    # 4. Verify API Gateway unauthenticated access returns 401
    try:
        req = urllib.request.Request(f"{api_url}/documents", headers={"User-Agent": "RedactIQ-SmokeTest"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            api_status = resp.getcode()
    except urllib.error.HTTPError as e:
        api_status = e.code
    assert api_status == 401, f"Expected 401 Unauthorized for unauthenticated API, got {api_status}"
    log("API Gateway JWT protection verified (returned HTTP 401 as expected).")

    # 5. Verify Lambda states
    lambda_client = boto3.client("lambda", region_name=context["region"])
    for logical_id, phys_id in context["lambdas"].items():
        cfg = lambda_client.get_function_configuration(FunctionName=phys_id)
        state = cfg.get("State")
        update_status = cfg.get("LastUpdateStatus")
        assert state == "Active", f"Lambda {logical_id} state is {state}, expected Active"
        assert update_status == "Successful", f"Lambda {logical_id} update status is {update_status}"
        log(f"Lambda {logical_id} ({phys_id}) is Active and Healthy.")

    # 6. Verify DynamoDB Table
    ddb = boto3.client("dynamodb", region_name=context["region"])
    tbl_name = context["outputs"]["TableName"]
    tbl_desc = ddb.describe_table(TableName=tbl_name)
    tbl_status = tbl_desc["Table"]["TableStatus"]
    assert tbl_status == "ACTIVE", f"DynamoDB table {tbl_name} status is {tbl_status}"
    log(f"DynamoDB table '{tbl_name}' is ACTIVE.")

    # 7. Verify Cognito User Pool
    cognito = boto3.client("cognito-idp", region_name=context["region"])
    pool_id = context["outputs"]["UserPoolId"]
    pool_desc = cognito.describe_user_pool(UserPoolId=pool_id)
    assert "UserPool" in pool_desc, f"Cognito User Pool {pool_id} not found"
    log(f"Cognito User Pool '{pool_id}' is available.")

    log("ALL POST-DEPLOYMENT VERIFICATION CHECKS PASSED!", "SUCCESS")


def main():
    parser = argparse.ArgumentParser(description="RedactIQ Continuous Deployment Engine")
    parser.add_argument("--component", choices=["all", "frontend", "backend"], default="all",
                        help="Deploy 'all', 'frontend' only, or 'backend' only")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS Region (default: us-east-1)")
    parser.add_argument("--skip-backup", action="store_true", help="Skip creating rollback snapshot")
    parser.add_argument("--verify-only", action="store_true", help="Run verification smoke tests only")
    args = parser.parse_args()

    started = time.time()
    log("Starting RedactIQ Continuous Deployment Pipeline...")

    context = check_prerequisites(region=args.region)

    if args.verify_only:
        post_deployment_verification(context)
        sys.exit(0)

    if not args.skip_backup:
        create_rollback_backup(context)

    if args.component in ("all", "backend"):
        api_zip, proc_zip = build_backend_packages()
        deploy_backend(context, api_zip, proc_zip)

    if args.component in ("all", "frontend"):
        build_and_deploy_frontend(context)

    post_deployment_verification(context)

    elapsed = time.time() - started
    log(f"DEPLOYMENT COMPLETED SUCCESSFULLY IN {elapsed:.1f} SECONDS", "SUCCESS")
    print("\n" + "=" * 60)
    print("RedactIQ Live Deployment Summary:")
    print(f"  Website URL: {context['website_url']}")
    print(f"  API URL:     {context['outputs']['ApiUrl']}")
    print(f"  UserPool ID: {context['outputs']['UserPoolId']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
