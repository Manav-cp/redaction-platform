# RedactIQ: Serverless AI-Driven Document Processing & Sensitive Data Redaction Platform

**Form title:** *Serverless Document Processing and Sensitive Data Redaction Platform using AWS Lambda, DynamoDB, and CloudFront*

You upload a PDF or TXT. An event-driven serverless pipeline finds the personal data in it
(emails, phone numbers, SSNs, credit cards, Aadhaar, PAN, IP addresses, dates of birth, and with Amazon Comprehend also
names, addresses and bank numbers) and gives back a redacted copy you can download.

```
redaction-platform/
├── backend/
│   ├── api/handler.py            # REST Lambda: upload URL, list, status, delete
│   ├── processor/                # S3-triggered Lambda: extract → detect → redact → save
│   │   ├── handler.py
│   │   ├── pii_detector.py       # regex + Luhn + Amazon Comprehend, span merging
│   │   ├── pdf_utils.py          # pypdf text extraction + dependency-free PDF writer
│   │   └── requirements.txt
│   ├── tests/                    # 23 PyTest unit tests
│   └── requirements-dev.txt
├── frontend/                     # React + Vite single-page app (Cognito auth, drag-drop upload)
├── infra/template.yaml           # Whole stack as CloudFormation (SAM transform)
├── scripts/cd_deploy.py          # Continuous Deployment engine (pre/post checks, zero delete)
├── scripts/rollback.py           # Automated rollback engine
├── scripts/e2e_test.py           # End-to-end cloud verification test suite
├── scripts/deploy.py             # Full CloudFormation stack deployment
├── scripts/destroy.py            # Teardown script
├── .github/workflows/ci.yml      # CI: lint → test → cfn-lint → pip-audit → npm audit → build
├── .github/workflows/cd.yml      # CD: controlled deployment with safety gates
├── .github/workflows/runner-test.yml # Harmless self-hosted runner connectivity test
├── iam-policies/                 # Least-privilege policies (for non-Learner-Lab accounts)
├── docs/                         # Project Report, SLA, Guides, and Presentation Material
│   ├── FINAL_PROJECT_REPORT.md   # Complete 43-section M.Tech Project Report (.docx, .pdf)
│   ├── SLA.md                    # Academic Service Level Agreement (.docx, .pdf)
│   ├── CICD.md                   # Complete CI/CD Architecture & Operations Manual
│   ├── TEST_REPORT.md            # Empirical Unit & Live Testing Results
│   ├── DEPLOYMENT_GUIDE.md       # Production Deployment Operations Guide
│   ├── ROLLBACK_GUIDE.md         # Automated & Emergency Rollback Procedures
│   ├── TROUBLESHOOTING.md        # Incident Remediation & Debugging Guide
│   ├── FINAL_VERIFICATION.md     # Component Verification Matrix & Live Evidence
│   ├── PRESENTATION_SCRIPT.md    # Defense Presentation Script
│   ├── VIVA_QUESTIONS.md         # Technical Defense & Professor Viva Q&A
│   └── LIVE_DEMO_GUIDE.md        # Step-by-Step Live Evaluator Demo Guide
└── samples/                      # Fake invoice PDF + résumé TXT full of test PII
```

---

## Step-by-step execution on AWS Academy Learner Lab

### Step 0: Install tools on your laptop (one time)

| Tool | Check | Get it |
|---|---|---|
| Python 3.10+ | `python --version` (Windows: `py --version`) | python.org |
| Node.js 20 LTS | `node -v` | nodejs.org |
| AWS CLI v2 | `aws --version` | https://aws.amazon.com/cli/ |
| Git (for CI/CD) | `git --version` | git-scm.com |

### Step 1: Start the Learner Lab and copy your credentials
1. AWS Academy → your course → **Modules → Launch AWS Academy Learner Lab**.
2. Click **Start Lab** and wait until the dot next to **AWS** turns **green** (1–2 min).
3. Click **AWS Details → AWS CLI: Show**. Copy the whole block (`[default]`, access key, secret key, **session token**).
4. Paste it into your credentials file, replacing what's there:
   * Windows: `C:\Users\<you>\.aws\credentials`
   * macOS/Linux: `~/.aws/credentials`
5. Set the region (Learner Lab only allows us-east-1 / us-west-2):
   ```bash
   aws configure set region us-east-1
   aws sts get-caller-identity        # should print your account and assumed-role/voclabs/...
   ```
   > The credentials expire when the lab session ends (~4 h). Next time, start the lab and paste the new block again. Your deployed resources stay.

### Step 2: Unzip and (optionally) run the tests locally
```bash
cd redaction-platform
python -m pip install -r backend/requirements-dev.txt
python -m pytest backend -q            # 23 passed
cd frontend && npm install && npm test && cd ..
```

