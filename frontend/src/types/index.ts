/** Shared types for the converter UI. Mirrors the backend schemas. */

export type Category = "document" | "image" | "archive";

export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface FormatInfo {
  extension: string;
  label: string;
  category: Category;
  mime_types: string[];
}

export interface CategoryInfo {
  id: Category;
  label: string;
  description: string;
  formats: FormatInfo[];
}

export interface FormatsPayload {
  categories: CategoryInfo[];
  conversions: Record<string, string[]>;
  max_file_size_mb: number;
  external_tools: Record<string, boolean>;
}

export interface UploadedFile {
  id: string;
  original_name: string;
  extension: string;
  category: Category | null;
  size_bytes: number;
  mime_type: string | null;
  label: string | null;
  available_formats: string[];
  uploaded_at: string;
}

export interface ConversionJob {
  id: string;
  status: JobStatus;
  progress: number;
  stage: string | null;
  source_name: string | null;
  source_extension: string | null;
  target_extension: string | null;
  output_name: string | null;
  output_size_bytes: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiEnvelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  code: string | null;
}

/** Every error the UI can show, with the message the user should read. */
export type UserFacingError =
  | "unsupported_format"
  | "file_too_large"
  | "file_not_found"
  | "conversion_failed"
  | "dependency_missing"
  | "validation_error"
  | "network_error"
  | "server_error"
  | "unknown";

export const ERROR_MESSAGES: Record<UserFacingError, string> = {
  unsupported_format: "Sorry, this file format is not supported.",
  file_too_large: "Your file exceeds the maximum allowed size.",
  file_not_found:
    "This file is no longer available. It may have expired, so please upload it again.",
  conversion_failed: "We couldn't convert this file. Please try again.",
  dependency_missing:
    "This conversion needs a tool that isn't installed on the server right now.",
  validation_error: "Something about that file didn't look right. Please try another one.",
  network_error: "Can't reach the conversion server. Is the backend running?",
  server_error: "Something went wrong. Please try again later.",
  unknown: "Something went wrong. Please try again later.",
};

export type WorkflowState =
  | "idle"
  | "uploading"
  | "uploaded"
  | "converting"
  | "completed"
  | "failed";
