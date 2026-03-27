#=========================================================================#
# Hestia Nginx Template - Docker reverse proxy for SIGEDO                 #
# Domain: sigedo.ddnsgeek.com                                             #
# Copies go to: /usr/local/hestia/data/templates/web/nginx/               #
#=========================================================================#
server {
    listen      %ip%:%web_port%;
    server_name %domain_idn% %alias_idn%;
    root        %docroot%;
    index       index.html index.htm;

    access_log  /var/log/nginx/domains/%domain%.log combined;
    access_log  /var/log/nginx/domains/%domain%.bytes bytes;
    error_log   /var/log/nginx/domains/%domain%.error.log error;

    include %home%/%user%/conf/web/%domain%/nginx.forcessl.conf*;

    location ~ /\.(?!well-known\/) {
        deny all;
        return 404;
    }

    location /static/ {
        alias %docroot%/static/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias %docroot%/media/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
        proxy_redirect off;
    }
}
