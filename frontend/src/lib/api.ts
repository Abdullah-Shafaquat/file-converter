/**
 * Central API client. Every network call the app makes lives here.
 *
 * Backend is the source of truth for the conversion matrix - nothing about
 * supported formats is hard-coded on the frontend.
 */

import type {
  ApiEnvelope,
  ConversionJob,
  FormatsPayload,
  UploadedFile,
  UserFacingError,
} from "@/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ?? "http://localhost:8000";

const REQUEST_TIMEOUT_MS = 120_000;

class ApiError extends Error {
  readonly code: UserFacingError;
  readonly status: number;

  constructor(code: UserFacingError, message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function normaliseCode(code: string | null, status: number): UserFacingError {
  const known: UserFacingError[] = [
    "unsupported_format",
    "file_too_large",
    "file_not_found",
    "conversion_failed",
    "dependency_missing",
    "validation_error",
    "server_error",
  ];
  if (code && (known as string[]).includes(code)) {
    return code as UserFacingError;
  }
  if (status === 413) return "file_too_large";
  if (status === 404) return "file_not_found";
  if (status >= 500) return "server_error";
  if (status >= 400) return "validation_error";
  return "server_error";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api${path}`, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timer);
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("network_error", "The request timed out.");
    }
    throw new ApiError(
      "network_error",
      "Can't reach the conversion server. Is the backend running?",
    );
  } finally {
    clearTimeout(timer);
  }

  let body: ApiEnvelope<T> | null = null;
  const text = await response.text();
  if (text) {
    try {
      body = JSON.parse(text) as ApiEnvelope<T>;
    } catch {
      throw new ApiError("server_error", "The server returned an unreadable response.");
    }
  }

  if (!response.ok || !body?.success) {
    throw new ApiError(
      normaliseCode(body?.code ?? null, response.status),
      body?.error ?? "Something went wrong. Please try again later.",
      response.status,
    );
  }

  return body.data as T;
}

export const api = {
  health(): Promise<Record<string, unknown>> {
    return request<Record<string, unknown>>("/health");
  },

  formats(): Promise<FormatsPayload> {
    return request<FormatsPayload>("/formats");
  },

  async upload(file: File): Promise<UploadedFile> {
    const body = new FormData();
    body.append("file", file);
    return request<UploadedFile>("/upload", { method: "POST", body });
  },

  startConversion(fileId: string, targetFormat: string): Promise<ConversionJob> {
    return request<ConversionJob>("/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: fileId, target_format: targetFormat }),
    });
  },

  getConversion(jobId: string): Promise<ConversionJob> {
    return request<ConversionJob>(`/conversions/${encodeURIComponent(jobId)}`);
  },

  deleteFile(fileId: string): Promise<{ id: string; deleted: boolean }> {
    return request(`/files/${encodeURIComponent(fileId)}`, { method: "DELETE" });
  },

  deleteConversion(jobId: string): Promise<{ id: string; deleted: boolean }> {
    return request(`/conversions/${encodeURIComponent(jobId)}`, { method: "DELETE" });
  },

  /**
   * Downloads through fetch rather than a plain link so the request goes
   * through CORS and errors surface as ApiError instead of a blank tab.
   */
  async download(jobId: string, fileName: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/download/${encodeURIComponent(jobId)}`,
    );
    if (!response.ok) {
      throw new ApiError(
        response.status === 404 ? "file_not_found" : "server_error",
        "The converted file could not be downloaded.",
        response.status,
      );
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    // Revoke on the next tick so Safari has time to start the download.
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  },
};

export { ApiError };
