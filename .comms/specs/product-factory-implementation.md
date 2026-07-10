# Product Factory — Implementation Guide

> **Purpose**: This document contains everything needed to implement a domain-based product system on top of the existing uzhavu.race architecture. Read this, implement it, ship standalone products.
>
> **Context**: Uzhavu is a multi-tenant SaaS monorepo (Turborepo + pnpm) with a plug-and-play app architecture. Each "app" (inventory, sales, invoicing, support, tasks) has a manifest, and apps are gated by subscription plans. This guide adds a **product layer** on top — so the same codebase can power multiple branded standalone products via different domains.
>
> **Prerequisites**: Read `APP_ARCHITECTURE.md` first. Understand the manifest system, registry, and plan-based gating.

---

## What We're Building

```
                    UZHAVU CODEBASE (single repo)
                            │
              ┌─────────────┼─────────────────┐
              │             │                  │
     farmbook.in    invoicesimple.in    gymtrack.in
     (inventory,    (invoicing,         (inventory,
      sales,         sales,              invoicing,
      feed)          finance)            tasks)
     Green theme    Blue theme          Red theme
```

**One codebase → multiple branded products → different domains → different app combinations.**

Each product is defined by a single config file (~20 lines). No code duplication. No forks. Bug fix once → all products get it.

---

## Step 1: Create the ProductConfig Type

### File: `apps/web/src/types/product.ts` [NEW]

```typescript
export interface ProductPlan {
  /** Monthly price in INR (0 = free) */
  price: number;
  /** Usage limits for this plan tier */
  limits: Record<string, number>;
  /** Which app IDs are available in this plan */
  apps: string[];
}

export interface ProductBranding {
  /** Path to logo SVG/PNG (relative to public/) */
  logo: string;
  /** Primary brand color (hex) */
  primaryColor: string;
  /** Favicon path */
  favicon?: string;
  /** Footer text override */
  footerText?: string;
}

export interface ProductMarketing {
  /** Hero headline for landing page */
  hero: string;
  /** Short product description */
  description: string;
  /** Feature bullet points */
  features: string[];
  /** CTA button text */
  ctaText?: string;
}

export interface ProductConfig {
  /** Unique product ID (kebab-case) */
  id: string;

  /** Display name shown in UI */
  name: string;

  /** One-line tagline */
  tagline: string;

  /** Primary domain for this product */
  domain: string;

  /** Additional domains that map to this product */
  aliasDomains?: string[];

  /** Which app IDs to include (from ALL_APPS in registry) */
  apps: string[];

  /** Plan tiers specific to this product */
  plans: Record<string, ProductPlan>;

  /** Branding overrides */
  branding: ProductBranding;

  /** Feature flags specific to this product */
  features: {
    ai_assistant: boolean;
    voice_input: boolean;
    knowledge_base: boolean;
    webhooks: boolean;
    api_access: boolean;
  };

  /** Landing page content */
  marketing: ProductMarketing;

  /** Default system prompt override for AI assistant (optional) */
  aiSystemPrompt?: string;
}
```

---

## Step 2: Create the Full Platform Product (Default)

### File: `apps/web/src/products/uzhavu.ts` [NEW]

```typescript
import type { ProductConfig } from '@/types/product';

export const product: ProductConfig = {
  id: 'uzhavu',
  name: 'Uzhavu',
  tagline: 'Complete business platform for Indian SMBs',
  domain: 'app.uzhavu.com',
  aliasDomains: ['localhost:3000'],

  // Full platform — all apps
  apps: ['inventory', 'sales', 'invoicing', 'support', 'tasks'],

  plans: {
    free: {
      price: 0,
      limits: { users: 2, products: 50 },
      apps: ['inventory', 'tasks'],
    },
    starter: {
      price: 499,
      limits: { users: 5, products: 500 },
      apps: ['inventory', 'sales', 'invoicing', 'tasks'],
    },
    pro: {
      price: 1499,
      limits: { users: 25, products: 10000 },
      apps: ['inventory', 'sales', 'invoicing', 'support', 'tasks'],
    },
    enterprise: {
      price: 4999,
      limits: { users: -1, products: -1 },  // -1 = unlimited
      apps: ['inventory', 'sales', 'invoicing', 'support', 'tasks'],
    },
  },

  branding: {
    logo: '/logo.svg',
    primaryColor: '#16a34a',  // Uzhavu green
  },

  features: {
    ai_assistant: true,
    voice_input: true,
    knowledge_base: true,
    webhooks: true,
    api_access: true,
  },

  marketing: {
    hero: 'Complete Business Platform for Indian SMBs',
    description: 'Inventory, sales, invoicing, support — all in one place.',
    features: [
      'GST-compliant invoicing',
      'Inventory management',
      'Sales tracking',
      'Customer support tickets',
      'AI assistant',
    ],
  },
};
```

