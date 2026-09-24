import "server-only"

import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"
import { supabaseConfig } from "./config"

export async function createClient() {
  const cookieStore = await cookies()
  const { url, publishableKey } = supabaseConfig()

  return createServerClient(url, publishableKey, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options))
        } catch {
          // Server Components cannot write cookies. The Next.js proxy refreshes
          // the session before rendering and persists the updated cookies.
        }
      },
    },
  })
}
