sudo ls
kubectl create namespace velero
wget https://github.com/vmware-tanzu/velero/releases/download/v1.14.0/velero-v1.14.0-linux-amd64.tar.gz
{ export VELERO_VERSION="1.14.0"; tar xf velero-v${VELERO_VERSION}-linux-amd64.tar.gz ; sudo mv velero-v${VELERO_VERSION}-linux-amd64/velero /usr/local/bin/; sudo chown root:root /usr/local/bin/velero; }
cat tkg-velero-backups

[default]
aws_access_key_id=<put yours>
aws_secret_access_key=<put yours>

vim tkg-velero-backups

velero install     --provider aws     --plugins velero/velero-plugin-for-aws:v1.0.0     --bucket tkg-velero-backups     --backup-location-config region=sa-east-1     --secret-file ./tkg-velero-backups     --use-node-agent     --default-volumes-to-fs-backup

kubectl get pods -n velero

# restore namespace
velero restore create wildfire-db-restore-v5 --from-backup wildfire-db-backup-v2 --wait
velero restore describe wildfire-db-restore-v5 --details
kubectl get pods -n wildfire-db
kubectl get pvc -n wildfire-db

-------------------------------

Identify the namespaces pvcs that are needed by running probevolumes on the specified namespace

ubuntu@k8s-devias-cluster-bastion-1:~$ ./probevolumes.sh defectdojo
Processing namespace: defectdojo
  Pod: dejectdojo-defectdojo-celery-beat-7bf5b6c7bd-xnbnv
  Pod: dejectdojo-defectdojo-celery-worker-6975748bf8-xj6lw
  Pod: dejectdojo-defectdojo-django-5c59cdb6d7-kkttx
  Pod: dejectdojo-initializer-2023-06-13-13-22-dh9hv
  Pod: dejectdojo-postgresql-0
    PVC: data-dejectdojo-postgresql-0, MountPath: /bitnami/postgresql
Annotating pod dejectdojo-postgresql-0 with mount path /bitnami/postgresql
  Pod: dejectdojo-rabbitmq-0

Let’s backup the namespaces that are do not have pvc

velero backup create wildfire-ai-backup \
    --include-namespaces wildfire-ai \
    --default-volumes-to-fs-backup \
    --ttl 8760h \
    --wait

# if needed 
velero backup delete wildfire-db-backup --confirm --wait

Store the backups in a safe place

# prod machine
aws s3 ls s3://tkg-velero-backups/
velero backup delete --all
velero backup get

# aws console machine
aws s3 ls s3://tkg-velero-backups/ --recursive
aws s3 sync s3://tkg-velero-backups/ /home/cesar/tkg-velero-backups
aws s3 rm s3://tkg-velero-backups --recursive
aws s3 ls s3://tkg-velero-backups/
# sync back the velero backups stored separately
aws s3 sync /home/cesar/tkg-velero-backups/ s3://tkg-velero-backups/

# backup to dev machine ot prod machine 
kubectl get namespaces
velero restore create wildfire-db-restore-v6 --from-backup wildfire-db-backup-v2 --wait
kubectl exec -n wildfire-db -it wildfire-db-mariadb-0 -- mysql -u root -p

Verifications

# check the size of the backups
aws s3 ls s3://tkg-velero-backups --recursive --human-readable --summarize
