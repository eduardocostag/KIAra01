import { redirect } from "next/navigation"

// Plans are hidden for now: the page and its PlanWorkspace stay in the code to come back later.
export default function PlanPage() {
  redirect("/app/leads")
}
