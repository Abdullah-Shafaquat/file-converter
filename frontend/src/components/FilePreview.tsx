"use client";

import { CATEGORY_ICONS, CloseIcon } from "@/components/icons";
import { categoryStyle, formatBytes, iconForCategory } from "@/lib/format";
import type { UploadedFile } from "@/types";

interface FilePreviewProps {
  file: UploadedFile;
  onRemove: () => void;
  removeDisabled: boolean;
}

/** Shows the selected file: name, type, size and a remove control. */
export function FilePreview({ file, onRemove, removeDisabled }: FilePreviewProps) {
const iconKey = iconForCategory(file.category);

const Icon =
  CATEGORY_ICONS[iconKey as keyof typeof CATEGORY_ICONS] ??
  CATEGORY_ICONS.default;
  return ( 
    <div className="flex items-center gap-3.5 rounded-2xl border border-zinc-200 bg-white p-4">
      <span
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ring-1 ${categoryStyle(
          file.category,
        )}`}
      >
        <Icon  />
      </span>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-zinc-900" title={file.original_name}>
          {file.original_name}
        </p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-zinc-500">
          <span className="rounded px-1.5 py-0.5 font-medium uppercase ring-1 ring-inset ring-zinc-200">
            {file.label ?? file.extension.toUpperCase()}
          </span>
          <span aria-hidden="true">·</span>
          <span>{formatBytes(file.size_bytes)}</span>
        </p>
      </div>

      <button
        type="button"
        onClick={onRemove}
        disabled={removeDisabled}
        className="shrink-0 rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <CloseIcon className="h-5 w-5" />
        <span className="sr-only">Remove {file.original_name}</span>
      </button>
    </div>
  );
}
