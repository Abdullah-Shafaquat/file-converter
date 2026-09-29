"use client";

import { LoadingSpinner } from "@/components/LoadingSpinner";

interface ConversionButtonProps {
  onClick: () => void;
  disabled: boolean;
  isConverting: boolean;
  targetLabel: string;
}

/** Primary call-to-action. Disabled until a valid file and target exist. */
export function ConversionButton({
  onClick,
  disabled,
  isConverting,
  targetLabel,
}: ConversionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || isConverting}
      className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-zinc-900 px-6 py-3.5
        text-sm font-semibold text-white transition-all
        hover:bg-zinc-800 active:scale-[.99]
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900
        disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400 disabled:active:scale-100"
    >
      {isConverting ? (
        <>
          <LoadingSpinner size="sm" label="Converting" />
          Converting…
        </>
      ) : (
        <>Convert File{targetLabel ? ` to ${targetLabel}` : ""}</>
      )}
    </button>
  );
}
