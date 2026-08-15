FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY app.html /usr/share/nginx/html/index.html
COPY app.html /usr/share/nginx/html/app.html
COPY assets /usr/share/nginx/html/assets

EXPOSE 80