---

## Step 3: Create First Standalone Product

### File: `apps/web/src/products/invoice-simple.ts` [NEW]

```typescript
import type { ProductConfig } from '@/types/product';

export const product: ProductConfig = {
  id: 'invoice-simple',
  name: 'InvoiceSimple',
  tagline: 'GST invoicing made simple',
  domain: 'invoicesimple.in',
  aliasDomains: ['invoice.localhost:3000'],

  apps: ['invoicing', 'sales'],

  plans: {
    free: {
      price: 0,
      limits: { invoices_per_month: 10, clients: 5 },
      apps: ['invoicing'],
    },
    pro: {
      price: 299,
      limits: { invoices_per_month: 500, clients: 100 },
      apps: ['invoicing', 'sales'],
    },
  },

  branding: {
    logo: '/products/invoice-simple/logo.svg',
    primaryColor: '#2563eb',
    footerText: '© InvoiceSimple',
  },

  features: {
    ai_assistant: true,
    voice_input: false,
    knowledge_base: false,
    webhooks: false,
    api_access: false,
  },

  marketing: {
    hero: 'Simple GST Invoicing for Indian Businesses',
    description: 'Create professional GST invoices in 30 seconds.',
    features: [
      'GST-compliant invoices',
      'Auto-calculate CGST/SGST/IGST',
      'PDF export & WhatsApp share',
      'Payment tracking',
      'Client management',
    ],
    ctaText: 'Start Free — No Credit Card',
  },

  aiSystemPrompt: 'You are InvoiceSimple AI — a helpful assistant specialized in Indian GST invoicing, tax compliance, and payment tracking. Keep responses concise and business-focused.',
};
```

### Create more products following the same pattern:

| File | Product | Apps |
|:-----|:--------|:-----|
| `products/farm-book.ts` | FarmBook | inventory, sales |
| `products/shop-track.ts` | ShopTrack | inventory, sales, invoicing |
| `products/support-desk.ts` | SupportDesk | support, tasks |
| `products/task-flow.ts` | TaskFlow | tasks |

---

## Step 4: Create Product Registry

### File: `apps/web/src/products/registry.ts` [NEW]

```typescript
import type { ProductConfig } from '@/types/product';

// ── Import all product configs ─────────────────────
import { product as uzhavu } from './uzhavu';
import { product as invoiceSimple } from './invoice-simple';
// import { product as farmBook } from './farm-book';
// import { product as shopTrack } from './shop-track';
// ... add more as you create them

const ALL_PRODUCTS: ProductConfig[] = [
  uzhavu,
  invoiceSimple,
  // farmBook,
  // shopTrack,
];

// ── Build domain lookup map ─────────────────────────
const DOMAIN_MAP = new Map<string, string>();
for (const p of ALL_PRODUCTS) {
  DOMAIN_MAP.set(p.domain, p.id);
  for (const alias of p.aliasDomains || []) {
    DOMAIN_MAP.set(alias, p.id);
  }
}

/**
 * Resolve product ID from a hostname.
 * Falls back to 'uzhavu' (full platform) if no match.
 */
export function resolveProductFromDomain(hostname: string): string {
  // Strip port for matching if needed
  return DOMAIN_MAP.get(hostname) || DOMAIN_MAP.get(hostname.split(':')[0]) || 'uzhavu';
}

/**
 * Get product config by ID.
 */
export function getProduct(productId: string): ProductConfig {
  return ALL_PRODUCTS.find((p) => p.id === productId) || uzhavu;
}

/**
 * Get the current product config.
 * Reads from:
 *   1. PRODUCT_ID env var (for server-side / build-time)
 *   2. Cookie 'product_id' (for client-side, set by middleware)
 */
export function getCurrentProduct(): ProductConfig {
  // Server-side: env var takes priority
  const envProduct = process.env.PRODUCT_ID;
  if (envProduct) return getProduct(envProduct);

  // Fallback to full platform
  return uzhavu;
}

/**
 * Get all registered products (for admin/internal use).
 */
export function getAllProducts(): ProductConfig[] {
  return ALL_PRODUCTS;
}
```

