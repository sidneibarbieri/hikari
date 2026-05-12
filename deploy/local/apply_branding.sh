#!/usr/bin/env bash
# Applies Hikari branding on top of the CTFd defaults:
#   * rewrites the index page so the CTFd hero and social icons are gone
#   * sets theme_footer to hide the upstream "Powered by CTFd" footer and
#     render a short Hikari footer in its place
# Idempotent: re-running with no changes is a no-op.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}

INDEX_CONTENT='<div class="hikari-landing">
  <div class="hikari-hero">
    <h1 class="hikari-wordmark">Hikari</h1>
    <p class="hikari-eyebrow">Threat-hunting training and research</p>
    <p class="hikari-tagline">
      A gamified lab where blue-team analysts practise hunting through
      live log streams, and where every action is captured for
      reproducible study.
    </p>
    <div class="hikari-actions">
      <a class="btn btn-primary" href="/challenges">Challenges</a>
      <a class="btn btn-outline-primary" href="/hikari/siem">SIEM</a>
      <a class="btn btn-outline-primary" href="/feedback">Feedback</a>
    </div>
  </div>
</div>'

FEEDBACK_CONTENT='<section class="hikari-landing">
  <div class="hikari-hero">
    <p class="hikari-eyebrow">Research feedback</p>
    <h1 class="hikari-wordmark">Feedback</h1>
    <p class="hikari-tagline">
      The questionnaire is hosted inside Hikari so responses stay attached
      to the exercise, participant account, and team context.
    </p>
    <div class="hikari-actions">
      <a class="btn btn-primary" href="/hikari/feedback">Open questionnaire</a>
    </div>
  </div>
</section>'

THEME_FOOTER='<style>
footer.footer { display: none; }
.hikari-footer {
  padding: 1.25rem 1rem;
  text-align: center;
  color: var(--hikari-text-muted);
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  border-top: 1px solid var(--hikari-border);
}
.hikari-footer strong { color: var(--hikari-text); font-weight: 600; }
</style>
<div class="hikari-footer">
  <strong>Hikari</strong> &middot; threat-hunting training platform &middot; built on CTFd
</div>'

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar" /tmp/hikari-brand-*' EXIT

page=/tmp/hikari-brand-login.html
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" "$CTFD_URL/login"
nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$page" \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "admin login returned $code"; exit 1; }

page=/tmp/hikari-brand-admin.html
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" -L "$CTFD_URL/admin"
csrf=$(grep -oE "'csrfNonce':[[:space:]]*\"[^\"]+\"" "$page" \
  | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
[[ -n "$csrf" ]] || { echo "no CSRF nonce"; exit 1; }

# Find the existing index page (route == 'index').
pages=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" "$CTFD_URL/api/v1/pages")
index_id=$(echo "$pages" | jq -r '.data[] | select(.route=="index") | .id' | head -1)
[[ -n "$index_id" ]] \
  || { echo "could not find index page; setup wizard not yet run?"; exit 1; }

current=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  "$CTFD_URL/api/v1/pages/$index_id" | jq -r '.data.content // ""')

if [[ "$current" != "$INDEX_CONTENT" ]]; then
  response=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
    -X PATCH "$CTFD_URL/api/v1/pages/$index_id" \
    -d "$(jq -cn --arg c "$INDEX_CONTENT" \
      '{title:"Hikari",route:"index",content:$c,format:"html",draft:false,hidden:false,auth_required:false}')")
  success=$(echo "$response" | jq -r '.success')
  [[ "$success" == "true" ]] \
    || { echo "FAIL: page patch returned $response"; exit 1; }
  echo "index page updated"
else
  echo "index page already up to date"
fi

feedback_id=$(echo "$pages" | jq -r '.data[] | select(.route=="feedback") | .id' | head -1)
if [[ -n "$feedback_id" ]]; then
  current_feedback=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
    "$CTFD_URL/api/v1/pages/$feedback_id" | jq -r '.data.content // ""')
  if [[ "$current_feedback" != "$FEEDBACK_CONTENT" ]]; then
    response=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
      -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
      -X PATCH "$CTFD_URL/api/v1/pages/$feedback_id" \
      -d "$(jq -cn --arg c "$FEEDBACK_CONTENT" \
        '{title:"Feedback",route:"feedback",content:$c,format:"html",draft:false,hidden:false,auth_required:false}')")
    success=$(echo "$response" | jq -r '.success')
    [[ "$success" == "true" ]] \
      || { echo "FAIL: feedback page patch returned $response"; exit 1; }
    echo "feedback page updated"
  else
    echo "feedback page already up to date"
  fi
else
  response=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
    -X POST "$CTFD_URL/api/v1/pages" \
    -d "$(jq -cn --arg c "$FEEDBACK_CONTENT" \
      '{title:"Feedback",route:"feedback",content:$c,format:"html",draft:false,hidden:false,auth_required:false}')")
  success=$(echo "$response" | jq -r '.success')
  [[ "$success" == "true" ]] \
    || { echo "FAIL: feedback page create returned $response"; exit 1; }
  echo "feedback page created"
fi

# theme_footer config — same idempotency dance as theme_header.
current_footer=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  "$CTFD_URL/api/v1/configs/theme_footer" | jq -r '.data.value // ""')

if [[ "$current_footer" != "$THEME_FOOTER" ]]; then
  if [[ -z "$current_footer" ]]; then
    response=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
      -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
      -X POST "$CTFD_URL/api/v1/configs" \
      -d "$(jq -cn --arg v "$THEME_FOOTER" '{key:"theme_footer",value:$v}')")
  else
    response=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
      -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
      -X PATCH "$CTFD_URL/api/v1/configs/theme_footer" \
      -d "$(jq -cn --arg v "$THEME_FOOTER" '{value:$v}')")
  fi
  success=$(echo "$response" | jq -r '.success')
  [[ "$success" == "true" ]] \
    || { echo "FAIL: theme_footer update returned $response"; exit 1; }
  echo "theme_footer updated"
else
  echo "theme_footer already up to date"
fi

echo "branding applied"
