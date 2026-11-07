# =====================================================================
# STAGE 1: BASE RUNTIME (Node 20 Alpine & Dependencies)
# =====================================================================
FROM node:20-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# =====================================================================
# STAGE 2: DEVELOPMENT TARGET (Hot-Reloading Vite Dev Server)
# =====================================================================
FROM base AS development
ENV NODE_ENV=development
COPY . .
EXPOSE 5174
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5174"]

# =====================================================================
# STAGE 3: BUILD TARGET (Vite Production Build)
# =====================================================================
FROM base AS builder
COPY . .
RUN npm run build

# =====================================================================
# STAGE 4: PRODUCTION TARGET (Hardened Nginx Alpine Serving Static SPA)
# =====================================================================
FROM nginx:1.27-alpine AS production
RUN apk upgrade --no-cache
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget -q -O - http://127.0.0.1:80/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