### Step 3: Deploy everything with one command
```bash
python scripts/deploy.py
```
What it does (takes ~8–15 min the first time, mostly CloudFront):
1. Builds both Lambda zips into `.build/` (downloads Linux wheels of `pypdf`).
2. Creates an artifacts bucket, runs `aws cloudformation package` and `deploy` for stack **`doc-redaction`**.
3. Builds the React app, writes `config.json` with your API URL and Cognito IDs, uploads to S3.
4. Invalidates the CloudFront cache and prints the outputs:
```
WebsiteURL   https://dxxxxxxxx.cloudfront.net
ApiUrl       https://xxxx.execute-api.us-east-1.amazonaws.com
...
```
Options: `--use-comprehend false` (regex only, $0), `--enable-waf true` (adds AWS WAF), `--frontend-only` (re-upload UI only), `--skip-frontend`.

### Step 4: Use the live site
1. Open the **WebsiteURL** (if you see an XML *AccessDenied* error, CloudFront is still spreading. Wait 2–5 minutes).
2. **Create account** with a real email → enter the 6-digit code from the email (check spam).
   *No email?* Console → Cognito → User pools → `doc-redaction-users` → Users → select user → **Actions → Confirm account**.
3. Drag `samples/sample_invoice.pdf` and `samples/sample_resume.txt` onto the upload box.
4. Status goes **Uploading → Processing → Redacted** in a few seconds; the chips show what was found.
5. Click **Download** to get the `redacted_*.pdf/.txt`.

### Step 5: Collect evidence screenshots for your report (AWS Console)
| Pillar | Where to look |
|---|---|
| Architecture / services | CloudFormation → `doc-redaction` → **Resources** tab (all ~30 resources) |
| Compute | Lambda → `doc-redaction-ProcessorFunction-…` → **Monitor** |
| Storage | S3 → raw bucket `uploads/…`, clean bucket `redacted/…`, lifecycle rules, *Block public access: On* |
| Database | DynamoDB → table → **Explore items** (status, piiCounts) · **Backups** (PITR on) |
| Identity | Cognito → user pool → Users, password policy, MFA optional |
| CDN + SSL | CloudFront → distribution → padlock 🔒 in browser, *Origin access control* |
| Monitoring | CloudWatch → **Dashboards → doc-redaction-dashboard** and **Alarms** (5 alarms) |
| Security | S3 bucket policies (deny non-TLS), API Gateway → Authorization (JWT), Throttling |
| Cost | Billing / Cost Explorer (may be restricted in Learner Lab), `docs/COSTING.md` |

### Step 6: CI/CD with GitHub Actions
1. Create an empty GitHub repo and push the project:
   ```bash
   git init && git add . && git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<you>/redaction-platform.git
   ```
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**, add from Learner Lab *AWS Details*:
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`.
3. `git push -u origin main`. Open the **Actions** tab: job **test** (flake8, pytest, cfn-lint, pip-audit, vitest, build, npm audit) then **deploy** (package Lambdas + API, build React, S3 sync, CloudFront invalidation, live smoke test).
4. Demo: change some text in `frontend/src/App.jsx`, push, and show the site updating on its own.
   > Learner Lab tokens expire every session, so update the 3 secrets before each demo run.

### Step 7: Optional extras
* **WAF**: `python scripts/deploy.py --enable-waf true` (rate limit 100 req / 5 min per IP + AWS managed rules on CloudFront). If Learner Lab refuses WAF, the stack rolls back that change only; redeploy with `false`.
* **Comprehend**: on by default. If your lab blocks it, processing still works: the code falls back to regex, and the table shows `engine: regex`.
* **Local UI development**: after one deploy, `cd frontend && npm run dev` → http://localhost:5173 (already allowed in CORS).

### Step 8: Clean up (save lab credit)
```bash
python scripts/destroy.py
```

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `ExpiredToken` / `InvalidClientTokenId` | Lab session ended. Start Lab, paste the new credentials (Step 1). |
| Stack fails: `LabRole` / `iam:PassRole` | Make sure you're in Learner Lab (not a sandbox lab) and in us-east-1. Check that `LabRole` exists in IAM → Roles. |
| `ROLLBACK_COMPLETE` | CloudFormation → stack → **Events**, read the first red reason, then `python scripts/destroy.py` and deploy again. |
| Site says *Configuration error* | Run `python scripts/deploy.py --frontend-only`. |
| Upload fails with CORS error | Use the CloudFront URL (not the S3 URL); wait for the invalidation to finish. |
| Document **Failed** "No extractable text" | It's a scanned image PDF. Use a text PDF (e.g. one exported from Word). |
| `python` not found on Windows | Use `py scripts/deploy.py`. |

## Grading pillar map
| # | Requirement | Implementation |
|---|---|---|
| 1 | Cloud generation & pattern | Serverless, event-driven (S3 event → Lambda), see `docs/ARCHITECTURE.md` |
| 2 | Cloud services | Lambda, S3 ×3, DynamoDB, Cognito, API Gateway, CloudFront, Comprehend, WAF, CloudWatch, CloudFormation |
| 3 | Costing | `docs/COSTING.md` |
| 4 | CI/CD | `.github/workflows/deploy.yml` |
| 5 | Security | `docs/SECURITY.md`, `iam-policies/` |
| 6 | SLA | `docs/SLA.md` (99.9 %, RPO < 1 min, RTO < 10 min) |
| 7 | Live hosting | CloudFront HTTPS URL printed by `deploy.py` |
