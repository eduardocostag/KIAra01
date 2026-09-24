"use client"

import { createBrowserClient } from "@supabase/ssr"
import { supabaseConfig } from "./config"

export function createClient() {
  const { url, publishableKey } = supabaseConfig()
  return createBrowserClient(url, publishableKey)
}
