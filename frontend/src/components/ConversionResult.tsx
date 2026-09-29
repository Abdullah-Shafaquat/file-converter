"use client";

import { useState } from "react";

import { CheckIcon, DownloadIcon, RefreshIcon } from "@/components/icons";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { formatBytes } from "@/lib/format";
import type { ConversionJob } from "@/types";

interface ConversionResultProps {
  job: ConversionJob;
  onDownload: () => Promise<void>;
  onReset: () => void;
}

/** Success state: confirms completion and offers download + start-over. */
export function ConversionResult({ job, onDownload, onReset }: ConversionResultProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      await onDownload();
    } finally {
      setIsDownloading(false);
    }
  };

  const size = job.output_size_bytes ? formatBytes(job.output_size_bytes) : null;

  return (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
          <CheckIcon className="h-5 w-5" />
        </span>

        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-emerald-900">
            Conversion complete
          </p>
          <p className="mt-1 truncate text-sm text-emerald-800" title={job.output_name ?? ""}>
            {job.output_name}
            {size ? <span className="text-emerald-700"> · {size}</span> : null}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          onClick={handleDownload}
          disabled={isDownloading}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-zinc-900 px-5 py-3
            text-sm font-semibold text-white transition-colors hover:bg-zinc-800
            focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900
            disabled:cursor-wait disabled:opacity-70"
        >
          {isDownloading ? (
            <>
              <LoadingSpinner size="sm" label="Preparing download" />
              Preparing…
            </>
          ) : (
            <>
              <DownloadIcon className="h-4.5 w-4.5" />
              Download File
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-5 py-3
            text-sm font-semibold text-zinc-800 ring-1 ring-inset ring-zinc-300
            transition-colors hover:bg-zinc-50
            focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900"
        >
          <RefreshIcon className="h-4.5 w-4.5" />
          Convert Another File
        </button>
      </div>

      <p className="mt-3 text-xs text-emerald-700/80">
        This file is deleted automatically after the retention period.
      </p>
    </div>
  );
}
