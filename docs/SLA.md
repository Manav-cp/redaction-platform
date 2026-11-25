# Service Level Agreement (SLA)

## Targets

| Metric | Target | How it is measured |
|---|---|---|
| Monthly availability | **99.9 %** | Successful (non-5xx) API responses ÷ total, CloudWatch `AWS/ApiGateway 5xx` vs `Count` |
| Maximum tolerable downtime | **43.8 min / month** | 0.1 % of 730 h |
| Latency SLO | **95 % of status lookups < 350 ms** | `ApiLatencyAlarm` on p95 `Latency` |
| Processing time | 95 % of documents ≤ 10 MB processed < 60 s | `ProcessorDurationAlarm` on p95 `Duration` |
| RPO (data loss) | **< 1 minute** | DynamoDB Point-in-Time Recovery (continuous backups, 35 days); S3 versioning on outputs |
| RTO (recovery time) | **< 10 minutes** for the application tier | Entire stack is code (`infra/template.yaml`); `python scripts/deploy.py` redeploys in ~5–8 min (CloudFront creation may add a few minutes on first deploy) |

The underlying AWS services publish their own SLAs (Lambda, S3, DynamoDB, API Gateway, CloudFront all ≥ 99.9 % or better), and the design has no single server that can fail.

## Exclusions
Scheduled maintenance announced 24 h in advance, AWS regional outages, client-side network issues, and AWS Academy Learner Lab session shutdowns.

## Incident response procedure

| Step | Action |
|---|---|
| 1. Detect | CloudWatch alarm enters ALARM state (errors, throttles, 5xx, latency). Check the `doc-redaction-dashboard`. |
| 2. Triage | Open CloudWatch Logs for the failing function; failed documents carry an `errorMessage` in DynamoDB. |
| 3. Mitigate | Bad deploy → re-run CI on the last good commit (or `git revert` + push). Throttling → raise API throttle / Lambda memory. Abuse → enable WAF (`--enable-waf true`). |
| 4. Recover data | DynamoDB: *Restore to point in time* (console → table → Backups) into a new table, then update `TABLE_NAME`. S3 outputs: restore previous object version. |
| 5. Full region loss | Deploy the same template to `us-west-2`: `python scripts/deploy.py --region us-west-2`. |
| 6. Post-mortem | Record timeline, root cause and preventive action within 48 h. |

## Disaster recovery drill (to demo in viva)
1. Delete the stack: `python scripts/destroy.py`.
2. Start a timer and run `python scripts/deploy.py`.
3. Stop when the site loads — this is your measured RTO.
