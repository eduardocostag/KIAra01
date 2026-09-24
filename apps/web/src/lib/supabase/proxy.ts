import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"
import { supabaseConfig } from "./config"

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
  await supabase.auth.getClaims()
  return response
}
