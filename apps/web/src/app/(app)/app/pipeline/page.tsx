import { redirect } from "next/navigation"

export default function PipelinePage() {
  redirect("/app/inbox?view=pipeline")
}
