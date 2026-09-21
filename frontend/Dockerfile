# 1단계: 정적 파일 빌드
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# nginx가 /api를 백엔드로 넘겨주므로 프론트는 같은 출처만 부르면 된다 (CORS 문제 없음)
ENV VITE_API_URL=/api
RUN npm run build

# 2단계: nginx로 서빙 + /api 프록시
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
