# Dockerfile for ADS Safety Platform Frontend
FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json vite.config.js ./

RUN npm install --frozen-lockfile 2>/dev/null || npm install

COPY src/ ./src/

RUN npm run build

# Production: serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]