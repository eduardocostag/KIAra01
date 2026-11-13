/** Text and voice helpers for Kiara's spoken replies (pure, testable). */

// Natural female pt-BR voices first (Edge/Windows "Natural", Google), never the default male ones.
const FEMININE = [/francisca/i, /thalita/i, /brenda/i, /elza/i, /leila/i, /yara/i, /manuela/i, /giovanna/i, /leticia/i, /luciana/i, /maria/i, /google português do brasil/i, /female|feminina/i]
const MASCULINE = /daniel|antonio|ant[oô]nio|fabio|f[aá]bio|donato|humberto|julio|j[uú]lio|nicolau|valerio|val[eé]rio|masculin|\bmale\b/i

type Voice = { name: string; lang: string }

/** Best female pt-BR voice, preferring neural "Natural/Online" ones; male voices only as a last resort. */
export function pickFeminineVoice<T extends Voice>(all: readonly T[]): T | undefined {
  const voices = all.filter((voice) => voice.lang.toLowerCase().replace("_", "-").startsWith("pt-br"))
  const score = (voice: Voice) => {
    const rank = FEMININE.findIndex((pattern) => pattern.test(voice.name))
    return (rank === -1 ? 100 : rank) - (/natural|online|neural/i.test(voice.name) ? 50 : 0) + (MASCULINE.test(voice.name) ? 1000 : 0)
  }
  return voices.sort((left, right) => score(left) - score(right))[0]
}

/** Splits a reply into sentences for streaming speech; the first chunk stays short so audio starts fast. */
export function speechChunks(text: string): string[] {
  const sentences = text.match(/[^.!?…]+[.!?…]+["')\]]*\s*|[^.!?…]+$/g)?.map((item) => item.trim()).filter(Boolean) ?? []
  const chunks: string[] = []
  for (const sentence of sentences) {
    const last = chunks.at(-1)
    // Join very short sentences ("Oi!") with the next one; keep later chunks up to ~220 characters.
    if (last !== undefined && (last.length < 12 || (chunks.length > 1 && last.length + sentence.length < 220))) chunks[chunks.length - 1] = `${last} ${sentence}`
    else chunks.push(sentence)
  }
  return chunks.length ? chunks : [text]
}
