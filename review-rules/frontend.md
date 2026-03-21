# Frontend Review Rules

Loaded when the diff contains `.tsx`, `.jsx`, `.css`, `.scss`, or `.module.css` files.

## Components
- Server Components by default — `'use client'` only when needed
- Push `'use client'` as far down the tree as possible
- No `any` type — use proper TypeScript types
- Handle all states: loading, error, empty, edge cases
- Use semantic HTML (`<button>`, `<nav>`, `<main>`, not styled divs)

## Accessibility
- Interactive elements have accessible labels (aria-label or visible text)
- Keyboard navigation works (Tab order, Enter/Space activation)
- Color is not the only way to convey information
- Images have meaningful alt text
- Touch targets are at least 44x44px on mobile

## Performance
- No unnecessary re-renders (check dependency arrays)
- Large lists use virtualization or pagination
- Images use `next/image` with proper width/height
- Fonts use `next/font` for zero CLS
- Lazy load below-fold content

## Styling
- Follow existing design system/component library patterns
- Use design tokens (CSS variables) not hardcoded values
- Mobile-first responsive design (320px → 1920px)
- Dark mode support if the project uses it
