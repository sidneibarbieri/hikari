#!/bin/bash


apt update
apt install curl -y

/scripts/create_users.sh
/scripts/check_pipeline.sh
/scripts/setup_kibana.sh
/scripts/setup_kibana_user.sh
/scripts/elasticsearch_user_creation.sh
