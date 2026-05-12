#!/usr/bin/env bash
# Checks the Hikari-owned artifact files for terms and files that should not
# be shipped in the reproducible package.

set -euo pipefail

cd "$(dirname "$0")/../.."

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

tracked_files=$(git ls-files)

generated_patterns='(^|/)(\.DS_Store|\.env)$|^deploy/local/artifacts/|data_backup\.zip|(^|/)__pycache__/|\.pyc$'
generated_hits=$(printf '%s\n' "$tracked_files" | grep -E "$generated_patterns" || true)
[[ -z "$generated_hits" ]] || fail "generated or local-only files are tracked:
$generated_hits"
echo "PASS: no generated runtime files are tracked"

hikari_files=$(printf '%s\n' "$tracked_files" | grep -E \
  '^(README.md|docs/|deploy/local/|ctfd/HIKARI.md|ctfd/CTFd/plugins/hikari_|ctfd/CTFd/plugins/hikari_plugin|ctfd/CTFd/themes/hikari-theme/templates/)' || true)

[[ -n "$hikari_files" ]] || fail "no Hikari-owned files found for hygiene scan"

restricted_terms=(
  "USE""NIX"
  "ND""SS"
  "ACM ""CCS"
  "IEEE ""S&P"
  "SIG""COMM"
  "Co""NEXT"
  "Euro""Sys"
  "SB""RC"
  "SB""Seg"
  "Sa""lão"
  "Trilha ""Principal"
  "top""-4"
  "TOP ""4"
  "Best ""Paper"
  "world""-class"
  "pre""mium"
  "su""preme"
  "Su""premo"
  "vend""ável"
  "extra""ordinary"
  "Per""fect"
  "Excel""lent"
  "Let ""me"
  $'\U0001F680'
  $'\U0001F389'
  $'\U00002728'
)
forbidden_terms=$(IFS='|'; echo "${restricted_terms[*]}")
term_hits=$(printf '%s\n' "$hikari_files" | xargs rg -n "$forbidden_terms" || true)
[[ -z "$term_hits" ]] || fail "forbidden terms found in Hikari-owned files:
$term_hits"
echo "PASS: naming and style scan is clean"

exception_pattern="except ""Exception|\\bprint\\("
exception_hits=$(printf '%s\n' "$hikari_files" | xargs rg -n "$exception_pattern" || true)
if [[ -n "$exception_hits" ]]; then
  echo "WARN: broad exception or print usage remains in Hikari-owned files:"
  echo "$exception_hits"
else
  echo "PASS: no broad exception or print usage in Hikari-owned files"
fi

echo
echo "Artifact hygiene verified."
