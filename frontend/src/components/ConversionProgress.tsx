"use client";

import { CheckIcon } from "@/components/icons";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { ConversionJob } from "@/types";

interface ConversionProgressProps {
  job: ConversionJob | null;
  sourceLabel: string;
  targetLabel: string;
}

/**
 * Live conversion status. Uses role="progressbar" with aria-valuenow so screen
 * readers announce progress, plus a polite live region for stage changes.
 */
export function ConversionProgress({
  job,
  sourceLabel,
  targetLabel,
}: ConversionProgressProps) {
  const progress = Math.max(0, Math.min(100, job?.progress ?? 0));
  const stage = job?.stage ?? "Preparing";

  return (
    <div
      className="rounded-2xl border border-zinc-200 bg-white p-5"
      role="group"
      aria-label="Conversion progress"
    >
      <div className="flex items-center gap-3">
        <LoadingSpinner size="md" label="Converting" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-zinc-900">
            Converting {sourceLabel} to {targetLabel}
          </p>
          <p className="mt-0.5 truncate text-xs text-zinc-500" aria-live="polite">
            {stage}
          </p>
        </div>
        <span className="shrink-0 text-sm font-semibold tabular-nums text-zinc-900">
          {progress}%
        </span>
      </div>

      <div
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Conversion progress"
        className="mt-4 h-2 w-full overflow-hidden rounded-full bg-zinc-100"
      >
        <div
          className="h-full rounded-full bg-zinc-900 transition-[width] duration-500 ease-out motion-reduce:transition-none"
          style={{ width: `${Math.max(progress, 3)}%` }}
        />
      </div>

      <p className="mt-3 flex items-center gap-1.5 text-xs text-zinc-500">
        <CheckIcon className="h-3.5 w-3.5 text-emerald-600" />
        You can keep this tab open — progress updates automatically.
      </p>
    </div>
  );
}
