FROM node:20-bookworm-slim AS development

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

FROM development AS build
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
