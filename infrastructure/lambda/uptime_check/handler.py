"""SkillPulse uptime check, run by AWS Lambda every 5 minutes.

It visits the live site's /api/ready check, which also tests PostgreSQL.
If the site is not ready, the function raises an error. Lambda counts that
in its "Errors" metric, and a CloudWatch alarm on that metric emails us.
"""

import json
import os
import urllib.error
import urllib.request


def handler(event, context):
    url = os.environ["CHECK_URL"]
    request = urllib.request.Request(url, headers={"User-Agent": "skillpulse-uptime-check"})

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{url} returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{url} could not be checked: {exc}") from exc

    if status != 200 or body.get("status") != "ready":
        raise RuntimeError(f"{url} is not ready: HTTP {status}, body {body}")

    print(f"OK {url} database={body.get('database')}")
    return {"status": "ok"}
