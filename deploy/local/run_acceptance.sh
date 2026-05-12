#!/usr/bin/env bash
# Single command that takes a reviewer from a clean checkout to a verified
# stack. Each step is one of the existing focused scripts; this file only
# orchestrates them and prints a final summary so the reviewer does not have
# to remember the order or stitch outputs together.

set -uo pipefail

cd "$(dirname "$0")"

steps=(
  "verify_artifact_hygiene.sh|artifact hygiene and terminology"
  "smoke.sh --wait|wait for services if cold-started"
  "setup_ctfd.sh|run setup wizard"
  "ensure_admin.sh|ensure automation admin exists"
  "apply_theme.sh|apply Hikari design tokens"
  "apply_branding.sh|apply Hikari home page and footer"
  "verify_branding.sh|home page and footer render Hikari branding"
  "verify_plugin.sh|admin can reach Hikari plugin"
  "verify_pipeline.sh|Kafka -> Elasticsearch data plane"
  "configure_siem.sh|default SIEM data view"
  "verify_activity.sh|activity logging captured in DB and ES"
  "verify_siem_flow.sh|competitor SIEM access and query attribution"
  "verify_kibana_classifier.sh|Kibana proxy extracts forensic facts (kind, indices, filters, time range)"
  "verify_feedback.sh|local feedback captured and exported"
  "verify_player_flow.sh|lone-wolf competitor: register, login, own one-person team, challenges"
  "verify_team_flow.sh|team competitors: captain creates team, second member joins with team password"
  "verify_challenge_flow.sh|admin creates challenge, player solves it, solve and activity recorded"
  "verify_progressive_unlock.sh|solving one Hikari challenge activates dependent log data"
  "verify_research.sh|researcher dashboard renders, JSONL export streams parseable records"
)

passed=()
failed=()

# CTFd rate-limits POSTs to /login and /register at 10 per 5 seconds per IP.
# The suite issues many admin logins in tight succession, so clear the
# ratelimit counters before each step. The keys are namespaced under "rl:".
clear_ratelimit_cache() {
  # Flask-Caching prefixes every key with "flask_cache_", so the rate-limit
  # entries CTFd writes appear under "flask_cache_rl:*", not "rl:*".
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
