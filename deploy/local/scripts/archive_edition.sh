#!/usr/bin/env bash
# Closes one edition of the competition and prepares the installation for the
# next one.
#
# Three kinds of data share this installation and have different lifetimes:
#
#   challenge collection  challenges, flags and their log data   kept always
#   research record       activity and feedback, per edition     archived
#   identities and score  accounts, teams, submissions, solves   cleared
#
# Both modes report their work before changing data.

set -euo pipefail

umask 077

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

ARCHIVE_ROOT=${ARCHIVE_ROOT:-"$LOCAL_DIR/arquivo"}
# Every verification script names what it creates with an underscore and the
# epoch second it ran. A person registering never produces that suffix, and
# listing the matches before deleting keeps the judgement with the operator.
TEST_ACCOUNT_PATTERN='_1[0-9]{9}$'

mode=""
confirmed=0

usage() {
  cat <<'TXT'
Uso: bash scripts/archive_edition.sh <modo> [--confirmar]

Modos:
  --limpar-testes   Remove contas, equipes, submissões e desafios criados
                    pelos scripts de verificação, identificados pelo sufixo de
                    época no nome. Lista os nomes antes de apagar. Contas de
                    pessoas reais não são tocadas.

  --nova-edicao     Arquiva a edição atual (registro científico, acervo de
                    desafios e cópia do banco) e depois zera identidades,
                    equipes, submissões e placar para a próxima edição.
                    Os desafios e as contas administrativas permanecem.

Sem --confirmar o script apenas relata o que faria.
TXT
}

fail() {
  echo "ERRO: $*" >&2
  exit 1
}

sql() {
  hikari_mariadb -N -e "$1"
}

count() {
  sql "SELECT COUNT(*) FROM $1;" | tr -d '[:space:]'
}

