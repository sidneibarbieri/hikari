FROM nginx:stable

# Instala o apache2-utils para usar o comando htpasswd
RUN apt-get update && apt-get install -y apache2-utils && rm -rf /var/lib/apt/lists/*

# Define variáveis de ambiente para o usuário e senha
ENV NGINX_BASIC_AUTH_USER=user
ENV NGINX_BASIC_AUTH_PASS=userPass456

# Copia o arquivo de configuração do Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Gera o arquivo .htpasswd durante o build
RUN echo "${NGINX_BASIC_AUTH_USER}:$(openssl passwd -apr1 ${NGINX_BASIC_AUTH_PASS})" > /etc/nginx/htpasswd
