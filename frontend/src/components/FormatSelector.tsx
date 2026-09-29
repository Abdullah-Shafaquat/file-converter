"use client";

import { useId } from "react";

import { ChevronIcon } from "@/components/icons";

interface FormatSelectorProps {
  formats: string[];
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  sourceExtension: string;
}

function prettyLabel(extension: string): string {
  const upper = extension.toUpperCase();
  const names: Record<string, string> = {
    MARKDOWN: "Markdown",
    DOCX: "Word (DOCX)",
    ODT: "OpenDocument (ODT)",
    RTF: "Rich Text (RTF)",
    TAR: "TAR archive",
    TGZ: "TAR.GZ archive",
    TAR_GZ: "TAR.GZ archive",
    BZ2: "BZIP2 archive",
    CSV: "CSV",
    TSV: "TSV",
    XLSX: "Excel (XLSX)",
    XLS: "Excel 97-2003 (XLS)",
    HTML: "HTML",
    JSON: "JSON",
    XML: "XML",
    YAML: "YAML",
    WEBP: "WebP",
    AVIF: "AVIF",
    ICO: "Icon (ICO)",
    SVG: "SVG",
  };
  return names[upper] ?? upper;
}

/** Native select: keyboard and mobile friendly for choosing a target format. */
export function FormatSelector({
  formats,
  value,
  onChange,
  disabled,
  sourceExtension,
}: FormatSelectorProps) {
  const selectId = useId();
  const hintId = useId();

  return (
    <div>
      <label
        htmlFor={selectId}
        className="mb-2 block text-sm font-medium text-zinc-700"
      >
        Convert to
      </label>

      <div className="relative">
        <select
          id={selectId}
          value={value}
          disabled={disabled}
          aria-describedby={hintId}
          onChange={(event) => onChange(event.target.value)}
          className="w-full appearance-none rounded-xl border border-zinc-300 bg-white py-3 pl-4 pr-11
            text-sm font-medium text-zinc-900 transition-colors
            hover:border-zinc-400 focus-visible:border-zinc-900 focus-visible:outline-2
            focus-visible:outline-offset-0 focus-visible:outline-zinc-900
            disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400"
        >
          {formats.length === 0 ? (
            <option value="">No conversions available</option>
          ) : (
            formats.map((format) => (
              <option key={format} value={format}>
                {prettyLabel(format)}
              </option>
            ))
          )}
        </select>

        <ChevronIcon
          className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
        />
      </div>

      <p id={hintId} className="mt-2 text-xs text-zinc-500">
        {formats.length} format{formats.length === 1 ? "" : "s"} available from{" "}
        {sourceExtension.toUpperCase()}
      </p>
    </div>
  );
}
