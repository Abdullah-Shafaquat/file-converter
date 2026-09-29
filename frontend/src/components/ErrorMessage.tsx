"use client";

import { AlertIcon } from "@/components/icons";
import { ERROR_MESSAGES, type UserFacingError } from "@/types";

interface ErrorMessageProps {
  code: UserFacingError;
  onRetry?: () => void;
  retryLabel?: string;
}

/** Friendly, non-technical error surface. Server internals are never shown. */
export function ErrorMessage({ code, onRetry, retryLabel }: ErrorMessageProps) {
  const message = ERROR_MESSAGES[code] ?? ERROR_MESSAGES.unknown;

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4"
    >
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-100 text-red-600">
        <AlertIcon className="h-4.5 w-4.5" />
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-red-900">Conversion failed</p>
        <p className="mt-0.5 text-sm leading-relaxed text-red-700">{message}</p>

        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-red-800
              ring-1 ring-inset ring-red-200 transition-colors hover:bg-red-100
              focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700"
          >
            {retryLabel ?? "Try again"}
          </button>
        )}
      </div>
    </div>
  );
}
