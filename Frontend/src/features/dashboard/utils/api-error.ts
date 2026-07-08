interface ErrorPayload {
  detail?: unknown;
  message?: unknown;
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

export async function readApiError(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as unknown;
      const message = messageFromPayload(payload);
      if (message) {
        return message;
      }
    } catch {
      return `Request failed with HTTP ${response.status}`;
    }
  }

  const text = await response.text();
  return text || `Request failed with HTTP ${response.status}`;
}
