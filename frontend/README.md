# Prodigy Uniform Wear

Responsive React + TypeScript storefront for the school uniform ordering POC.

## Run

Run the API using the instructions in `../backend/README.md`, then start Vite:

```powershell
npm install
npm run dev
```

Vite proxies `/api` requests to `http://localhost:8000`.

## Deploy

For Netlify, set the `VITE_API_BASE_URL` environment variable to the deployed
FastAPI service's origin, such as `https://your-api.example.com` (no trailing
slash and no `/api` suffix). Trigger a new frontend deploy after setting it;
Vite embeds this value at build time. Without it, production requests use the
local-development `/api` path and will receive Netlify 404s. API requests and
uploaded media are sent to the configured backend.

## Frontend structure

- `src/App.tsx` — session restoration and top-level page navigation
- `src/pages/` — sign-in/registration, catalog, cart, checkout, payment,
  confirmation, order history/tracking and store dashboard
- `src/components/` — shared brand, navigation, product card, analytics charts
  and status badge
- `src/services/api.ts` — authenticated API requests and invoice downloads
- `src/types.ts` — shared API/domain types
