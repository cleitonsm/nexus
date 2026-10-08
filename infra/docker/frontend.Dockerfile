FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend .
RUN npm run build

FROM nginx:1.27-alpine

# O modelo vira /etc/nginx/conf.d/default.conf na subida, com os enderecos do
# Keycloak lidos do ambiente.
COPY frontend/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
