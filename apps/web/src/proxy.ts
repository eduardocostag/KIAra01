import { clerkMiddleware } from "@clerk/nextjs/server";

// Authorization belongs to each protected resource. The proxy only makes the
// verified Clerk session available to those layouts and route handlers.
export default clerkMiddleware();

export const config = { matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)", "/(api|trpc)(.*)"] };
