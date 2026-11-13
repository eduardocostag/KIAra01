import type { Metadata } from "next"
import { ApprovalCenter } from "@/components/approvals/approval-center"

export const metadata: Metadata = { title: "Central de aprovações · Kiara" }

export default function ApprovalsPage() {
  return <ApprovalCenter />
}
