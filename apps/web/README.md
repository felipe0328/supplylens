# SupplyLens Frontend

<div align="center">

![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-149eca)
![Bundler](https://img.shields.io/badge/vite-8-646CFF)
![Status](https://img.shields.io/badge/status-early%20scaffold-orange)

</div>

---

## 🎯 What this app is

This is the frontend for SupplyLens, created with React 19, TypeScript, and Vite.

Right now, it is still a starter shell rather than the final product UI. The app boots correctly, but the business workflow for document upload, review, and purchase analysis has not been implemented yet.

---

## 📍 Current implementation snapshot

```text
apps/web/
├── public/              # static assets
├── src/
│   ├── App.tsx          # starter app shell
│   ├── App.css          # starter styling
│   ├── main.tsx         # app bootstrap
│   └── assets/          # bundled media
├── package.json         # scripts and dependencies
├── vite.config.ts       # Vite configuration
├── tsconfig*.json       # TypeScript config
├── eslint.config.js     # lint config
├── index.html           # Vite entry page
└── README.md            # this guide
```

---

## ⚙️ Setup

### 1) Install dependencies

From the repo root or directly inside `apps/web`:

```bash
cd apps/web
npm ci
```

### 2) Start the frontend

```bash
cd apps/web
npm run dev
```

The dev server typically runs on:

```text
http://127.0.0.1:5173
```

---

## 🛠️ Available scripts

```bash
npm run dev          # start Vite dev server
npm run build        # type-check + production bundle
npm run lint         # run ESLint
npm run test         # run Vitest tests
npm run typecheck    # TypeScript check only
npm run preview      # preview production build locally
```

You can also use the repo-level Makefile:

```bash
make fe
make fe-lint
make fe-build
make setup
```

---

## 🧪 Current status

This frontend is currently a modern React/Vite starter with no SupplyLens-specific workflow implemented yet. The next product-facing work will likely include:

- upload and review flow for supplier PDFs
- document side-by-side comparison views
- confirmation and correction tooling
- report and purchase summary pages
- search and cited document Q&A

---

## 🧩 Development standards

This app follows the repo conventions in [AGENTS.md](../../AGENTS.md):

- TypeScript and React conventions remain the default
- keep components simple and explicit
- prefer deterministic UI behavior over hidden logic
- do not rely on AI to approve business values or final decisions

---

## 🔗 Related docs

- [Main project README](../../README.md)
- [Backend README](../backend/README.md)
- [Architecture document](../../docs/SupplyLens-Architecture-v0.1.md)
- [MVP definition](../../docs/SupplyLens-MVP-Definition-v0.1.md)
