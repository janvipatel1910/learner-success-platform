# SkillPulse Runbook

What to do when a SkillPulse alarm emails you. Written for one person running
the live demo; every command is run from your own computer with the AWS CLI
(region `eu-west-2`). No SSH is needed: commands reach the server through
AWS Systems Manager (SSM) Run Command.

| Thing | Value |
|---|---|
| Live site | https://d2aji2q3nf26vx.cloudfront.net |
| Readiness check (API + database) | https://d2aji2q3nf26vx.cloudfront.net/api/ready |
| EC2 instance | `i-0306f814af3a27f08` |
| Alert email topic | SNS `skillpulse-alerts` |
| Uptime checker | Lambda `skillpulse-uptime-check` (every 5 minutes) |

## 1. First two minutes (any alarm)

1. Open the readiness check in a browser.
   - `{"status":"ready","database":"connected"}` = the site is working.
   - `504 Gateway Timeout` = CloudFront cannot reach the API.
   - `503` with `"database":"unavailable"` = the API runs but PostgreSQL is down.
2. Check the server and containers:

```bash
cat > /tmp/ps.json <<'EOF'
{"commands":["cd /opt/skillpulse && docker compose --env-file deploy/.env --file deploy/compose.prod.yaml ps && df -h / && free -m"]}
EOF
aws ssm send-command --region eu-west-2 --instance-ids i-0306f814af3a27f08 \
  --document-name AWS-RunShellScript --parameters file:///tmp/ps.json \
  --query Command.CommandId --output text
```

Read the result (replace `COMMAND-ID`):

```bash
aws ssm get-command-invocation --region eu-west-2 \
  --instance-id i-0306f814af3a27f08 --command-id COMMAND-ID \
  --query "[Status, StandardOutputContent, StandardErrorContent]"
```

Healthy output shows `backend` and `database` as `Up (healthy)`.

## 2. Alarms

### `skillpulse-site-not-ready`

**Meaning:** the uptime checker failed in 2 of the last 3 checks. The API or
the database is not answering, even if the server itself is running.

**Find out why:**

```bash
aws logs tail /aws/lambda/skillpulse-uptime-check --region eu-west-2 --since 30m
```

- `returned HTTP 504` → the API container is stopped or crashed.
- `returned HTTP 503` → PostgreSQL is down.

**Fix: start the API (and the database if needed):**

```bash
cat > /tmp/start.json <<'EOF'
{"commands":["cd /opt/skillpulse && docker compose --env-file deploy/.env --file deploy/compose.prod.yaml up --detach && sleep 15 && docker compose --env-file deploy/.env --file deploy/compose.prod.yaml ps"]}
EOF
aws ssm send-command --region eu-west-2 --instance-ids i-0306f814af3a27f08 \
  --document-name AWS-RunShellScript --parameters file:///tmp/start.json \
  --query Command.CommandId --output text
```

If the API keeps stopping, read its logs:

```bash
cat > /tmp/logs.json <<'EOF'
{"commands":["cd /opt/skillpulse && docker compose --env-file deploy/.env --file deploy/compose.prod.yaml logs --tail 100 backend"]}
EOF
aws ssm send-command --region eu-west-2 --instance-ids i-0306f814af3a27f08 \
  --document-name AWS-RunShellScript --parameters file:///tmp/logs.json \
  --query Command.CommandId --output text
```

**Done when:** `/api/ready` shows `ready` and the OK email arrives
(within about 15 minutes).

### `skillpulse-backend-status-check-failed`

**Meaning:** AWS's own health check of the EC2 server failed, or the server
is stopped. The whole API is down.

**Check:** EC2 console → instance `i-0306f814af3a27f08` → **Status checks**.

**Fix:**
- Instance **stopped**: start it (EC2 console → Instance state → Start). The
  containers restart on their own (`restart: unless-stopped`). The Elastic IP
  stays the same, so CloudFront keeps working.
- Instance running but **status check failed**: reboot it (Instance state →
  Reboot). If the system check still fails, stop and start it, which moves it
  to new hardware.

Then follow "First two minutes" to confirm the containers are healthy.

### `skillpulse-backend-cpu-high`

**Meaning:** CPU above 80% for 15 minutes. The site may be slow.

**Check:** run the container check above, then look at what is busy:

```bash
cat > /tmp/top.json <<'EOF'
{"commands":["docker stats --no-stream && top -b -n 1 | head -20"]}
EOF
aws ssm send-command --region eu-west-2 --instance-ids i-0306f814af3a27f08 \
  --document-name AWS-RunShellScript --parameters file:///tmp/top.json \
  --query Command.CommandId --output text
```

**Fix:** if one container is stuck, restart it with the start command above.
If it happens often, the `t4g.small` instance may be too small; resize it in
Terraform (`backend_instance_type`).

## 3. Restore a backup

Nightly `pg_dump` backups go to S3 (`skillpulse-backups-<account-id>`, kept
35 days). To **test** the newest backup in a scratch database (live data is
not touched):

```bash
cat > /tmp/restore-check.json <<'EOF'
{"commands":["cd /opt/skillpulse && bash deploy/restore.sh"]}
EOF
aws ssm send-command --region eu-west-2 --instance-ids i-0306f814af3a27f08 \
  --document-name AWS-RunShellScript --parameters file:///tmp/restore-check.json \
  --query Command.CommandId --output text
```

Expected: user and course counts, then `Restore check passed.`

Restoring over the **live** database is a deliberate, manual step. Stop the
API first, take a fresh backup, and only then restore.

## 4. Outage test (to prove monitoring works)

1. Stop only the API: `docker compose ... stop backend` (through SSM, as above).
2. Confirm `/api/ready` returns 504.
3. Wait for the **ALARM** email (about 10–15 minutes).
4. **Start the API again straight away** with the start command above.
5. Wait for the **OK** email and check `/api/ready` shows `ready`.

> Lesson learned (October 2026): after the first outage test the API was not
> restarted, and the demo site stayed down for 10 days. Step 4 is not optional.

## 5. After any incident

- Write one or two lines below: date, what happened, cause, fix, how long.
- If a command here was wrong or missing, fix this runbook.

### Incident log

| Date | What happened | Cause | Fix | Downtime |
|---|---|---|---|---|
| 2026-10-25 → 2026-11-04 | `site-not-ready` alarm; `/api/ready` returned 504 | API stopped for an outage test and not restarted | Started the API container; alarm changed to 2-of-3 checks to stop repeated emails | About 10 days (demo data only) |
