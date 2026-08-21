"""Resolve os desafios de credenciais do mesmo jeito que o competidor resolveria.

Aqui a conferência não é uma agregação no índice: é refazer o raciocínio. O
script localiza o registro da conta no log convertido, aplica a operação que o
enunciado pede e compara com a flag. Um desafio que pede o nome de um algoritmo
é conferido pelo comprimento da assinatura; um que pede uma senha é conferido
recalculando o resumo e comparando com o que está gravado.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

CONSTANTE = "reseg26!"


def registros_por_conta(caminho: Path) -> Dict[str, List[str]]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    eventos = dados["eventos"] if isinstance(dados, dict) else dados
    por_conta: Dict[str, List[str]] = {}
    for evento in eventos:
        conta = evento.get("user.email")
        if conta:
            por_conta.setdefault(conta, []).append(evento["credential.hash"])
    return por_conta


def hexadecimal_de(assinaturas: List[str], comprimento: int) -> Optional[str]:
    """A assinatura hexadecimal do comprimento pedido, quando a conta tem mais de uma."""
    for assinatura in assinaturas:
        if len(assinatura) == comprimento and all(c in "0123456789abcdef" for c in assinatura.lower()):
            return assinatura
    return None


def reversivel_de(assinaturas: List[str]) -> Optional[str]:
    """O valor que é apenas transporte, e não resumo."""
    for assinatura in assinaturas:
        try:
            texto = base64.b64decode(assinatura + "=" * (-len(assinatura) % 4)).decode("utf-8")
        except Exception:
            continue
        if texto.startswith(CONSTANTE):
            return texto
    return None


def derivacao_de(assinaturas: List[str]) -> Optional[str]:
    for assinatura in assinaturas:
        if assinatura.startswith("$2b$"):
            return assinatura
    return None


def conferir(por_conta: Dict[str, List[str]]) -> bool:
    provas = []

    texto = reversivel_de(por_conta["marta.santos89@yahoo.com.br"])
    provas.append(("A Constante da Aplicação", texto and texto.startswith(CONSTANTE),
                   f"decodificado: {texto}"))

    assinatura = hexadecimal_de(por_conta["root.santos15@outlook.com"], 32)
    provas.append(("Trinta e Dois Caracteres", assinatura is not None,
                   f"{len(assinatura) if assinatura else 0} caracteres = md5"))

    assinatura = hexadecimal_de(por_conta["tiago.silva70@gmail.com"], 40)
    provas.append(("Quarenta Caracteres", assinatura is not None,
                   f"{len(assinatura) if assinatura else 0} caracteres = sha-1"))
    provas.append(("O Peso em Bytes", assinatura is not None and len(assinatura) // 2 == 20,
                   f"{len(assinatura) // 2 if assinatura else 0} bytes"))

    assinatura = hexadecimal_de(por_conta["dev.silva51@bol.com.br"], 64)
    provas.append(("Duzentos e Cinquenta e Seis Bits", assinatura is not None,
                   f"{len(assinatura) if assinatura else 0} caracteres = sha-256"))

    texto = reversivel_de(por_conta["pedro.costa37@gmail.com"])
    senha = texto[len(CONSTANTE):] if texto else None
    provas.append(("A Senha Que Não Foi Protegida", senha == "1234567821", f"senha: {senha}"))

    assinatura = hexadecimal_de(por_conta["admin.souza58@uol.com.br"], 32)
    calculado = hashlib.md5((CONSTANTE + "flamengo8277").encode()).hexdigest()
    provas.append(("A Tabela Pré-Computada", assinatura == calculado,
                   f"md5(constante+senha) = {calculado[:20]} contra {str(assinatura)[:20]}"))

    derivacao = derivacao_de(por_conta["marta.pereira99@protonmail.com"])
    sal = derivacao.split("$")[3][:22] if derivacao else None
    provas.append(("O Sal Embutido", sal == "MC45MTQwMjc2NjEwMDk5Mj", f"sal: {sal}"))

    assinatura = hexadecimal_de(por_conta["fernanda.oliveira44@gmail.com"], 64)
    calculado = hashlib.sha256((CONSTANTE + "password4438").encode()).hexdigest()
    provas.append(("O Sufixo de Quatro Dígitos", assinatura == calculado,
                   f"sha256(constante+senha) = {calculado[:20]} contra {str(assinatura)[:20]}"))

    reprovados = []
    for nome, ok, detalhe in provas:
        print(f"  {'PASS' if ok else 'FALHA'}: {nome[:34]:<36} {detalhe[:66]}")
        if not ok:
            reprovados.append(nome)

    print()
    print(f"{len(provas) - len(reprovados)} de {len(provas)} desafios de credenciais resolvem")
    return not reprovados


if __name__ == "__main__":
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--log", type=Path, required=True, help="log de credenciais convertido")
    if not conferir(registros_por_conta(analisador.parse_args().log)):
        raise SystemExit(1)
