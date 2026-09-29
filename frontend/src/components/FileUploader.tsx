"use client";

import { useCallback, useId, useRef, useState } from "react";

import { CloseIcon, UploadIcon } from "@/components/icons";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { formatLimit } from "@/lib/format";

interface FileUploaderProps {
  onFileSelected: (file: File) => void;
  maxSizeBytes: number;
  isBusy: boolean;
  acceptedExtensions: string[];
}

const ACCEPT_ATTRIBUTE_CACHE = new Map<string, string>();

function buildAcceptAttribute(extensions: string[]): string {
  const key = extensions.join(",");
  const cached = ACCEPT_ATTRIBUTE_CACHE.get(key);
  if (cached) return cached;
  const value = extensions.map((extension) => `.${extension}`).join(",");
  ACCEPT_ATTRIBUTE_CACHE.set(key, value);
  return value;
}

/**
 * Drag-and-drop + click-to-browse uploader.
 *
 * Accessible as a button: it is focusable, responds to Enter/Space, and the
 * hidden native input is labelled. Client-side checks here are a fast
 * courtesy only - the backend re-validates everything.
 */
export function FileUploader({
  onFileSelected,
  maxSizeBytes,
  isBusy,
  acceptedExtensions,
}: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  const [localError, setLocalError] = useState<string | null>(null);
  const describedBy = useId();

  const validate = useCallback(
    (file: File): string | null => {
      if (file.size === 0) {
        return "This file is empty. Please choose a file with content.";
      }
      if (file.size > maxSizeBytes) {
        return `This file is ${formatLimit(file.size)}. The limit is ${formatLimit(maxSizeBytes)}.`;
      }
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (acceptedExtensions.length > 0 && !acceptedExtensions.includes(extension)) {
        return "Sorry, this file format is not supported.";
      }
      return null;
    },
    [acceptedExtensions, maxSizeBytes],
  );

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;

      const problem = validate(file);
      if (problem) {
        setLocalError(problem);
        return;
      }
      setLocalError(null);
      onFileSelected(file);
    },
    [onFileSelected, validate],
  );

  const openPicker = useCallback(() => {
    if (!isBusy) inputRef.current?.click();
  }, [isBusy]);

  // Counter-based enter/leave so nested elements don't flicker the state.
  const onDragEnter = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragCounter.current += 1;
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragCounter.current = Math.max(0, dragCounter.current - 1);
    if (dragCounter.current === 0) setIsDragging(false);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      dragCounter.current = 0;
      setIsDragging(false);
      if (isBusy) return;
      handleFiles(event.dataTransfer?.files ?? null);
    },
    [handleFiles, isBusy],
  );

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openPicker();
      }
    },
    [openPicker],
  );

  return (
    <div className="w-full">
      <div
        role="button"
        tabIndex={isBusy ? -1 : 0}
        aria-disabled={isBusy}
        aria-describedby={describedBy}
        aria-label="Upload a file: drag and drop, or press Enter to browse"
        onClick={openPicker}
        onKeyDown={onKeyDown}
        onDragEnter={onDragEnter}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`group relative flex cursor-pointer flex-col items-center justify-center
          rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-all duration-200
          focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-900
          sm:px-10 sm:py-16
          ${
            isDragging
              ? "scale-[1.01] border-zinc-900 bg-zinc-50"
              : "border-zinc-300 bg-white hover:border-zinc-400 hover:bg-zinc-50/60"
          }
          ${isBusy ? "pointer-events-none opacity-60" : ""}`}
      >
        <span
          className={`flex h-14 w-14 items-center justify-center rounded-2xl transition-colors ${
            isDragging ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-700"
          }`}
        >
          {isBusy ? (
            <LoadingSpinner size="md" label="Uploading" />
          ) : (
            <UploadIcon className="h-6 w-6" />
          )}
        </span>

        <p className="mt-5 text-base font-semibold text-zinc-900 sm:text-lg">
          {isBusy ? "Uploading your file…" : "Drag & drop your file here"}
        </p>

        {!isBusy && (
          <>
            <p className="mt-1.5 text-sm text-zinc-500">
              or <span className="font-medium text-zinc-900 underline underline-offset-4">choose a file</span> from your computer
            </p>
            <p className="mt-4 text-xs text-zinc-400">
              Up to {formatLimit(maxSizeBytes)} per file
            </p>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept={buildAcceptAttribute(acceptedExtensions)}
          disabled={isBusy}
          onChange={(event) => {
            handleFiles(event.target.files);
            // Allow re-selecting the same file after a validation error.
            event.target.value = "";
          }}
        />
      </div>

      <div id={describedBy} aria-live="polite" className="min-h-0">
        {localError && (
          <p className="mt-3 flex items-start gap-1.5 text-sm text-red-600">
            <CloseIcon className="mt-0.5 h-4 w-4 shrink-0" />
            {localError}
          </p>
        )}
      </div>
    </div>
  );
}
