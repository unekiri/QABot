FROM nginx:1.25-alpine

RUN apk add --no-cache apache2-utils
COPY 40-create-auth-file.sh /docker-entrypoint.d/40-create-auth-file.sh
RUN chmod 755 /docker-entrypoint.d/40-create-auth-file.sh