---

## Step 5: Domain Detection Middleware

### File: `apps/web/src/middleware.ts` [MODIFY]

Add product detection to the existing middleware. If `middleware.ts` re-exports from `proxy.ts`, modify accordingly.

```typescript
import { NextResponse, type NextRequest } from 'next/server';
import { resolveProductFromDomain } from '@/products/registry';

export function middleware(request: NextRequest) {
  const hostname = request.headers.get('host') || 'localhost:3000';
  const productId = resolveProductFromDomain(hostname);

  // Clone the request headers and add product context
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-product-id', productId);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });

  // Set cookie so client components can read the product ID
  response.cookies.set('product_id', productId, {
    httpOnly: false,  // Client-readable
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24,  // 1 day
  });

  return response;
}

export const config = {
  matcher: [
    // Match all routes except static files and API internals
    '/((?!_next/static|_next/image|favicon.ico|products/).*)',
  ],
};
```

> **Note**: If the existing middleware has auth logic (from `proxy.ts`), MERGE this product detection into it. Don't replace the auth middleware — add to it.

---

## Step 6: Modify App Registry — Filter by Product

### File: `apps/web/src/platform/registry.ts` [MODIFY]

Add product-aware filtering to the existing `getAppsForPlan` function.

```typescript
// ADD this import at the top
import { getCurrentProduct } from '@/products/registry';

// MODIFY getAppsForPlan — add product filtering
export function getAppsForPlan(planName: string): AppManifest[] {
  const product = getCurrentProduct();

  return ALL_APPS.filter((app) => {
    // ── NEW: Only include apps that belong to this product ──
    if (!product.apps.includes(app.id)) return false;

    // ── EXISTING: Check plan access ──
    if (!app.plans.includes(planName as any)) return false;

    // ── EXISTING: Check dependencies ──
    for (const depId of app.dependencies) {
      const dep = ALL_APPS.find((a) => a.id === depId);
      if (!dep || !dep.plans.includes(planName as any)) return false;
    }

    return true;
  });
}

// ADD new helper
export function getAppsForProduct(productId?: string): AppManifest[] {
  const product = productId 
    ? require('@/products/registry').getProduct(productId)
    : getCurrentProduct();
  
  return ALL_APPS.filter((app) => product.apps.includes(app.id));
}
```

**This is the critical change.** Once the registry filters by product, the sidebar, navigation, and all UI that reads from the registry will automatically show only the correct apps.

---

## Step 7: Product-Aware Branding

### File: `apps/web/src/hooks/useProduct.ts` [NEW]

Client-side hook to access current product config:

```typescript
'use client';

import { useMemo } from 'react';
import { getProduct } from '@/products/registry';

export function useProduct() {
  const productId = useMemo(() => {
    if (typeof document === 'undefined') return 'uzhavu';
    const cookie = document.cookie
      .split('; ')
      .find((c) => c.startsWith('product_id='));
    return cookie?.split('=')[1] || 'uzhavu';
  }, []);

  return useMemo(() => getProduct(productId), [productId]);
}
```

### File: `apps/web/src/components/AppSidebar.tsx` [MODIFY]

Add product branding to the sidebar:

```typescript
// ADD import
import { useProduct } from '@/hooks/useProduct';

// INSIDE the component:
export function AppSidebar() {
  const product = useProduct();

  // Use product.branding.logo instead of hardcoded logo
  // Use product.name instead of "Uzhavu"
  // Use product.branding.primaryColor for accent

  return (
    <aside>
      <div className="sidebar-header">
        <img src={product.branding.logo} alt={product.name} />
        <span>{product.name}</span>
      </div>
      {/* rest of sidebar — already reads from registry, which now filters by product */}
    </aside>
  );
}
```