require_no_open_competition() {
  local open_run_count
  open_run_count=$(sql "SELECT COUNT(*) FROM hikari_competition_runs
                 WHERE status IN ('scheduled','running','paused');" | tr -d '[:space:]')
  [[ "$open_run_count" == "0" ]] \
    || fail "há uma execução agendada, em andamento ou pausada. Encerre-a em /admin/hikari/competitions antes de continuar."
}

report_test_data() {
  echo "Contas e equipes criadas por scripts de verificação:"
  sql "SELECT CONCAT('  contas de teste .......... ', COUNT(*)) FROM users
        WHERE name REGEXP '$TEST_ACCOUNT_PATTERN';
       SELECT CONCAT('  equipes de teste ......... ', COUNT(*)) FROM teams
        WHERE name REGEXP '$TEST_ACCOUNT_PATTERN';
       SELECT CONCAT('  submissões dessas contas . ', COUNT(*)) FROM submissions s
        JOIN users u ON u.id = s.user_id WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       SELECT CONCAT('  eventos de atividade ..... ', COUNT(*)) FROM hikari_activity
        WHERE competition_key REGEXP '^(acceptance|simulacao|ensaio)-';
       SELECT CONCAT('  eventos de contas teste .. ', COUNT(*)) FROM hikari_activity a
        JOIN users u ON u.id = a.actor_id WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       SELECT CONCAT('  desafios de teste ........ ', COUNT(*))
        FROM hikari_challenge_library_entries e
        JOIN hikari_challenge_library_imports i ON i.id = e.library_import_id
        WHERE i.package_key LIKE 'acceptance-library-%';"
  echo
  echo "Contas fora do padrão de verificação:"
  sql "SELECT CONCAT('  contas de pessoas reais .. ', COUNT(*)) FROM users
        WHERE type = 'user' AND name NOT REGEXP '$TEST_ACCOUNT_PATTERN';
       SELECT CONCAT('  submissões dessas contas . ', COUNT(*)) FROM submissions s
        JOIN users u ON u.id = s.user_id WHERE u.name NOT REGEXP '$TEST_ACCOUNT_PATTERN';"
}

# Deleting accounts is irreversible, so the operator sees the actual names
# before confirming rather than a count they have to trust.
list_test_accounts() {
  local names
  names=$(sql "SELECT name FROM users WHERE name REGEXP '$TEST_ACCOUNT_PATTERN'
               ORDER BY name;" | tr -d '\r')
  [[ -n "$names" ]] || return 0
  echo
  echo "Contas que serão removidas:"
  printf '  %s\n' $names
}

report_edition_data() {
  echo "Serão arquivados e depois removidos:"
  printf '  contas (exceto administradores) . %s\n' \
    "$(sql "SELECT COUNT(*) FROM users WHERE type <> 'admin';" | tr -d '[:space:]')"
  printf '  equipes ......................... %s\n' "$(count teams)"
  printf '  submissões ...................... %s\n' "$(count submissions)"
  printf '  acertos ......................... %s\n' "$(count solves)"
  printf '  eventos de atividade ............ %s\n' "$(count hikari_activity)"
  printf '  respostas de feedback ........... %s\n' "$(count hikari_feedback_responses)"
  echo
  echo "Permanecem na instalação:"
  printf '  desafios ........................ %s\n' "$(count challenges)"
  printf '  flags ........................... %s\n' "$(count flags)"
  printf '  administradores ................. %s\n' \
    "$(sql "SELECT COUNT(*) FROM users WHERE type = 'admin';" | tr -d '[:space:]')"
}

# Each export names the one thing it writes. Two constraints shape all three:
# the CTFd imports need an application context while they are imported, so they
# sit inside it, and the plugin loader writes to stdout while the app is built,
# which would otherwise land in the middle of the exported data.
export_activity() {
  hikari_compose exec -T ctfd python - <<'PY' > "$1"
import contextlib
import sys

from CTFd import create_app

with contextlib.redirect_stdout(sys.stderr):
    app = create_app()

with app.app_context():
    from CTFd.plugins.hikari_plugin.hikari_research.dto import ResearchFilters
    from CTFd.plugins.hikari_plugin.hikari_research.exporter import jsonl_lines

    for line in jsonl_lines(ResearchFilters()):
        sys.stdout.write(line)
PY
}

export_feedback() {
  hikari_compose exec -T ctfd python - <<'PY' > "$1"
import contextlib
import sys

from CTFd import create_app

with contextlib.redirect_stdout(sys.stderr):
    app = create_app()

with app.app_context():
    from CTFd.plugins.hikari_plugin.hikari_feedback.views import feedback_jsonl_lines

    for line in feedback_jsonl_lines():
        sys.stdout.write(line)
PY
}

export_challenge_collection() {
  hikari_compose exec -T ctfd python - <<'PY' > "$1"
import contextlib
import sys

from CTFd import create_app

with contextlib.redirect_stdout(sys.stderr):
    app = create_app()

with app.app_context():
    from CTFd.plugins.hikari_plugin.hikari_challenge_library.exporter import export_library

    sys.stdout.buffer.write(export_library("acervo", "Acervo de desafios"))
PY
}

dump_database() {
  hikari_mariadb_dump > "$1"
}

# The order is the contract: everything is written before anything is removed.
archive_edition() {
  local destination=$1
  mkdir "$destination"

  echo "Exportando o registro científico..."
  export_activity "$destination/atividade.jsonl"
  export_feedback "$destination/feedback.jsonl"

  echo "Exportando o acervo de desafios..."
  export_challenge_collection "$destination/acervo-desafios.zip"

  echo "Copiando o banco de dados..."
  dump_database "$destination/banco.sql"

  write_manifest "$destination" "$(exported_challenge_count "$destination/acervo-desafios.zip")"
}

exported_challenge_count() {
  unzip -p "$1" manifest.json | jq '.challenges | length'
}

write_manifest() {
  local destination=$1
  local challenge_count=$2
  cat > "$destination/MANIFESTO.md" <<TXT
# Edição arquivada

Gerado em $(date '+%d/%m/%Y %H:%M:%S').

| Conteúdo | Arquivo | Registros |
| --- | --- | --- |
| Atividade dos competidores | \`atividade.jsonl\` | $(wc -l < "$destination/atividade.jsonl" | tr -d ' ') |
| Respostas de feedback | \`feedback.jsonl\` | $(wc -l < "$destination/feedback.jsonl" | tr -d ' ') |
| Acervo de desafios | \`acervo-desafios.zip\` | $challenge_count desafios exportados |
| Cópia completa do banco | \`banco.sql\` | $(count users) contas, $(count submissions) submissões |

Para reabrir esta edição, suba um projeto Compose próprio e restaure
\`banco.sql\` nele. O procedimento está em \`docs/OPERATIONS.md\`, seção 7.

Para reaproveitar os desafios numa nova edição, importe \`acervo-desafios.zip\`
em \`/admin/hikari/challenge-library\`.
TXT
}

purge_test_data() {
  sql "DELETE s FROM submissions s JOIN users u ON u.id = s.user_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE sv FROM solves sv JOIN users u ON u.id = sv.user_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE a FROM awards a JOIN users u ON u.id = a.user_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE un FROM unlocks un JOIN users u ON u.id = un.user_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE t FROM tracking t JOIN users u ON u.id = t.user_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE r FROM hikari_team_membership_requests r JOIN users u ON u.id = r.user_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE f FROM hikari_feedback_responses f JOIN users u ON u.id = f.user_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE FROM hikari_activity WHERE competition_key REGEXP '^(acceptance|simulacao|ensaio)-';
       -- A rehearsal run inside the real competition records its telemetry under
       -- the real key, so the actor is what identifies it as test data. This has
       -- to precede the account removal, while the join still resolves.
       DELETE a FROM hikari_activity a JOIN users u ON u.id = a.actor_id
        WHERE u.name REGEXP '$TEST_ACCOUNT_PATTERN';
       UPDATE users SET team_id = NULL WHERE name REGEXP '$TEST_ACCOUNT_PATTERN';
       UPDATE teams SET captain_id = NULL WHERE name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE FROM users WHERE name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE FROM teams WHERE name REGEXP '$TEST_ACCOUNT_PATTERN';
       DELETE FROM hikari_competition_runs WHERE \`key\` REGEXP '^(acceptance|simulacao|ensaio)-';"
  purge_test_challenges
}

purge_test_challenges() {
  local ids
  ids=$(sql "SELECT GROUP_CONCAT(e.challenge_id) FROM hikari_challenge_library_entries e
             JOIN hikari_challenge_library_imports i ON i.id = e.library_import_id
             WHERE i.package_key LIKE 'acceptance-library-%';" | tr -d '[:space:]')
  [[ -n "$ids" && "$ids" != "NULL" ]] || return 0

  sql "DELETE FROM challenge_topics WHERE challenge_id IN ($ids);
       DELETE FROM comments WHERE challenge_id IN ($ids);
       DELETE FROM files WHERE challenge_id IN ($ids);
       DELETE FROM flags WHERE challenge_id IN ($ids);
       DELETE FROM hints WHERE challenge_id IN ($ids);
       DELETE FROM solves WHERE challenge_id IN ($ids);
       DELETE FROM submissions WHERE challenge_id IN ($ids);
       DELETE FROM tags WHERE challenge_id IN ($ids);
       DELETE FROM hikari_challenge_library_entries WHERE challenge_id IN ($ids);
       DELETE FROM challenges WHERE id IN ($ids);
       DELETE FROM hikari_challenge_library_imports
        WHERE package_key LIKE 'acceptance-library-%';"
}

reset_identities() {
  sql "START TRANSACTION;
       DELETE FROM submissions;
       DELETE FROM solves;
       DELETE FROM awards;
       DELETE FROM unlocks;
       DELETE FROM tracking;
       DELETE FROM hikari_team_membership_requests;
       DELETE FROM hikari_feedback_responses;
       DELETE FROM hikari_activity;
       DELETE FROM notifications;
       UPDATE users SET team_id = NULL;
       UPDATE teams SET captain_id = NULL;
       DELETE FROM users WHERE type <> 'admin';
       DELETE FROM teams;
       DELETE FROM hikari_competition_runs;
       COMMIT;"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limpar-testes|--nova-edicao) mode="$1" ;;
    --confirmar) confirmed=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; fail "argumento desconhecido: $1" ;;
  esac
  shift
done

[[ -n "$mode" ]] || { usage; exit 2; }

require_no_open_competition

case "$mode" in
  --limpar-testes)
    report_test_data
    list_test_accounts
    if [[ $confirmed -eq 0 ]]; then
      echo
      echo "Nada foi alterado. Repita com --confirmar para aplicar."
      exit 0
    fi
    echo
    echo "Removendo os dados de teste..."
    purge_test_data
    echo "Instalação sem resíduo de verificação."
    ;;

  --nova-edicao)
    report_edition_data
    if [[ $confirmed -eq 0 ]]; then
      echo
      echo "Nada foi alterado. Repita com --confirmar para arquivar e zerar."
      exit 0
    fi
    mkdir -p "$ARCHIVE_ROOT"
    destination="$ARCHIVE_ROOT/$(date '+%Y-%m-%d-%H%M%S')"
    echo
    echo "Arquivando em $destination"
    archive_edition "$destination"
    echo
    echo "Arquivo concluído. Zerando identidades e placar..."
    reset_identities
    bash "$SCRIPT_DIR/reset_competition_state.sh"
    echo
    echo "Instalação pronta para uma nova edição."
    echo "Edição anterior preservada em $destination"
    ;;
esac
