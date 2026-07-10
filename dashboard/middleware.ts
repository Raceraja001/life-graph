/**
 * Next.js middleware — route protection.
 *
 * Runs on every request BEFORE the page renders (edge runtime).
 * If the user has no credentials in cookies/localStorage we can't
 * check localStorage from middleware (server-side), so we use a
 * simple cookie `lg_authed=1` that the login page sets on success.
 *
 * Protected routes redirect → /login
 * /login when already authed redirects → /
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/api/webhooks"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths and static assets
  if (
    PUBLIC_PATHS.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/icons") ||
    pathname === "/manifest.json" ||
    pathname === "/sw.js" ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  // Check auth cookie
  const authed = request.cookies.get("lg_authed")?.value === "1";

  if (!authed) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on all routes except Next.js internals
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
