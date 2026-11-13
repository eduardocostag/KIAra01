"use client"

import { createContext, useContext, type ReactNode } from "react"

const AdminAccessContext = createContext(false)

export function AdminAccessProvider({ allowed, children }: { allowed: boolean; children: ReactNode }) {
  return <AdminAccessContext.Provider value={allowed}>{children}</AdminAccessContext.Provider>
}

export function AdminOnly({ children }: { children: ReactNode }) {
  return useContext(AdminAccessContext) ? children : null
}
