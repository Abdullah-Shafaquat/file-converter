"use client";

import { useMemo, useState } from "react";

import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { FormatsPayload } from "@/types";

interface SupportedFormatsProps {
  formats: FormatsPayload | null;
  isLoading: boolean;
}

const TABS = ["Documents", "Images", "Archives"] as const;
type Tab = (typeof TABS)[number];

const TAB_TO_CATEGORY: Record<Tab, string> = {
  Documents: "document",
  Images: "image",
  Archives: "archive",
};

/** Full format list straight from the backend matrix - never hard-coded. */
export function SupportedFormats({ formats, isLoading }: SupportedFormatsProps) {
  const [activeTab, setActiveTab] = useState<Tab>("Documents");

  const byCategory = useMemo(() => {
    if (!formats) return {} as Record<string, string[]>;
    return formats.categories.reduce<Record<string, string[]>>((accumulator, category) => {
      accumulator[category.id] = category.formats.map((format) => format.extension);
      return accumulator;
    }, {});
  }, [formats]);

  const conversionCount = formats
    ? Object.values(formats.conversions).reduce((total, targets) => total + targets.length, 0)
    : 0;

  const activeExtensions = byCategory[TAB_TO_CATEGORY[activeTab]] ?? [];

  return (
    <section id="formats" aria-labelledby="formats-heading" className="mt-20 scroll-mt-20 sm:mt-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2
            id="formats-heading"
            className="text-2xl font-semibold tracking-tight text-zinc-900 sm:text-3xl"
          >
            Supported formats
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-base text-zinc-500">
            {isLoading
              ? "Loading the conversion matrix from the backend…"
              : `${conversionCount} working conversions across ${Object.keys(formats?.conversions ?? {}).length} input formats.`}
          </p>
        </div>

        <div className="mt-8 flex flex-col items-center">
          <div
            role="tablist"
            aria-label="Format categories"
            className="inline-flex rounded-xl bg-zinc-100 p-1"
          >
            {TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-all
                  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900
                  ${
                    activeTab === tab
                      ? "bg-white text-zinc-900 shadow-sm"
                      : "text-zinc-600 hover:text-zinc-900"
                  }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div
            role="tabpanel"
            className="mt-8 min-h-40 w-full rounded-2xl border border-zinc-200 bg-white p-6"
          >
            {isLoading ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="lg" label="Loading formats" />
              </div>
            ) : activeExtensions.length === 0 ? (
              <p className="py-8 text-center text-sm text-zinc-500">
                No formats in this category.
              </p>
            ) : (
              <ul className="flex flex-wrap justify-center gap-2">
                {activeExtensions.map((extension) => (
                  <li key={extension}>
                    <span className="inline-block rounded-lg bg-zinc-50 px-3 py-1.5 font-mono text-xs font-medium text-zinc-700 ring-1 ring-inset ring-zinc-200">
                      {extension.toUpperCase()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <p className="mt-4 text-center text-xs text-zinc-400">
          Legacy <span className="font-mono">DOC</span>,{" "}
          <span className="font-mono">ODT</span>, <span className="font-mono">RTF</span> and{" "}
          <span className="font-mono">XLS</span> need LibreOffice. Without it those
          conversions are hidden rather than faked.
        </p>
      </div>
    </section>
  );
}
