
# Project Overview

This is a [Next.js](https://nextjs.org) project created with
[`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app). It includes both a Next.js frontend and a Python-based backend, which can be run locally or through Docker.

---

# Getting Started (Local Development)

If you want to run the frontend locally without Docker, follow the steps below.

## 1. Check your Node.js setup

```bash
node -v
npm -v
```

## 2. Install dependencies

From the **Frontend** directory:

```bash
npm install
```

## 3. Start the development server

```bash
npm run dev
```

Open the app in your browser:

**[http://localhost:3000](http://localhost:3000)**

You can modify `app/page.tsx` and the page will update automatically.

---

# Running with Docker

If you prefer not to install Node.js or Python locally, you can run the entire project using Docker.

## Requirements

Make sure you have:

* Docker
* Docker Compose (v2+, installed automatically with Docker Desktop)

## Environment setup

The app expects the following values:

```
NEXT_PUBLIC_FRONTEND_ORIGIN=http://localhost:3000
BACKEND_URL=http://localhost:5001/api/schedule
```

If you're running the frontend manually (not with Docker), put these in a `.env` file inside the **Frontend** folder.

When using Docker Compose, these values are already passed in automatically, so you normally don’t need to set anything.

## Start the full stack

From the project root:

```bash
docker compose up -d --build
```

When it's up:

* **Frontend:** [http://localhost:3000](http://localhost:3000)
* **Backend:** [http://localhost:5001](http://localhost:5001)

## Stop everything

```bash
docker compose down
```

## Useful Docker commands

See running containers:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

View logs for a specific service:

```bash
docker compose logs -f frontend
docker compose logs -f backend
```

Restart services:

```bash
docker compose restart
```

Open a shell inside a container:

```bash
docker exec -it frontend sh
docker exec -it backend sh
```

Rebuild from scratch:

```bash
docker compose build --no-cache
docker compose up -d
```

Clean up unused Docker data:

```bash
docker system prune
```

---

# Learn More

* Next.js Docs: [https://nextjs.org/docs](https://nextjs.org/docs)
* Next.js Tutorial: [https://nextjs.org/learn](https://nextjs.org/learn)
* Next.js GitHub: [https://github.com/vercel/next.js](https://github.com/vercel/next.js)

---

# Deploying

The easiest way to deploy the frontend is through [Vercel](https://vercel.com).
Check the Next.js deployment guide for details:

[https://nextjs.org/docs/app/building-your-application/deploying](https://nextjs.org/docs/app/building-your-application/deploying)


