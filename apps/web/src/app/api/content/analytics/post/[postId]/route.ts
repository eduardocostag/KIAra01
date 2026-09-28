import { requireContentAdmin } from "@/lib/postiz/admin";

export async function GET() {
  const denied = await requireContentAdmin();
  if (denied) return denied;
  return Response.json({ error: { code: "social_analytics_not_available", message: "Analytics estarão disponíveis com os providers oficiais da Kiara Social API." } }, { status: 501 });
}
