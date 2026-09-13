#!/bin/sh
set -eu

password_file=/run/secrets/qabot_auth_password
username=${QABOT_AUTH_USER:-qabot}

case "$username" in
    *[!A-Za-z0-9._-]*|'')
        echo "QABOT_AUTH_USER contains invalid characters" >&2
        exit 1
        ;;
esac

if [ ! -s "$password_file" ]; then
    echo "qabot_auth_password secret is required" >&2
    exit 1
fi

password=$(cat "$password_file")
if [ -z "$password" ]; then
    echo "qabot_auth_password secret must not be empty" >&2
    exit 1
fi
if [ "${#password}" -lt 12 ]; then
    echo "qabot_auth_password secret must contain at least 12 characters" >&2
    exit 1
fi

htpasswd -Bbc /etc/nginx/qabot.htpasswd "$username" "$password" >/dev/null
chown nginx:nginx /etc/nginx/qabot.htpasswd
chmod 600 /etc/nginx/qabot.htpasswd
unset password
