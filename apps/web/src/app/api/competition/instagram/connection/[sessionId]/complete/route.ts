import { kiaraApi } from "@/lib/api/server-client";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  return kiaraApi(
    `/v1/competition/instagram/connection/${encodeURIComponent(sessionId)}/complete`,
    { method: "POST", body: "{}" },
  );
}

