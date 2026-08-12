# Local operational checks

Use these commands after changing the local stack or before opening it to
participants. They do not create users, teams, or challenges.

```bash
cd deploy/local
bash bootstrap.sh
bash tests/smoke.sh --wait
```

The operator interface is available at:

| Surface | URL | Access |
| --- | --- | --- |
| Competition | `http://localhost:8000/` | CTFd session |
| SIEM gateway | `http://localhost:8000/hikari/siem` | CTFd session |
| Live board | `http://localhost:8000/hikari/live` | Public |
| Research dashboard | `http://localhost:8000/admin/hikari/research` | Administrator |

Run the full verification only in its isolated environment:

```bash
bash tests/acceptance_isolated.sh
```

On a workstation with limited memory, stop the local stack first and start it
again after validation. This preserves the named volumes and avoids running
two Elasticsearch and Kibana instances at once.

```bash
docker-compose stop
bash tests/acceptance_isolated.sh
docker-compose up -d
```

To verify a legacy backup without changing the active stack:

```bash
bash tests/verify_backup_import.sh /path/to/data_backup.zip
```

The isolated checks create and remove their own Compose project and volumes.
