# ---------- 构建阶段 ----------
FROM node:20 AS build
WORKDIR /app

# 先拷贝依赖清单，利用 Docker 层缓存
COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com

# 拷贝源码并构建
COPY . .
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:alpine

# 静态产物
COPY --from=build /app/dist /usr/share/nginx/html

# Nginx 配置（/api 反代到 backend:8000，SSE 长连接支持）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]