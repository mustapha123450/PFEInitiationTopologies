FROM node:18-alpine

# Installer curl pour les tests
RUN apk add --no-cache curl

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY server.js .
COPY gateway.js .
COPY device.js .
COPY application.js .

RUN addgroup -g 1001 -S nodejs
RUN adduser -S nodejs -u 1001
USER nodejs

EXPOSE 8080 8181 8282 9001 8081

CMD ["node", "server.js", "--local_ip=0.0.0.0", "--local_port=8080", "--local_name=srv"]