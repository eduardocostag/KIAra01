const truthyValues = new Set(["1", "true", "yes"]);

export type AuthMode = "clerk" | "demo";

export function resolveAuthMode(environment: NodeJS.ProcessEnv = process.env): AuthMode {
  const demoRequested = truthyValues.has((environment.NEXT_PUBLIC_KIARA_DEMO_MODE ?? "").trim().toLowerCase());
  const hasPublishableKey = Boolean(environment.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());
  const hasSecretKey = Boolean(environment.CLERK_SECRET_KEY?.trim());
  // Next sets NODE_ENV=production while compiling. NEXT_PHASE lets a local demo
  // build complete, while the resulting production server still fails closed.
  const isProductionBuild = environment.NEXT_PHASE === "phase-production-build";
  const isProduction =
    environment.VERCEL_ENV === "production" ||
    environment.KIARA_DEPLOYMENT_ENV === "production" ||
    (environment.NODE_ENV === "production" && !isProductionBuild);

  if (isProduction && demoRequested) throw new Error("NEXT_PUBLIC_KIARA_DEMO_MODE is forbidden in production.");
  if (hasPublishableKey !== hasSecretKey) {
    throw new Error("Clerk configuration is incomplete: provide both publishable and secret keys.");
  }
  if (hasPublishableKey && hasSecretKey) return "clerk";
  if (!isProduction && demoRequested) return "demo";
  throw new Error("Authentication is not configured. Configure Clerk, or explicitly set NEXT_PUBLIC_KIARA_DEMO_MODE=true outside production.");
}

export const isDemoAuth = () => resolveAuthMode() === "demo";
