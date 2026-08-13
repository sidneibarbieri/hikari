# Matriz de componentes

Este artefato fixa as versões de infraestrutura em
`deploy/local/docker-compose.yml`. A matriz abaixo registra as versões
exercitadas pela suíte de verificação local.

| Componente | Versão testada | Papel |
| --- | --- | --- |
| CTFd | fork da 3.7.3 | Interface da competição, ciclo de vida dos desafios, fluxos de pessoa e equipe |
| Python | 3.11 slim bookworm | Runtime do CTFd |
| MariaDB | 11.8 | Armazenamento relacional do CTFd e dos registros de atividade do Hikari |
| Redis | 8.2 Alpine | Cache, sessões e estado do limite de requisições |
| Apache Kafka | 4.2.0 | Fluxo de eventos dos logs da competição e das atividades |
| Elasticsearch | 8.19.15 | Índice dos logs dos desafios e do espelho de atividade para pesquisa |
| Kibana | 8.19.15 | Interface do SIEM e painéis |
| Logstash | 8.19.15, imagem local construída de `deploy/local/logstash` | Pipelines de ingestão do Kafka para o Elasticsearch |

Atualize um componente por vez. Após cada mudança, reconstrua a stack e execute:

```bash
cd deploy/local
make acceptance
```

Mantenha a versão fixada quando a suíte falhar. Registre a falha, corrija a
integração e execute a mesma suíte novamente antes de publicar a mudança.
