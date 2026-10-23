# School Uniform Store

Full-stack school-uniform e-commerce demo with a React storefront and FastAPI
API.

## Project layout

- `backend/` — FastAPI application, SQLAlchemy models, Alembic migrations,
  tests, and backend setup instructions.
- `frontend/` — React + TypeScript storefront and frontend setup instructions.
- `backend/certs/` — database provider CA certificate used for verified TLS.
- `backend/uploads/` — runtime image uploads; uploaded files are not tracked.

## Run locally

1. Follow [backend setup](./backend/README.md) to configure the database,
   private environment values, and start the API.
2. Follow [frontend setup](./frontend/README.md) to install frontend
   dependencies and start the development server.

Keep `backend/.env` and any other local credentials private. The root
`.gitignore` excludes environment files, local databases, uploaded media,
dependency folders, caches, and generated build output. The `.env.example`
template is safe to track; replace its example values in your private `.env`.
