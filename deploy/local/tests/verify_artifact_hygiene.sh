#!/usr/bin/env bash
# Checks the Hikari-owned artifact files for terms and files that should not
# be shipped in the reproducible package.

set -euo pipefail

cd "$(dirname "$0")/../../.."

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

tracked_files=$(git ls-files | while IFS= read -r path; do
  [[ -e "$path" ]] && printf '%s\n' "$path"
done)

# Terminology and style apply to a file from the moment it is written, not from
# the moment it is committed. Scanning only tracked files let a brand new file
# through in exactly the window where it is most likely to carry a mistake.
# Ignored paths stay out: they never reach the artifact.
reviewable_files=$(git ls-files --cached --others --exclude-standard \
  | while IFS= read -r path; do
      [[ -e "$path" ]] && printf '%s\n' "$path"
    done)

generated_patterns='(^|/)(\.DS_Store|\.env)$|^deploy/local/artifacts/|^(lab|detectionlab)/|data_backup\.zip|(^|/)__pycache__/|\.pyc$'
generated_hits=$(printf '%s\n' "$tracked_files" | grep -E "$generated_patterns" || true)
[[ -z "$generated_hits" ]] || fail "generated or local-only files are tracked:
$generated_hits"
echo "PASS: no generated runtime files are tracked"

hikari_files=$(printf '%s\n' "$reviewable_files" | grep -E \
  '^(README.md|SECURITY.md|Makefile|docs/|deploy/(local|production)/|ctfd/HIKARI.md|ctfd/CTFd/plugins/hikari_|ctfd/CTFd/plugins/hikari_plugin|ctfd/CTFd/themes/hikari-theme/templates/)' || true)

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
  "not ""only"
  "but ""also"
  "does ""not"
  "cur""rent limits"
  "compre""hensive"
  "sea""mless"
  "ro""bust"
  "cutting-""edge"
  "util""ize"
  "leve""rage"
  "Chat""GPT"
  "Cla""ude"
  "Co""dex"
  "\\bLL""M\\b"
  "\\bA""I\\b"
  $'\U0001F680'
  $'\U0001F389'
  $'\U00002728'
)
forbidden_terms=$(IFS='|'; echo "${restricted_terms[*]}")
# Terminology is a property of text. Screenshots and other binaries would
# otherwise match on arbitrary byte sequences.
scannable_files=$(printf '%s\n' "$hikari_files" | grep -vE '\.(png|jpg|jpeg|gif|webp|ico|pdf|zip|mp4|woff2?)$')

run_scan() {
  local paths=$1
  local expression=$2
  local scan_result
  local scan_status

  set +e
  scan_result=$(printf '%s\n' "$paths" | xargs rg -n "$expression")
  scan_status=$?
  set -e
  [[ $scan_status -le 1 ]] || fail "scan failed to run (rg exit $scan_status)"
  printf '%s' "$scan_result"
}

term_hits=$(run_scan "$scannable_files" "$forbidden_terms")
[[ -z "$term_hits" ]] || fail "forbidden terms found in Hikari-owned files:
$term_hits"
echo "PASS: naming and style scan is clean"

personal_default_hits=$(run_scan "$scannable_files" 'sidneibarbieri@gmail\\.com')
[[ -z "$personal_default_hits" ]] || fail "personal account data remains in the artifact:\n$personal_default_hits"
echo "PASS: no personal account is seeded by default"

exception_pattern="except ""Exception|\\bprint\\("
# The rule targets application code, where progress belongs in a log rather
# than on stdout. A script an operator runs by hand reports to the terminal by
# design, and it declares itself with a main guard, so name the category
# instead of listing files one by one.
operator_tools=$(printf '%s\n' "$scannable_files" \
  | grep -E '\.py$' \
  | while IFS= read -r path; do
      grep -q '^if __name__ == "__main__":' "$path" && printf '%s\n' "$path"
    done)
exception_files=$(printf '%s\n' "$scannable_files" \
  | grep -E '\.(py|sh)$' \
  | grep -vxF "${operator_tools:-__sem_correspondencia__}")
exception_hits=$(run_scan "$exception_files" "$exception_pattern")
if [[ -n "$exception_hits" ]]; then
  fail "broad exception or print usage remains in Hikari-owned files:
$exception_hits"
else
  echo "PASS: no broad exception or print usage in Hikari-owned files"
fi

echo
echo "Artifact hygiene verified."
