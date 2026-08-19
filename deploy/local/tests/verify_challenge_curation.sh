#!/usr/bin/env bash
# Holds the challenge collection to the rules that make it readable.
#
# The collection reached the eve of an event with twenty-five challenges under
# one category, eight titles repeated across fifty-one challenges, and every
# hint written into the description where it was free. None of that is visible
# from the code; it only shows on the screen a competitor opens. These are the
# rules, checked against whatever the installation actually holds.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

# A category wide enough to hold a quarter of the event is a list, not a
# category; one that holds a single challenge is a label.
MAXIMO_POR_CATEGORIA=${MAXIMO_POR_CATEGORIA:-10}

consulta() { hikari_mariadb -N -B -e "$1" | tr -d '\r'; }

falhou=0
reprovar() { echo "FAIL: $*"; falhou=1; }

total=$(consulta "SELECT COUNT(*) FROM challenges WHERE state = 'visible';")
if [[ "$total" == "0" ]]; then
  echo "Nenhum desafio visível: nada a curar."
  exit 0
fi

echo "== 1. cada título nomeia um desafio =="
repetidos=$(consulta "SELECT COUNT(*) FROM (SELECT name FROM challenges WHERE state='visible'
                       GROUP BY name HAVING COUNT(*) > 1) AS d;")
if [[ "$repetidos" != "0" ]]; then
  reprovar "$repetidos título(s) usados por mais de um desafio"
  consulta "SELECT CONCAT('  ', name, ' (', COUNT(*), 'x)') FROM challenges
             WHERE state='visible' GROUP BY name HAVING COUNT(*) > 1;"
else
  echo "PASS: $total desafios, $total títulos distintos"
fi

echo
echo "== 2. nenhuma categoria vira um blocão =="
largas=$(consulta "SELECT COUNT(*) FROM (SELECT category FROM challenges WHERE state='visible'
                    GROUP BY category HAVING COUNT(*) > $MAXIMO_POR_CATEGORIA) AS d;")
if [[ "$largas" != "0" ]]; then
  reprovar "$largas categoria(s) com mais de $MAXIMO_POR_CATEGORIA desafios"
  consulta "SELECT CONCAT('  ', category, ': ', COUNT(*)) FROM challenges WHERE state='visible'
             GROUP BY category HAVING COUNT(*) > $MAXIMO_POR_CATEGORIA;"
else
  categorias=$(consulta "SELECT COUNT(DISTINCT category) FROM challenges WHERE state='visible';")
  maior=$(consulta "SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM challenges WHERE state='visible'
                     GROUP BY category) AS d;")
  echo "PASS: $categorias categorias, a maior com $maior desafios"
fi

echo
echo "== 3. toda dica custa pontos =="
sem_dica=$(consulta "SELECT COUNT(*) FROM challenges c WHERE c.state='visible'
                      AND NOT EXISTS (SELECT 1 FROM hints h WHERE h.challenge_id = c.id);")
gratis=$(consulta "SELECT COUNT(*) FROM hints h JOIN challenges c ON c.id = h.challenge_id
                    WHERE c.state='visible' AND (h.cost IS NULL OR h.cost <= 0);")
na_descricao=$(consulta "SELECT COUNT(*) FROM challenges WHERE state='visible' AND description LIKE '%Dica:%';")

[[ "$na_descricao" == "0" ]] \
  || reprovar "$na_descricao descrição(ões) ainda carregam a dica, onde ela é grátis"
[[ "$gratis" == "0" ]] || reprovar "$gratis dica(s) sem custo em pontos"
if [[ "$sem_dica" != "0" ]]; then
  echo "  aviso: $sem_dica desafio(s) sem dica cadastrada"
fi
[[ "$na_descricao" == "0" && "$gratis" == "0" ]] \
  && echo "PASS: nenhuma dica grátis e nenhuma escondida na descrição"

echo
echo "== 4. as categorias vêm do vocabulário declarado =="
# Nomear categorias por gosto deixa a coleção sem apoio nenhum. O vocabulário
# vem das táticas do MITRE ATT&CK, com uma exceção declarada para as tarefas
# de analista que não são movimento de adversário.
vocabulario=$(python3 -c "
import sys; sys.path.insert(0, '$LOCAL_DIR/scripts')
from attack_taxonomy import VOCABULARIO
print('|'.join(VOCABULARIO))
")
fora=$(consulta "SELECT COUNT(*) FROM (SELECT DISTINCT category FROM challenges
                  WHERE state='visible') AS d;")
conhecidas=0
while IFS= read -r nome; do
  [[ -z "$nome" ]] && continue
  case "|$vocabulario|" in
    *"|$nome|"*) conhecidas=$((conhecidas + 1)) ;;
    *) reprovar "categoria fora do vocabulário: $nome" ;;
  esac
done < <(consulta "SELECT DISTINCT category FROM challenges WHERE state='visible';")
[[ "$conhecidas" == "$fora" ]] \
  && echo "PASS: as $fora categorias pertencem ao vocabulário do ATT&CK"

echo
echo "== 5. todo desafio tem resposta =="
sem_flag=$(consulta "SELECT COUNT(*) FROM challenges c WHERE c.state='visible'
                      AND NOT EXISTS (SELECT 1 FROM flags f WHERE f.challenge_id = c.id);")
[[ "$sem_flag" == "0" ]] && echo "PASS: todos os $total desafios têm flag" \
  || reprovar "$sem_flag desafio(s) sem flag"

echo
if [[ "$falhou" == "0" ]]; then
  echo "Curadoria verificada."
else
  echo "Curadoria reprovada."
  exit 1
fi
