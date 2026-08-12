# Test execution

The acceptance scripts create accounts, teams, challenges and Elasticsearch
events. Run them only through the isolated entrypoint:

```bash
bash acceptance_isolated.sh
```

It creates a disposable Compose project, executes the 26 checks and removes
its containers and volumes when finished. It never changes a running
competition.

`verify_backup_import.sh` also starts a disposable project. It imports the
legacy archive supplied as its first argument, validates the restored state
and removes the project afterwards.

The individual scripts are diagnostic tools. Do not run them against an
active competition because they intentionally create test records.
