export function supabaseConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()
  const publishableKey = (
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
    ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  )?.trim()

  if (!url || !publishableKey) {
    throw new Error("Supabase Auth não está configurado neste ambiente.")
  }

  return { url, publishableKey }
}
