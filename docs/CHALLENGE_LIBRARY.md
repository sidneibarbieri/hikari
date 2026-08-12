# Biblioteca de desafios

Uma biblioteca é um arquivo ZIP portátil que reúne desafios, flags,
dependências e conjuntos de logs. O administrador a importa em
`/admin/hikari/challenge-library` antes de agendar uma execução. A plataforma
valida todo o conteúdo antes de criar qualquer registro.

Não use backups de uma execução como biblioteca: o backup preserva o estado de
uma instalação. A biblioteca descreve desafios reutilizáveis e não inclui
contas, equipes, submissões nem atividade de participantes.

## Estrutura do pacote

```text
minha-biblioteca.zip
├── manifest.json
└── logs/
    ├── coleta-inicial.json
    └── correlacao.json
```

`manifest.json` usa a versão de formato `1`:

```json
{
  "format_version": 1,
  "package_key": "defesa-2026",
  "display_name": "Desafios de defesa 2026",
  "challenges": [
    {
      "key": "coleta-inicial",
      "name": "Coleta inicial",
      "category": "Forense",
      "description": "Identifique o indicador solicitado no conjunto de eventos.",
      "flag": "HIKARI{exemplo-substitua-antes-de-importar}",
      "value": 100,
      "state": "visible",
      "prerequisites": [],
      "log_file": "logs/coleta-inicial.json"
    },
    {
      "key": "correlacao",
      "name": "Correlação",
      "category": "Forense",
      "description": "Relacione os eventos liberados e informe o indicador.",
      "flag": "HIKARI{outro-exemplo-substitua-antes-de-importar}",
      "value": 200,
      "state": "visible",
      "prerequisites": ["coleta-inicial"],
      "log_file": "logs/correlacao.json"
    }
  ]
}
```

Cada chave usa apenas letras minúsculas, números e hífens. O arquivo de logs
é opcional; quando informado, precisa estar sob `logs/`, ter extensão `.json`
e conter uma lista JSON de objetos. A biblioteca pode conter até 500 desafios
e 512 MB descompactados.

## Regras de importação

1. Faça a importação antes de criar uma execução agendada ou ativa.
2. Use uma `package_key` inédita na instalação.
3. Valide o ZIP no ambiente local isolado antes de enviá-lo ao servidor.
4. Após a importação, confira os desafios em `Desafios` no painel CTFd.
5. Faça um checkpoint antes de iniciar a competição.

O importador recusa referências a desafios inexistentes, dependências próprias,
chaves duplicadas, arquivos ausentes, caminhos fora de `logs/` e JSON de logs
malformado. As flags ficam somente no banco da instalação; não publique o ZIP
de uma biblioteca com flags de uma competição em repositório público.

## Relação com conjuntos legados

Conjuntos recebidos em formatos antigos podem servir como fonte de migração,
mas não são aceitos diretamente. Converta cada desafio para o manifesto acima,
separe o JSON de logs correspondente e valide as flags antes da importação.
Isso evita que convenções implícitas de diretórios, arquivos auxiliares ou
metadados de uma edição alterem outra execução.
