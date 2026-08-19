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

# Um número fixo seria arbitrário: duas linhas de investigação podem somar dez
# desafios com toda a coerência. O que estraga a leitura é a categoria que
# engole a edição, e isso se mede em proporção, não em contagem.
FRACAO_MAXIMA=${FRACAO_MAXIMA:-3}

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
echo "== 2. nenhuma categoria engole a edição =="
teto=$(( total / FRACAO_MAXIMA ))
largas=$(consulta "SELECT COUNT(*) FROM (SELECT category FROM challenges WHERE state='visible'
                    GROUP BY category HAVING COUNT(*) > $teto) AS d;")
if [[ "$largas" != "0" ]]; then
  reprovar "$largas categoria(s) passam de $teto desafios, um terço da edição"
  consulta "SELECT CONCAT('  ', category, ': ', COUNT(*)) FROM challenges WHERE state='visible'
             GROUP BY category HAVING COUNT(*) > $teto;"
else
  categorias=$(consulta "SELECT COUNT(DISTINCT category) FROM challenges WHERE state='visible';")
  maior=$(consulta "SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM challenges WHERE state='visible'
                     GROUP BY category) AS d;")
  echo "PASS: $categorias categorias, a maior com $maior de um teto de $teto"
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
echo "== 6. nenhum texto entrega a própria resposta =="
# Um título que contém a flag transforma o desafio em leitura. Vale para a
# descrição e para a dica, que também são lidas antes de qualquer busca.
vazamentos=$(hikari_compose exec -T -w /opt/CTFd -e PYTHONPATH=/opt/CTFd ctfd python - <<'PY' 2>/dev/null | tail -1
import unicodedata
from CTFd import create_app

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))

app = create_app()
with app.app_context():
    from CTFd.models import Challenges, Flags, Hints
    vazando = 0
    for desafio in Challenges.query.filter_by(state="visible").all():
        for flag in Flags.query.filter_by(challenge_id=desafio.id).all():
            valor = (flag.content or "")
            if valor.startswith("flag{") and valor.endswith("}"):
                valor = valor[5:-1]
            if len(valor) < 4:
                continue
            alvo = normalizar(valor)
            textos = [desafio.name, desafio.description]
            textos += [h.content for h in Hints.query.filter_by(challenge_id=desafio.id).all()]
            if any(alvo in normalizar(texto) for texto in textos):
                vazando += 1
    print(vazando)
PY
)
if [[ "$vazamentos" == "0" ]]; then
  echo "PASS: nenhum título, descrição ou dica contém a própria flag"
else
  reprovar "$vazamentos desafio(s) entregam a resposta no próprio texto"
fi

echo
echo "== 7. a dificuldade chega ao competidor =="
sem_tag=$(consulta "SELECT COUNT(*) FROM challenges c WHERE c.state='visible'
                     AND NOT EXISTS (SELECT 1 FROM tags t WHERE t.challenge_id = c.id);")
if [[ "$sem_tag" == "0" ]]; then
  niveis=$(consulta "SELECT GROUP_CONCAT(DISTINCT t.value ORDER BY t.value SEPARATOR ', ')
                       FROM tags t JOIN challenges c ON c.id = t.challenge_id WHERE c.state='visible';")
  echo "PASS: todos os $total desafios anunciam a dificuldade ($niveis)"
else
  echo "  aviso: $sem_tag desafio(s) sem dificuldade anunciada"
fi

echo
echo "== 8. o jogo inteiro pode ser terminado =="
# Um grafo sem laço e sem órfão ainda pode prender um desafio atrás de algo
# que ninguém alcança. A única prova é jogar no papel, onda a onda.
saida=$(hikari_compose exec -T -w /opt/CTFd -e PYTHONPATH=/opt/CTFd ctfd \
  python /tmp/simular.py 2>/dev/null || true)
if grep -q "todos os desafios são alcançáveis" <<<"$saida"; then
  echo "PASS: $(grep -oE 'ondas até o fim [. ]+[0-9]+' <<<"$saida" | grep -oE '[0-9]+$') ondas até o último desafio"
else
  reprovar "há desafio que nunca abre: $(grep 'NUNCA ABREM' <<<"$saida")"
fi

echo
if [[ "$falhou" == "0" ]]; then
  echo "Curadoria verificada."
else
  echo "Curadoria reprovada."
  exit 1
fi
