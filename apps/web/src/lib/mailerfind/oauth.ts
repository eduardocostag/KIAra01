import "server-only"

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto"

export const MAILERFIND_COOKIE = "kiara_mailerfind_oauth"
export const MAILERFIND_MCP_URL = process.env.MAILERFIND_MCP_URL?.trim() || "https://mcp.mailerfind.com/mcp"
export const MAILERFIND_ISSUER = "https://mcp.mailerfind.com/"

export type MailerFindOAuthState = {
  state: string
  verifier: string
  clientId: string
  clientSecret?: string
  redirectUri: string
  createdAt: number
}

function encryptionKey() {
  const secret = (
    process.env.MAILERFIND_OAUTH_COOKIE_SECRET
    ?? process.env.SUPABASE_SERVICE_ROLE_KEY
    ?? process.env.SUPABASE_SECRET_KEY
  )?.trim()
  if (!secret) throw new Error("A proteção temporária do OAuth não está configurada.")
  return createHash("sha256").update(secret).digest()
}

export function randomUrlSafe(bytes = 32) {
  return randomBytes(bytes).toString("base64url")
}

export function pkceChallenge(verifier: string) {
  return createHash("sha256").update(verifier).digest("base64url")
}

export function sealOAuthState(value: MailerFindOAuthState) {
  const iv = randomBytes(12)
  const cipher = createCipheriv("aes-256-gcm", encryptionKey(), iv)
  const encrypted = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()])
  return [iv, cipher.getAuthTag(), encrypted].map((part) => part.toString("base64url")).join(".")
}

export function openOAuthState(value: string): MailerFindOAuthState {
  const [ivValue, tagValue, encryptedValue] = value.split(".")
  if (!ivValue || !tagValue || !encryptedValue) throw new Error("Estado OAuth inválido.")
  const decipher = createDecipheriv("aes-256-gcm", encryptionKey(), Buffer.from(ivValue, "base64url"))
  decipher.setAuthTag(Buffer.from(tagValue, "base64url"))
  const clear = Buffer.concat([decipher.update(Buffer.from(encryptedValue, "base64url")), decipher.final()]).toString("utf8")
  return JSON.parse(clear) as MailerFindOAuthState
}
