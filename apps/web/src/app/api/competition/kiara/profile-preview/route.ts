import { kiaraApi } from "@/lib/api/server-client";
export const maxDuration = 60;

export async function POST(request: Request) {
  return kiaraApi("/v1/competition/kiara/profile-preview", {
    method: "POST",
    body: await request.text(),
  });
}
