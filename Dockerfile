FROM node:22-bookworm-slim AS build

WORKDIR /app
COPY . .
RUN npm ci
RUN npm run build --workspace @uniqa-conversion-coach/shared
RUN npm run build --workspace coach-api
RUN npm run build --workspace admin-portal
RUN npm prune --omit=dev

FROM node:22-bookworm-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8080

COPY --from=build /app/package.json /app/package-lock.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/shared ./shared
COPY --from=build /app/coach-api ./coach-api
COPY --from=build /app/admin-portal/dist ./admin-portal/dist

EXPOSE 8080
CMD ["npm", "run", "start", "--workspace", "coach-api"]
