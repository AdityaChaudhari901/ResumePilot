import type { ValidationWarning } from "@/features/dashboard/types";

interface ErrorPayload {
  detail?: unknown;
  message?: unknown;
}

export interface ApiFieldError {
  field: string;
  message: string;
}

export interface ApiProblem {
  status: number;
  message: string;
  warnings: ValidationWarning[];
  fieldErrors: ApiFieldError[];
  retryAfter?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function messageFromPayload(payload: unknown): string | null {
  if (!isRecord(payload)) {
    return null;
  }

  const typedPayload = payload as ErrorPayload;
  if (typeof typedPayload.detail === "string") {
    return typedPayload.detail;
  }

  if (isRecord(typedPayload.detail) && typeof typedPayload.detail.message === "string") {
    return typedPayload.detail.message;
  }

  if (Array.isArray(typedPayload.detail) && typedPayload.detail.length > 0) {
    const firstError = typedPayload.detail[0];
    if (isRecord(firstError) && typeof firstError.msg === "string") {
      return firstError.msg;
    }
  }

  if (typeof typedPayload.message === "string") {
    return typedPayload.message;
  }

  return null;
}

function warningsFromPayload(payload: unknown): ValidationWarning[] {
  if (!isRecord(payload) || !isRecord(payload.detail) || !Array.isArray(payload.detail.warnings)) {
    return [];
  }

  return payload.detail.warnings.flatMap((warning) => {
    if (
      !isRecord(warning) ||
      typeof warning.code !== "string" ||
      typeof warning.message !== "string"
    ) {
      return [];
    }
    const severity = warning.severity;
    return [
      {
        code: warning.code,
        evidence_ids: Array.isArray(warning.evidence_ids)
          ? warning.evidence_ids.filter((item): item is string => typeof item === "string")
          : [],
        message: warning.message,
        ...(severity === "pass" || severity === "warn" || severity === "block"
          ? { severity }
          : {})
      }
    ];
  });
}

function fieldErrorsFromPayload(payload: unknown): ApiFieldError[] {
  if (!isRecord(payload) || !Array.isArray(payload.detail)) {
    return [];
  }

  return payload.detail.flatMap((error) => {
    if (!isRecord(error) || typeof error.msg !== "string") {
      return [];
    }
    const location = Array.isArray(error.loc)
      ? error.loc.filter((item): item is string | number =>
          typeof item === "string" || typeof item === "number"
        )
      : [];
    return [{ field: location.slice(1).join(".") || "request", message: error.msg }];
  });
}

function retryAfterSeconds(response: Response): number | undefined {
  const value = response.headers.get("retry-after");
  if (!value) {
    return undefined;
  }
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

export async function readApiProblem(response: Response): Promise<ApiProblem> {
  const fallbackMessage = `Request failed with HTTP ${response.status}`;
  const contentType = response.headers.get("content-type") ?? "";
  const base = {
    fieldErrors: [] as ApiFieldError[],
    message: fallbackMessage,
    retryAfter: retryAfterSeconds(response),
    status: response.status,
    warnings: [] as ValidationWarning[]
  };

  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as unknown;
      return {
        ...base,
        fieldErrors: fieldErrorsFromPayload(payload),
        message: messageFromPayload(payload) ?? fallbackMessage,
        warnings: warningsFromPayload(payload)
      };
    } catch {
      return base;
    }
  }

  const body = await response.text();
  return { ...base, message: body || fallbackMessage };
}

export async function readApiError(response: Response): Promise<string> {
  return (await readApiProblem(response)).message;
}
