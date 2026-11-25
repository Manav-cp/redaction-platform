#!/usr/bin/env python3
"""Tear down everything (saves Learner Lab budget).

Empties all buckets (including old object versions) and deletes the stack and
the artifacts bucket.

Usage: python scripts/destroy.py [--stack doc-redaction] [--region us-east-1]
"""

import argparse
import json
import shutil
import subprocess
import sys

AWS = shutil.which("aws") or sys.exit("AWS CLI not found")


def aws(*args, region, check=True):
    r = subprocess.run([AWS, *args, "--region", region, "--output", "json"],
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        print(r.stderr)
        sys.exit(f"Failed: aws {' '.join(args)}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def empty_bucket(bucket, region):
    print(f"Emptying s3://{bucket} ...")
    while True:
        data = aws("s3api", "list-object-versions", "--bucket", bucket, "--max-items", "900",
                   region=region, check=False)
        objs = [{"Key": o["Key"], "VersionId": o["VersionId"]}
                for o in data.get("Versions", []) + data.get("DeleteMarkers", [])]
        if not objs:
            break
        aws("s3api", "delete-objects", "--bucket", bucket,
            "--delete", json.dumps({"Objects": objs, "Quiet": True}), region=region)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stack", default="doc-redaction")
    p.add_argument("--region", default="us-east-1")
    a = p.parse_args()

    account = aws("sts", "get-caller-identity", region=a.region)["Account"]
    stacks = aws("cloudformation", "describe-stacks", "--stack-name", a.stack,
                 region=a.region, check=False).get("Stacks", [])
    if stacks:
        outs = {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}
        for key in ("FrontendBucketName", "RawBucketName", "CleanBucketName"):
            if outs.get(key):
                empty_bucket(outs[key], a.region)
        print(f"Deleting stack {a.stack} (CloudFront deletion can take ~10 min) ...")
        aws("cloudformation", "delete-stack", "--stack-name", a.stack, region=a.region)
        aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", a.stack, region=a.region)

    artifacts = f"{a.stack}-artifacts-{account}-{a.region}".lower()[:63]
    exists = subprocess.run([AWS, "s3api", "head-bucket", "--bucket", artifacts, "--region", a.region],
                            capture_output=True).returncode == 0
    if exists:
        empty_bucket(artifacts, a.region)
        aws("s3api", "delete-bucket", "--bucket", artifacts, region=a.region, check=False)
    print("All resources removed.")


if __name__ == "__main__":
    main()
