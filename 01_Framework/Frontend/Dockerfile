FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

ENV NEXT_DISABLE_ESLINT=1
ENV NEXT_DISABLE_TYPECHECK=1
ARG NEXT_PUBLIC_FRONTEND_ORIGIN
ENV NEXT_PUBLIC_FRONTEND_ORIGIN=$NEXT_PUBLIC_FRONTEND_ORIGIN

RUN npm run build

FROM node:20-alpine

WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app ./

EXPOSE 3000

CMD ["npm", "run", "start"]
