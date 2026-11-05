import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

// schema.ts is generated from the FastAPI OpenAPI schema (`make gen-api`). Never edit it by hand.
export type Schemas = components["schemas"];

// Same origin: Caddy routes /api to FastAPI, and the session cookie rides along.
export const api = createClient<paths>({ baseUrl: "" });

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Await an openapi-fetch call, returning its data or throwing ApiError. */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : `Request failed (${response.status})`,
    );
  }
  return data as T;
}
