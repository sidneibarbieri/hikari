#!/usr/bin/env bash
# Single command that takes a reviewer from a clean checkout to a verified
# stack. Each step is one of the existing focused scripts; this file only
# orchestrates them and prints a final summary so the reviewer does not have
# to remember the order or stitch outputs together.

set -uo pipefail

cd "$(dirname "$0")"

steps=(
  "smoke.sh|stack health"
  "smoke.sh --wait|wait for services if cold-started"
  "setup_ctfd.sh|run setup wizard"
  "apply_theme.sh|apply Hikari design tokens"
  "verify_plugin.sh|admin can reach Hikari plugin"
  "verify_pipeline.sh|Kafka -> Elasticsearch data plane"
  "verify_activity.sh|activity logging captured in DB and ES"
  "verify_player_flow.sh|competitor: register, login, team, challenges"
  "verify_team_flow.sh|two users sharing a team"
  "verify_challenge_flow.sh|admin creates challenge, player solves it"
)

passed=()
failed=()

for entry in "${steps[@]}"; do
  script="${entry%%|*}"
  label="${entry#*|}"
  echo
  echo "================================================================"
  echo "  $label"
  echo "  bash $script"
  echo "================================================================"
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