### File: `apps/web/src/app/layout.tsx` [MODIFY]

Inject product theme as CSS custom properties:

```typescript
// In the root layout or dashboard layout
import { getCurrentProduct } from '@/products/registry';

export default function RootLayout({ children }) {
  const product = getCurrentProduct();

  return (
    <html>
      <head>
        <title>{product.name}</title>
        <link rel="icon" href={product.branding.favicon || '/favicon.ico'} />
      </head>
      <body style={{
        '--brand-primary': product.branding.primaryColor,
      } as React.CSSProperties}>
        {children}
      </body>
    </html>
  );
}
```

Update the CSS to use the variable:

```css
/* In your global CSS or design tokens */
:root {
  --brand-primary: #16a34a;  /* Default fallback */
}

/* Anywhere you use the brand color: */
.sidebar-header { background: var(--brand-primary); }
.btn-primary { background: var(--brand-primary); }
```

---

## Step 8: Product-Aware Landing Page

### File: `apps/web/src/app/(marketing)/page.tsx` [MODIFY]

Make the public landing page dynamic based on product:

```typescript
import { getCurrentProduct } from '@/products/registry';

export default function LandingPage() {
  const product = getCurrentProduct();

  return (
    <main>
      <section className="hero">
        <img src={product.branding.logo} alt={product.name} />
        <h1>{product.marketing.hero}</h1>
        <p>{product.marketing.description}</p>
        <a href="/register" className="cta-button">
          {product.marketing.ctaText || 'Get Started Free'}
        </a>
      </section>

      <section className="features">
        <h2>Features</h2>
        <ul>
          {product.marketing.features.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </section>

      <section className="pricing">
        <h2>Pricing</h2>
        {Object.entries(product.plans).map(([name, plan]) => (
          <div key={name} className="plan-card">
            <h3>{name}</h3>
            <p className="price">
              {plan.price === 0 ? 'Free' : `₹${plan.price}/month`}
            </p>
          </div>
        ))}
      </section>
    </main>
  );
}

// Dynamic metadata for SEO
export async function generateMetadata() {
  const product = getCurrentProduct();
  return {
    title: `${product.name} — ${product.tagline}`,
    description: product.marketing.description,
  };
}
```

---

## Step 9: Product-Aware AI Engine

### File: `apps/ai-engine/app/api/chat.py` [MODIFY]

Pass product context to the AI system prompt:

```python
# In the generate endpoint, when building the system prompt:

product_id = request.headers.get("x-product-id", "uzhavu")

# Load product-specific prompt override
# Option 1: From a config file
# Option 2: From the request (frontend sends it)
# Option 3: From the product config via an internal API call

if product_prompt := request.product_system_prompt:
    system_prompt = product_prompt
else:
    system_prompt = default_system_prompt

# The AI now behaves differently per product:
# - InvoiceSimple AI talks about GST and invoicing
# - FarmBook AI talks about crops and farming
# - SupportDesk AI talks about ticket management
```

---

## Step 10: Backend API — Product Scoping

### File: `apps/api/src/main.ts` [MODIFY]

Add product-aware middleware to the NestJS API:

```typescript
// Global middleware to extract product ID from request
app.use((req, res, next) => {
  req.productId = req.headers['x-product-id'] || 'uzhavu';
  next();
});
```

### Endpoint filtering (optional, for strict isolation):

```typescript
// In controllers, check if the requested feature belongs to this product
@UseGuards(ProductGuard)  // Verifies the endpoint's app is in the product's app list
@Get('invoices')
async listInvoices() { ... }
```

This is **optional** — the frontend already hides unavailable features. Backend filtering adds defense-in-depth but isn't required for MVP.

---

## Deployment

### Option A: Single Deploy, Multiple Domains (Simplest)

```nginx
# nginx.conf — route all domains to the same app
server {
    server_name invoicesimple.in farmbook.in app.uzhavu.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;  # Middleware reads this
    }
}
```

- ONE server, ONE deployment
- Middleware detects domain → sets product
- All products share same database (multi-tenant by orgId)

### Option B: Separate Deploy Per Product (Isolation)

