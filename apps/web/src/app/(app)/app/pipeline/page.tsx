import { redirect } from "next/navigation"

export default async function PipelinePage() {
  redirect("/app/inbox?view=contacts")
}
