import { dateRange, integrations, noStore, posts, withPostizAdmin } from "../_shared";

export async function GET(request: Request) {
  return withPostizAdmin(async () => {
    const range = dateRange(request);
    const [channels, items] = await Promise.all([integrations(), posts(range)]);
    return Response.json({ integrations: channels, posts: items, ...range }, { headers: noStore });
  });
}
