import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"
import { supabaseConfig } from "./config"
import { moduleForPage, modulesFor } from "@/lib/modules"

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request })
  const { url, publishableKey } = supabaseConfig()
  const supabase = createServerClient(url, publishableKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet, headers) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
        response = NextResponse.next({ request })
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options))
        Object.entries(headers).forEach(([name, value]) => response.headers.set(name, value))
      },
    },
  })

  // This verified call must happen immediately after client creation so a
  // near-expiry token is refreshed before any page or route handler runs.
  const { data } = await supabase.auth.getClaims()
  const claims = data?.claims
  const pageModule = moduleForPage(request.nextUrl.pathname)
  if (pageModule && typeof claims?.sub === "string"
      && !modulesFor(typeof claims.email === "string" ? claims.email : null, claims.app_metadata).includes(pageModule)) {
    // A module the administrator did not give this account (typed or old link): back to the module selector.
    const target = request.nextUrl.clone()
    target.pathname = "/app"
    target.search = ""
    target.hash = ""
    const redirect = NextResponse.redirect(target)
    response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie))
    return redirect
  }
  return response
}
