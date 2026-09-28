import { kiaraApi } from "@/lib/api/server-client";

export async function GET() {
  return kiaraApi("/v1/competition/overview");
}

export async function DELETE() {
  return kiaraApi("/v1/competition/analyses", { method: "DELETE" });
}
