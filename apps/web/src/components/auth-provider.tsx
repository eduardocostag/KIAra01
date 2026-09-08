"use client";
import { ClerkProvider } from "@clerk/nextjs";
import type { AuthMode } from "@/lib/auth-config";

export function AuthProvider({ children, mode }: { children: React.ReactNode; mode: AuthMode }) {
  if (mode === "demo") {
    return <><div role="status" className="fixed inset-x-0 top-0 z-[100] bg-amber-300 px-4 py-2 text-center text-xs font-bold tracking-wide text-amber-950 shadow-sm">MODO DEMONSTRAÇÃO — autenticação e dados reais estão desativados</div><div className="pt-8">{children}</div></>;
  }
  return <ClerkProvider>{children}</ClerkProvider>;
}