```yaml
# docker-compose.yml
services:
  invoice-simple:
    build: .
    environment:
      - PRODUCT_ID=invoice-simple
      - NEXT_PUBLIC_APP_NAME=InvoiceSimple
    ports: ["3001:3000"]

  farm-book:
    build: .
    environment:
      - PRODUCT_ID=farm-book
      - NEXT_PUBLIC_APP_NAME=FarmBook
    ports: ["3002:3000"]
```

- Same image, different env var
- Can use separate databases if needed
- Better isolation, slightly more resources

### Option C: Vercel (Easiest for SaaS)

```json
// vercel.json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/" }
  ]
}
```

Add each domain in Vercel dashboard → middleware handles the rest.

---

## Testing

### How to test locally:

```bash
# Test as InvoiceSimple
# Add to /etc/hosts (or C:\Windows\System32\drivers\etc\hosts):
# 127.0.0.1 invoice.localhost

# Then visit: http://invoice.localhost:3000
# Middleware maps "invoice.localhost:3000" → product "invoice-simple"
```

Or use the `PRODUCT_ID` env var:

```bash
PRODUCT_ID=invoice-simple pnpm dev
# Now localhost:3000 shows InvoiceSimple
```

### Verification checklist per product:

- [ ] Landing page shows correct branding, name, features, pricing
- [ ] Login/register works
- [ ] Dashboard sidebar shows ONLY the product's apps
- [ ] Other app routes return 404 or redirect to dashboard
- [ ] AI assistant uses product-specific personality
- [ ] SEO metadata (title, description) is product-specific

---

## Adding a New Product (After Setup)

### Time: ~30 minutes

1. Create `apps/web/src/products/<product-id>.ts` (copy template, change values)
2. Import in `products/registry.ts` and add to `ALL_PRODUCTS`
3. Add logo to `public/products/<product-id>/logo.svg`
4. Add domain to DNS → point to your server
5. Add domain to nginx config (if using Option A) or Vercel dashboard
6. Done. New product is live.

### Template for new products:

```typescript
// products/<product-id>.ts — COPY THIS TEMPLATE
import type { ProductConfig } from '@/types/product';

export const product: ProductConfig = {
  id: '<product-id>',
  name: '<ProductName>',
  tagline: '<one-line tagline>',
  domain: '<productname>.in',
  aliasDomains: ['<alias>.localhost:3000'],
  
  apps: ['<app1>', '<app2>'],  // Pick from: inventory, sales, invoicing, support, tasks
  
  plans: {
    free: {
      price: 0,
      limits: { /* ... */ },
      apps: ['<app1>'],
    },
    pro: {
      price: 299,
      limits: { /* ... */ },
      apps: ['<app1>', '<app2>'],
    },
  },
  
  branding: {
    logo: '/products/<product-id>/logo.svg',
    primaryColor: '#<hex>',
  },
  
  features: {
    ai_assistant: true,
    voice_input: false,
    knowledge_base: false,
    webhooks: false,
    api_access: false,
  },
  
  marketing: {
    hero: '<Headline>',
    description: '<Description>',
    features: ['Feature 1', 'Feature 2', 'Feature 3'],
  },
};
```

---

## File Summary

| File | Action | Purpose |
|:-----|:-------|:--------|
| `src/types/product.ts` | **[NEW]** | ProductConfig type definition |
| `src/products/uzhavu.ts` | **[NEW]** | Full platform product (default) |
| `src/products/invoice-simple.ts` | **[NEW]** | First standalone product |
| `src/products/registry.ts` | **[NEW]** | Product discovery + domain resolution |
| `src/hooks/useProduct.ts` | **[NEW]** | Client-side product access hook |
| `src/middleware.ts` | **[MODIFY]** | Add domain → product detection |
| `src/platform/registry.ts` | **[MODIFY]** | Filter apps by product |
| `src/components/AppSidebar.tsx` | **[MODIFY]** | Product branding (logo, name) |
| `src/app/layout.tsx` | **[MODIFY]** | Product theme (CSS vars, title, favicon) |
| `src/app/(marketing)/page.tsx` | **[MODIFY]** | Dynamic landing page per product |

**Total new files: 5 | Modified files: 5 | Estimated effort: 1-2 days**

---

*Generated: 05 Jul 2026*
*For: uzhavu.race monorepo*
*Architecture ref: APP_ARCHITECTURE.md*
