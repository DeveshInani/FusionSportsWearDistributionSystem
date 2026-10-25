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

## Deploy the frontend to Netlify

The repository includes a `netlify.toml` that builds the Vite app from
`frontend/` and publishes its generated `dist/` directory. Connect the
repository to Netlify and use the configuration file for the build settings.
If build settings are entered manually, set the base directory to `frontend`,
the build command to `npm run build`, and the publish directory to `dist`.

The FastAPI backend must be deployed separately. Configure the frontend to use
the deployed API before relying on API-backed features; Vite's local `/api`
proxy only applies during development.

Keep `backend/.env` and any other local credentials private. The root
`.gitignore` excludes environment files, local databases, uploaded media,
dependency folders, caches, and generated build output. The `.env.example`
template is safe to track; replace its example values in your private `.env`.
