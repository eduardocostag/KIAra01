import { kiaraApi } from "@/lib/api/server-client";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  return kiaraApi(
    `/v1/competition/instagram/connection/${encodeURIComponent(sessionId)}/screenshot`,
  );
}

