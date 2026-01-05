# --- Build stage ---
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .

ENV NEXT_DISABLE_ESLINT=1
ENV NEXT_DISABLE_TYPECHECK=1
ARG NEXT_PUBLIC_FRONTEND_ORIGIN
ENV NEXT_PUBLIC_FRONTEND_ORIGIN=$NEXT_PUBLIC_FRONTEND_ORIGIN

RUN npm run build


FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -S nextjs && adduser -S nextjs -G nextjs


RUN rm -f /usr/bin/wget /bin/wget 2>/dev/null || true

# Copy only runtime-required artifacts
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/next.config.* ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
# If you use custom server code or other runtime files, copy them explicitly too:
# COPY --from=builder /app/server.js ./server.js

RUN npm ci --omit=dev && npm cache clean --force

RUN chown -R nextjs:nextjs /app

USER nextjs

EXPOSE 3000

CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3000"]
