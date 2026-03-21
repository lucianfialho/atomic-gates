# Performance Review Rules

Loaded when performance review is requested or when performance-sensitive files are changed.

## Data Fetching
- No N+1 database queries
- Parallel data fetching where possible (Promise.all)
- No waterfall requests (sequential fetches that could be parallel)
- Caching strategy for expensive operations

## Rendering
- Server Components by default (zero client JS)
- No unnecessary re-renders (proper deps in useEffect, useMemo)
- Heavy components lazy loaded (dynamic import)
- Streaming with Suspense for slow data

## Assets
- Images optimized (next/image, proper format, sizing)
- Fonts self-hosted or via next/font
- Third-party scripts loaded with proper strategy (afterInteractive, lazyOnload)
- Bundle size monitored — no large libraries for small features

## Infrastructure
- Functions in correct region (close to data)
- Proper cache headers on static assets
- Large lists paginated (not loading all records)
- Background work uses waitUntil/after (not blocking response)
