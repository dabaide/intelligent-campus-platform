#!/bin/sh

# Replace environment variables in nginx config
if [ -n "$BACKEND_URL" ]; then
    envsubst '$BACKEND_URL' < /etc/nginx/nginx.conf > /etc/nginx/nginx.conf.tmp
    mv /etc/nginx/nginx.conf.tmp /etc/nginx/nginx.conf
fi

# Replace environment variables in index.html and JS files
if [ -n "$REACT_APP_API_URL" ]; then
    find /usr/share/nginx/html -name "*.js" -exec sed -i "s|REACT_APP_API_URL_PLACEHOLDER|$REACT_APP_API_URL|g" {} \;
    find /usr/share/nginx/html -name "*.html" -exec sed -i "s|REACT_APP_API_URL_PLACEHOLDER|$REACT_APP_API_URL|g" {} \;
fi

# Execute the original command
exec "$@"
