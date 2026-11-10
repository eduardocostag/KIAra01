import { integrations, noStore, withPostizAdmin } from "../_shared";

export async function GET() {
  return withPostizAdmin(async () => Response.json(await integrations(), { headers: noStore }));
}
