FROM node:24-alpine AS builder

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build \
    && npm prune --omit=dev

FROM node:24-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

RUN addgroup -S resumepilot && adduser -S resumepilot -G resumepilot

COPY --from=builder --chown=resumepilot:resumepilot /app/package.json ./package.json
COPY --from=builder --chown=resumepilot:resumepilot /app/package-lock.json ./package-lock.json
COPY --from=builder --chown=resumepilot:resumepilot /app/node_modules ./node_modules
COPY --from=builder --chown=resumepilot:resumepilot /app/.next ./.next
COPY --from=builder --chown=resumepilot:resumepilot /app/next.config.ts ./next.config.ts

USER resumepilot

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-H", "0.0.0.0", "-p", "3000"]
