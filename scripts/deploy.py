#!/usr/bin/env python3
"""One-command deployment for AWS Academy Learner Lab (works on Windows, macOS, Linux).

Steps it performs:
  1. Checks AWS CLI credentials (from Learner Lab > AWS Details > AWS CLI)
  2. Builds the two Lambda packages into .build/ (installs pypdf for Linux)
  3. Creates an artifacts bucket, packages and deploys the CloudFormation stack
  4. Writes local React config.json (frontend runs with npm run dev)

Usage:
  python scripts/deploy.py                       # full deploy
  python scripts/deploy.py --skip-frontend       # infra + Lambdas only
  python scripts/deploy.py --frontend-only       # re-upload the website only
  python scripts/deploy.py --use-comprehend false
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".build"
INFRA = ROOT / "infra"
FRONTEND = ROOT / "frontend"


def run(cmd, cwd=None, capture=False):
    exe = shutil.which(cmd[0])
    if not exe:
        sys.exit(f"ERROR: '{cmd[0]}' not found on PATH. Please install it first.")
    printable = " ".join(str(c) for c in cmd)
    print(f"\n$ {printable}")
    result = subprocess.run([exe, *cmd[1:]], cwd=cwd, text=True,
                            capture_output=capture)
    if result.returncode != 0:
        if capture:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        sys.exit(f"ERROR: command failed ({result.returncode}): {printable}")
    return result.stdout if capture else ""


def aws(args, region, capture=True):
    out = run(["aws", *args, "--region", region, "--output", "json"], capture=capture)
    return json.loads(out) if capture and out.strip() else {}


def build_lambdas():
    print("\n=== Building Lambda packages ===")
    shutil.rmtree(BUILD, ignore_errors=True)
    api_dir, proc_dir = BUILD / "api", BUILD / "processor"
    api_dir.mkdir(parents=True)
    proc_dir.mkdir(parents=True)
    shutil.copy(ROOT / "backend" / "api" / "handler.py", api_dir)
    for f in (ROOT / "backend" / "processor").glob("*.py"):
        shutil.copy(f, proc_dir)
    # Install Linux-compatible wheels regardless of the machine we build on
    run([sys.executable, "-m", "pip", "install",
         "-r", str(ROOT / "backend" / "processor" / "requirements.txt"),
         "-t", str(proc_dir), "--platform", "manylinux2014_x86_64",
         "--implementation", "cp", "--python-version", "3.12",
         "--only-binary=:all:", "--upgrade", "--quiet"])


def stack_outputs(stack, region):
    data = aws(["cloudformation", "describe-stacks", "--stack-name", stack], region)
    outs = data["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outs}


def deploy_stack(stack, region, account, args):
    bucket = f"{stack}-artifacts-{account}-{region}".lower()[:63]
    print(f"\n=== Ensuring artifacts bucket s3://{bucket} ===")
    exists = subprocess.run([shutil.which("aws"), "s3api", "head-bucket", "--bucket", bucket,
                             "--region", region], capture_output=True).returncode == 0
    if not exists:
        run(["aws", "s3", "mb", f"s3://{bucket}", "--region", region])

    print("\n=== Packaging and deploying CloudFormation stack (5-15 min first time) ===")
    packaged = BUILD / "packaged.yaml"
    run(["aws", "cloudformation", "package",
         "--template-file", str(INFRA / "template.yaml"),
         "--s3-bucket", bucket, "--output-template-file", str(packaged),
         "--region", region])
    run(["aws", "cloudformation", "deploy",
         "--template-file", str(packaged),
         "--stack-name", stack,
         "--capabilities", "CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND",
         "--no-fail-on-empty-changeset",
         "--region", region,
         "--parameter-overrides",
         f"UseComprehend={args.use_comprehend}",
         f"LabRoleName={args.lab_role}"])


def deploy_frontend(outputs, region, skip_build=False):
    print("\n=== Writing local React configuration ===")
    config = {
        "region": outputs["Region"],
        "apiUrl": outputs["ApiUrl"],
        "userPoolId": outputs["UserPoolId"],
        "userPoolClientId": outputs["UserPoolClientId"],
    }
    config_path = FRONTEND / "public" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Wrote {config_path}")
    print("Run: cd frontend; npm run dev")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stack", default="doc-redaction")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--lab-role", default="LabRole")
    p.add_argument("--use-comprehend", default="true", choices=["true", "false"])
    p.add_argument("--skip-frontend", action="store_true")
    p.add_argument("--frontend-only", action="store_true")
    p.add_argument("--skip-npm-build", action="store_true", help="upload existing frontend/dist")
    args = p.parse_args()

    started = time.time()
    ident = aws(["sts", "get-caller-identity"], args.region)
    account = ident["Account"]
    print(f"Using AWS account {account} as {ident['Arn']} in {args.region}")

    if not args.frontend_only:
        build_lambdas()
        deploy_stack(args.stack, args.region, account, args)

    outputs = stack_outputs(args.stack, args.region)
    if not args.skip_frontend:
        deploy_frontend(outputs, args.region, args.skip_npm_build)

    print("\n" + "=" * 70)
    print("DEPLOYMENT COMPLETE in %.1f min" % ((time.time() - started) / 60))
    for k in ("ApiUrl", "UserPoolId", "RawBucketName", "CleanBucketName", "TableName"):
        print(f"  {k:18} {outputs.get(k)}")
    print("Frontend: run cd frontend then npm run dev; open http://localhost:5173")
    print("=" * 70)


if __name__ == "__main__":
    main()
