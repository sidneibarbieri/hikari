#!/usr/bin/env bash
# Runs the full Hikari acceptance suite against the running stack.
#
# Steps are split into two groups:
#   scripts/  — operational steps that configure the platform
#   tests/    — verification steps that assert correctness
#
# Usage: bash deploy/local/run_acceptance.sh
# All steps are idempotent; re-running is safe.

set -uo pipefail

cd "$(dirname "$0")"

steps=(
  "tests/verify_artifact_hygiene.sh|artifact hygiene and terminology"
  "tests/smoke.sh --wait|wait for services if cold-started"
  "scripts/setup_ctfd.sh|run setup wizard"
  "scripts/ensure_admin.sh|ensure automation admin exists"
  "scripts/apply_theme.sh|apply Hikari design tokens"
  "scripts/apply_branding.sh|apply Hikari home page and footer"
  "tests/verify_branding.sh|home page and footer render Hikari branding"
  "tests/verify_oauth.sh|Google OAuth button hidden by default, /auth/google/login bounces with clear message"
  "tests/verify_public_pages.sh|public pages render without server errors"
  "tests/verify_plugin.sh|admin can reach Hikari plugin"
  "tests/verify_pipeline.sh|Kafka -> Elasticsearch data plane"
  "scripts/configure_siem.sh|default SIEM data view"
  "scripts/import_siem_dashboards.sh|import Kibana SIEM dashboard and set default route"
  "tests/verify_siem_dashboard.sh|Kibana SIEM dashboard saved objects and authenticated route"
  "tests/verify_activity.sh|activity logging captured in DB and ES"
  "tests/verify_siem_flow.sh|competitor SIEM access and query attribution"
  "tests/verify_kibana_classifier.sh|Kibana proxy extracts forensic facts (kind, indices, filters, time range)"
  "tests/verify_feedback.sh|local feedback captured and exported"
  "tests/verify_notifications.sh|admin notifications round-trip via REST and reach competitors"
  "tests/verify_isolation.sh|anonymous and non-admin actors are blocked from admin and research surfaces"
  "tests/verify_player_flow.sh|lone-wolf competitor: register, login, own one-person team, challenges"
  "tests/verify_team_flow.sh|team competitors: captain creates team, second member joins with team password"
  "tests/verify_challenge_flow.sh|admin creates challenge, player solves it, solve and activity recorded"
  "tests/verify_progressive_unlock.sh|solving one Hikari challenge activates dependent log data"
  "tests/verify_live_board.sh|live competition board renders standings and recent solves"
  "tests/verify_research.sh|researcher dashboard renders, JSONL export streams parseable records"
)

passed=()
failed=()

# CTFd rate-limits POSTs to /login and /register at 10 per 5 seconds per IP.
# Clear the counters before each step so tight-succession admin logins succeed.
clear_ratelimit_cache() {
  docker-compose exec -T cache redis-cli eval \
    "local k = redis.call('keys', 'flask_cache_rl:*'); if #k > 0 then return redis.call('del', unpack(k)) else return 0 end" \
    0 >/dev/null 2>&1 || true
}

for entry in "${steps[@]}"; do
  script="${entry%%|*}"
  label="${entry#*|}"
  echo
  echo "================================================================"
  echo "  $label"
  echo "  bash $script"
  echo "================================================================"
  clear_ratelimit_cache
  if bash $script; then
    passed+=("$script")
  else
    failed+=("$script")
    echo "FAILED: $script ($label)"
  fi
done

echo
echo "================================================================"
echo "  acceptance summary"
echo "================================================================"
printf '  passed: %d\n' "${#passed[@]}"
for name in "${passed[@]:-}"; do
  [[ -n "$name" ]] && printf '    - %s\n' "$name"
done
printf '  failed: %d\n' "${#failed[@]}"
for name in "${failed[@]:-}"; do
  [[ -n "$name" ]] && printf '    - %s\n' "$name"
done

if (( ${#failed[@]} > 0 )); then
  exit 1
fi
echo
echo "All acceptance checks passed."
