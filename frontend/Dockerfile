# ── Stage 1: builder ────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY src/ ./src/
COPY index.html tsconfig.json tsconfig.build.json vite.config.ts ./

RUN npm run build

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Override main config (caps worker_processes; base image uses 'auto' which
# can hang on high-core-count hosts) and replace the default server block.
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.main.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

# Use 127.0.0.1, not localhost: inside the container localhost resolves to
# IPv6 ::1 first, but nginx listens on IPv4 0.0.0.0:8080, so a localhost
# probe is refused and the container is falsely reported unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
