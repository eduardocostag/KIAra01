import { kiaraApi } from "@/lib/api/server-client";

export async function GET() {
  return kiaraApi("/v1/competition/instagram/connection");
}

export async function POST() {
  return kiaraApi("/v1/competition/instagram/connection", {
    method: "POST",
    body: "{}",
  });
}

export async function DELETE() {
  return kiaraApi("/v1/competition/instagram/connection", {
    method: "DELETE",
  });
}

