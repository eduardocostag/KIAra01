#!/bin/sh
# One automation tick: the API fires due schedules and new-lead triggers and runs queued flows.
# The token is sent only in the Authorization header and never printed.
set -eu
: "${KIARA_API_URL:?defina KIARA_API_URL em /etc/kiara/automation.env}"
: "${KIARA_WORKER_TOKEN:?defina KIARA_WORKER_TOKEN em /etc/kiara/automation.env}"
url="${KIARA_API_URL%/}/v1/automation/internal/tick"
if [ -n "${VERCEL_AUTOMATION_BYPASS_SECRET:-}" ]; then
  exec curl -fsS --max-time 290 -X POST -o /dev/null -w 'tick HTTP %{http_code}\n' \
    -H "Authorization: Bearer ${KIARA_WORKER_TOKEN}" -H "x-vercel-protection-bypass: ${VERCEL_AUTOMATION_BYPASS_SECRET}" "$url"
fi
exec curl -fsS --max-time 290 -X POST -o /dev/null -w 'tick HTTP %{http_code}\n' \
  -H "Authorization: Bearer ${KIARA_WORKER_TOKEN}" "$url"
