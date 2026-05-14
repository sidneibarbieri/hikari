FROM docker.elastic.co/logstash/logstash:8.19.15

COPY config/logstash.yml /usr/share/logstash/config/logstash.yml
COPY config/pipelines.yml /usr/share/logstash/config/pipelines.yml
COPY pipelines/ /usr/share/logstash/pipelines/
