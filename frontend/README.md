# Prodigy Uniform Wear

Responsive React + TypeScript storefront for the school uniform ordering POC.

## Run

Run the API using the instructions in `../backend/README.md`, then start Vite:

```powershell
npm install
npm run dev
```

Vite proxies `/api` requests to `http://localhost:8000`.

## Frontend structure

- `src/App.tsx` — session restoration and top-level page navigation
- `src/pages/` — sign-in/registration, catalog, cart, checkout, payment,
  confirmation, order history/tracking and store dashboard
- `src/components/` — shared brand, navigation, product card, analytics charts
  and status badge
- `src/services/api.ts` — authenticated API requests and invoice downloads
- `src/types.ts` — shared API/domain types
