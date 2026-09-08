import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { resolveAuthMode } from "@/lib/auth-config";

// Authorization belongs to each protected resource. The proxy only makes the
// verified Clerk session available to those layouts and route handlers.
const clerkProxy = clerkMiddleware();

function demoProxy() {
  const response = NextResponse.next();
  response.headers.set("x-kiara-auth-mode", "demo");
  return response;
}

export default resolveAuthMode() === "demo" ? demoProxy : clerkProxy;

export const config = { matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)", "/(api|trpc)(.*)"] };
