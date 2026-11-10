import "server-only"
import { lookup } from "node:dns"
import { request as httpsRequest } from "node:https"
import { request as httpRequest } from "node:http"
import { isIP, type LookupFunction } from "node:net"

export function publicAddress(address: string): boolean {
  if (isIP(address) === 4) {
    const [a, b, c] = address.split(".").map(Number)
    return !(a === 0 || a === 10 || a === 127 || a >= 224 || (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && (b === 168 || b === 0 || (b === 88 && c === 99))) || (a === 198 && (b === 18 || b === 19 || (b === 51 && c === 100))) || (a === 203 && b === 0 && c === 113))
  }
  return isIP(address) === 6 && /^[23]/.test(address) && !/^2001:0?db8:/i.test(address)
}

export async function postizTransport(target: URL, init: RequestInit, headers: Headers, timeout = 30000) {
  const localAllowed = process.env.NODE_ENV === "development" && ["localhost", "127.0.0.1", "[::1]"].includes(target.hostname)
  const permitted = (address: string) => publicAddress(address) || (localAllowed && ["127.0.0.1", "::1"].includes(address))
  if (target.username || target.password || target.hash || (target.protocol !== "https:" && !(localAllowed && target.protocol === "http:"))) throw new Error("Destino Postiz inválido.")
  if (isIP(target.hostname.replace(/^\[|\]$/g, "")) && !permitted(target.hostname.replace(/^\[|\]$/g, ""))) throw new Error("Destino Postiz privado recusado.")
  const pinnedLookup: LookupFunction = (hostname, options, callback) => {
    lookup(hostname, { all: true }, (error, addresses) => {
      if (error || !addresses.length || addresses.some(item => !permitted(item.address))) return callback(error ?? new Error("Destino Postiz privado recusado."), "", 0)
      if (options.all) callback(null, addresses)
      else callback(null, addresses[0].address, addresses[0].family)
    })
  }
  // Request encodes FormData/Blob without forwarding browser authentication headers.
  const encoded = new Request(target, { method: init.method ?? "GET", headers, ...(init.body != null ? { body: init.body } : {}) })
  const data = init.body != null ? Buffer.from(await encoded.arrayBuffer()) : undefined
  if (data && data.length > 53_000_000) throw new Error("Arquivo Postiz excede o limite.")
  return new Promise<{ ok: boolean; status: number; text: () => Promise<string> }>((resolve, reject) => {
    const request = (target.protocol === "https:" ? httpsRequest : httpRequest)(target, { method: init.method ?? "GET", headers: Object.fromEntries(encoded.headers), lookup: pinnedLookup, agent: false }, response => {
      const status = response.statusCode ?? 502
      if (status >= 300 && status < 400) { response.destroy(); request.destroy(); reject(new Error("Redirecionamento Postiz recusado.")); return }
      const chunks: Buffer[] = []
      let size = 0
      response.on("data", (chunk: Buffer) => { size += chunk.length; if (size > 8_000_000) { response.destroy(); request.destroy(); reject(new Error("Resposta Postiz excede o limite.")) } else chunks.push(chunk) })
      response.on("error", reject)
      response.on("end", () => resolve({ ok: status >= 200 && status < 300, status, text: async () => Buffer.concat(chunks).toString("utf8") }))
    })
    const timer = setTimeout(() => request.destroy(new DOMException("Postiz demorou além do limite.", "TimeoutError")), timeout)
    request.on("error", reject)
    request.on("close", () => clearTimeout(timer))
    request.end(data)
  })
}
