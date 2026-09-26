import { kiaraApi } from "@/lib/api/server-client";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  return kiaraApi(
    `/v1/competition/instagram/connection/${encodeURIComponent(sessionId)}/input`,
    { method: "POST", body: await request.text() },
  );
}

