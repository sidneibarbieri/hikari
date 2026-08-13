# Arquitetura

O Hikari executa uma interface de competição do CTFd ao lado de uma superfície
de investigação apoiada em Elasticsearch e Kibana. O CTFd é dono de identidade,
equipes, desafios, pontuação, feedback e exportações de pesquisa. O Kafka leva
os logs injetados pelos desafios e os eventos de atividade até o Elasticsearch
para busca e análise.

## Disposição em execução

    navegador
      |-- páginas do CTFd: desafios, equipes, feedback, placar ao vivo
      |-- /hikari/siem, gateway autenticado
              |
              v
    CTFd + plugin Hikari
      |-- MariaDB: pessoas, equipes, desafios, solves, atividade, feedback
      |-- Redis: cache e estado do limite de requisições
      |-- Kafka: logs da competição e fluxo de atividade
              |
              v
    Logstash -> Elasticsearch -> Kibana

## Fluxo da competição

Os competidores se cadastram no CTFd, criam ou entram em equipes, abrem a
superfície SIEM e submetem flags pelos desafios do CTFd. Os registros de
desafio do Hikari guardam os arquivos de log que cada desafio ativa. Quando um
desafio é resolvido, os logs dependentes podem ser transmitidos ao
Elasticsearch pelo Kafka. O conjunto de dados investigado muda durante a
competição, então o tempo até o solve afeta quanto ruído os competidores
seguintes precisam examinar.

Um administrador cria uma execução nomeada antes do início. A chave dessa
execução é gravada junto aos registros de atividade e de feedback, o
cronograma é aplicado ao CTFd, e o estado cronometrado pode ser estendido,
pausado, retomado ou encerrado pela interface administrativa. As identidades,
a pontuação e os desafios do CTFd são tabelas globais, portanto uma instalação
hospeda uma competição ativa. Competições simultâneas e independentes exigem
projetos Compose e volumes separados.

## Fluxo de pesquisa

O plugin registra em `hikari_activity` as ações observadas no CTFd e no Kibana.
O tráfego do Kibana passa pelo gateway autenticado, que classifica cada
requisição uma vez e guarda fatos estruturados junto ao registro de atividade.
O painel de análise científica lê esses registros e exporta JSONL para análise
externa.

## Limites

O artefato local é o alvo de revisão e de desenvolvimento. A instalação em
produção usa os mesmos componentes de aplicação, com TLS, nomes de host,
segredos, política de backup e controle de acesso definidos pela implantação.
