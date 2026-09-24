import { cookies } from "next/headers"
import { AdministratorRequiredError, AuthenticationRequiredError, requireSystemAdmin } from "@/lib/auth"
import {
  MAILERFIND_COOKIE, MAILERFIND_ISSUER, pkceChallenge, randomUrlSafe, sealOAuthState,
} from "@/lib/mailerfind/oauth"

type Registration = { client_id?: string; client_secret?: string }

export async function GET(request: Request) {
  try {
    await requireSystemAdmin()
    const origin = new URL(request.url).origin
    const redirectUri = `${origin}/api/admin/integrations/mailerfind/callback`
    const registrationResponse = await fetch(`${MAILERFIND_ISSUER}register`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        client_name: "Kiara Lead Intelligence",
        redirect_uris: [redirectUri],
        grant_types: ["authorization_code", "refresh_token"],
        response_types: ["code"],
        token_endpoint_auth_method: "client_secret_post",
      }),
      signal: AbortSignal.timeout(12_000),
    })
    const registration = await registrationResponse.json() as Registration
    if (!registrationResponse.ok || !registration.client_id) throw new Error("O MailerFind não aceitou o registro seguro da Kiara.")

    const state = randomUrlSafe()
    const verifier = randomUrlSafe(48)
    const cookieStore = await cookies()
    cookieStore.set(MAILERFIND_COOKIE, sealOAuthState({
      state, verifier, clientId: registration.client_id, clientSecret: registration.client_secret,
      redirectUri, createdAt: Date.now(),
    }), { httpOnly: true, secure: origin.startsWith("https://"), sameSite: "lax", path: "/", maxAge: 600 })

    const authorization = new URL("authorize", MAILERFIND_ISSUER)
    authorization.searchParams.set("response_type", "code")
    authorization.searchParams.set("client_id", registration.client_id)
    authorization.searchParams.set("redirect_uri", redirectUri)
    authorization.searchParams.set("scope", "mailerfind:read mailerfind:write")
    authorization.searchParams.set("state", state)
    authorization.searchParams.set("code_challenge", pkceChallenge(verifier))
    authorization.searchParams.set("code_challenge_method", "S256")
    return Response.redirect(authorization)
  } catch (error) {
    const origin = new URL(request.url).origin
    if (error instanceof AuthenticationRequiredError) return Response.redirect(`${origin}/sign-in`)
    if (error instanceof AdministratorRequiredError) return Response.json({ error: "Acesso exclusivo do administrador." }, { status: 403 })
    console.error(JSON.stringify({
      level: "error",
      event: "mailerfind.oauth_start_failed",
      error_class: error instanceof Error ? error.name : "UnknownError",
      message: error instanceof Error ? error.message.slice(0, 240) : "Falha desconhecida",
    }))
    return Response.redirect(`${origin}/app/admin?mailerfind=error`)
  }
}
