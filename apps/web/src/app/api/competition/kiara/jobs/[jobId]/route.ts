import { kiaraApi } from "@/lib/api/server-client";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  return kiaraApi(`/v1/competition/kiara/jobs/${encodeURIComponent(jobId)}`);
}
