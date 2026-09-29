"use client";

import { useMemo } from "react";

import { ConversionButton } from "@/components/ConversionButton";
import { ConversionProgress } from "@/components/ConversionProgress";
import { ConversionResult } from "@/components/ConversionResult";
import { ErrorMessage } from "@/components/ErrorMessage";
import { FilePreview } from "@/components/FilePreview";
import { FileUploader } from "@/components/FileUploader";
import { FormatSelector } from "@/components/FormatSelector";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { useConverter } from "@/hooks/useConverter";
import { findFormat } from "@/lib/format";

/**
 * The whole conversion workflow in one place. Presentational children stay
 * small and reusable; all state lives in `useConverter`.
 */
export function Converter() {
  const {
    formats,
    formatsError,
    isLoadingFormats,
    state,
    file,
    job,
    targetFormat,
    error,
    setTargetFormat,
    handleFile,
    startConversion,
    download,
    reset,
  } = useConverter();

  const acceptedExtensions = useMemo(
    () => Object.keys(formats?.conversions ?? {}),
    [formats?.conversions],
  );

  const maxSizeBytes = (formats?.max_file_size_mb ?? 100) * 1024 * 1024;

  const targetLabel = useMemo(() => {
    if (!targetFormat) return "";
    return (findFormat(formats, targetFormat)?.label ?? targetFormat).toUpperCase();
  }, [formats, targetFormat]);

  const sourceLabel = (file?.label ?? file?.extension ?? "").toUpperCase();

  const isConverting = state === "converting";
  const showUploader = state === "idle" || state === "uploading" || state === "failed";

  return (
    <section id="converter" className="scroll-mt-20">
      <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-7">
        {isLoadingFormats && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <LoadingSpinner size="lg" label="Loading supported formats" />
            <p className="mt-4 text-sm text-zinc-500">Loading supported formats…</p>
          </div>
        )}

        {!isLoadingFormats && formatsError && !file && (
          <div
            role="alert"
            className="flex flex-col items-center justify-center rounded-2xl border border-amber-200 bg-amber-50 px-6 py-14 text-center"
          >
            <p className="text-sm font-medium text-amber-900">
              Can't load the format list
            </p>
            <p className="mt-2 max-w-sm text-sm leading-relaxed text-amber-800">
              The converter backend isn&apos;t responding. Start it with{" "}
              <code className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-xs">
                uvicorn app.main --reload --port 8000
              </code>{" "}
              in the <code className="font-mono text-xs">backend</code> folder, then reload.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-5 rounded-lg bg-amber-900 px-4 py-2 text-sm font-medium text-white
                transition-colors hover:bg-amber-800
                focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-900"
            >
              Reload page
            </button>
          </div>
        )}

        {!isLoadingFormats && !formatsError && (
          <div className="space-y-5">
            {showUploader && (
              <FileUploader
                onFileSelected={handleFile}
                maxSizeBytes={maxSizeBytes}
                isBusy={state === "uploading"}
                acceptedExtensions={acceptedExtensions}
              />
            )}

            {error && state === "failed" && (
              <ErrorMessage
                code={error}
                onRetry={file ? () => void startConversion() : undefined}
                retryLabel={file ? "Try this file again" : undefined}
              />
            )}

            {file && state !== "failed" && (
              <>
                <FilePreview
                  file={file}
                  onRemove={reset}
                  removeDisabled={isConverting}
                />

                {isConverting ? (
                  <ConversionProgress
                    job={job}
                    sourceLabel={sourceLabel}
                    targetLabel={targetLabel}
                  />
                ) : state === "completed" && job ? (
                  <ConversionResult job={job} onDownload={download} onReset={reset} />
                ) : (
                  <div className="space-y-4">
                    <FormatSelector
                      formats={file.available_formats}
                      value={targetFormat}
                      onChange={setTargetFormat}
                      disabled={isConverting}
                      sourceExtension={file.extension}
                    />
                    <ConversionButton
                      onClick={() => void startConversion()}
                      disabled={!targetFormat || file.available_formats.length === 0}
                      isConverting={isConverting}
                      targetLabel={targetLabel}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
