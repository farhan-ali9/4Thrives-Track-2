FROM node:22-bookworm-slim AS base

WORKDIR /app
RUN apt-get update \
  && apt-get install -y --no-install-recommends openssl \
  && rm -rf /var/lib/apt/lists/*

FROM base AS builder

COPY package.json package-lock.json ./
COPY shared/package.json ./shared/package.json
COPY coach-api/package.json ./coach-api/package.json
COPY extension/package.json ./extension/package.json
COPY admin-portal/package.json ./admin-portal/package.json
RUN npm ci --ignore-scripts \
  --workspace @uniqa-conversion-coach/shared \
  --workspace coach-api

COPY shared ./shared
COPY coach-api ./coach-api
RUN ./node_modules/.bin/prisma generate --schema coach-api/prisma/schema.prisma
RUN npm run build --workspace @uniqa-conversion-coach/shared
RUN npm run build --workspace coach-api

FROM base AS runtime
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8080
ENV NODE_OPTIONS=--experimental-specifier-resolution=node

COPY package.json package-lock.json ./
COPY shared/package.json ./shared/package.json
COPY coach-api/package.json ./coach-api/package.json
COPY extension/package.json ./extension/package.json
COPY admin-portal/package.json ./admin-portal/package.json
RUN npm ci --omit=dev --ignore-scripts \
  --workspace @uniqa-conversion-coach/shared \
  --workspace coach-api \
  && npm install --no-save --ignore-scripts prisma@6.19.3

COPY --from=builder /app/shared/dist ./shared/dist
COPY --from=builder /app/coach-api/dist ./coach-api/dist
COPY --from=builder /app/coach-api/prisma ./coach-api/prisma
RUN ./node_modules/.bin/prisma generate --schema coach-api/prisma/schema.prisma

EXPOSE 8080
CMD ["npm", "run", "start", "--workspace", "coach-api"]
