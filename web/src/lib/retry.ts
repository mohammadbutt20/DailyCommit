// When TanStack Query should retry a failed request. A 4xx (not logged in, forbidden, not
// found, invalid) won't change on retry, so show it at once instead of after ~7 s of retries
// (e.g. opening someone else's submission: "not found" straight away). Network errors and
// 5xx are retried up to 3 times, as before.

export const MAX_RETRIES = 3;

export function shouldRetry(failureCount: number, error: unknown): boolean {
  const status = (error as { status?: unknown } | null)?.status;
  if (typeof status === "number" && status >= 400 && status < 500) return false;
  return failureCount < MAX_RETRIES;
}
