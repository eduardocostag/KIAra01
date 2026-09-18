export function SourceMark({ kind }: { kind: "maps" | "instagram" | "facebook" | "web" }) {
  if (kind === "maps") return <svg viewBox="0 0 24 24" className="size-full" aria-hidden="true">
    <defs><linearGradient id="kiara-maps-mark" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#28ae68" /><stop offset=".42" stopColor="#41b7ef" /><stop offset=".66" stopColor="#f7c948" /><stop offset="1" stopColor="#e84e59" /></linearGradient></defs>
    <path d="M12 1.8a8 8 0 0 0-8 8c0 5.5 8 12.4 8 12.4s8-6.9 8-12.4a8 8 0 0 0-8-8Z" fill="url(#kiara-maps-mark)" />
    <circle cx="12" cy="9.8" r="3.3" fill="#fff" />
  </svg>
  if (kind === "instagram") return <svg viewBox="0 0 24 24" className="size-full" aria-hidden="true">
    <defs><linearGradient id="kiara-instagram-mark" x1="0" x2="1" y1="1" y2="0"><stop stopColor="#f6ad61" /><stop offset=".45" stopColor="#df4ab2" /><stop offset="1" stopColor="#6c4ff9" /></linearGradient></defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#kiara-instagram-mark)" />
    <rect x="5.2" y="5.2" width="13.6" height="13.6" rx="4" fill="none" stroke="#fff" strokeWidth="1.8" />
    <circle cx="12" cy="12" r="3.1" fill="none" stroke="#fff" strokeWidth="1.8" />
    <circle cx="17.1" cy="6.9" r="1.1" fill="#fff" />
  </svg>
  if (kind === "facebook") return <svg viewBox="0 0 24 24" className="size-full" aria-hidden="true">
    <defs><linearGradient id="kiara-facebook-mark" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#1877f2" /><stop offset="1" stopColor="#0b55b8" /></linearGradient></defs>
    <circle cx="12" cy="12" r="11" fill="url(#kiara-facebook-mark)" />
    <path d="M13.5 12h2.2l.35-2.8H13.5V7.5c0-.75.25-1.4 1.4-1.4H16V3.5c-.25-.05-1.15-.1-2.2-.1-2.2 0-3.8 1.35-3.8 3.9V9.2H7.5V12H10v8h3.5v-8Z" fill="#fff" />
  </svg>
  return <svg viewBox="0 0 24 24" className="size-full" aria-hidden="true">
    <defs><linearGradient id="kiara-web-mark" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#42c5fa" /><stop offset="1" stopColor="#216bd5" /></linearGradient></defs>
    <circle cx="12" cy="12" r="11" fill="url(#kiara-web-mark)" />
    <circle cx="12" cy="12" r="7" fill="none" stroke="#fff" strokeWidth="1.4" />
    <path d="M5 12h14M12 5c-2.2 2-3.2 4.3-3.2 7s1 5 3.2 7c2.2-2 3.2-4.3 3.2-7S14.2 7 12 5Z" fill="none" stroke="#fff" strokeWidth="1.3" />
  </svg>
}
