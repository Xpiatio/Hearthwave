# ── Stage 1: builder ────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Copy all frontend source files
COPY src/ ./src/
COPY index.html tsconfig.json vite.config.ts ./

RUN npm run build

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM nginx:alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
