"use client";

import { useEffect, useState } from "react";

import { CategoryCards } from "@/components/CategoryCards";
import { Converter } from "@/components/Converter";
import { HowItWorks } from "@/components/HowItWorks";
import { ShieldIcon } from "@/components/icons";
import { SupportedFormats } from "@/components/SupportedFormats";
import { api } from "@/lib/api";
import type { FormatsPayload } from "@/types";

/**
 * Home page. The format list is fetched client-side because the converter
 * workflow already requires the client, and the backend is the source of truth
 * for every format shown.
 */
export default function HomePage() {
  const [formats, setFormats] = useState<FormatsPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    api
      .formats()
      .then((payload) => {
        if (!cancelled) setFormats(payload);
      })
      .catch(() => {
        // The converter card shows the actionable error; the sections degrade
        // to empty rather than crashing the page.
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <section className="mx-auto max-w-3xl px-4 pt-14 text-center sm:px-6 sm:pt-20 lg:px-8">
        <span className="inline-flex items-center gap-2 rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-600">
          <ShieldIcon className="h-3.5 w-3.5" />
          Runs locally · Files auto-deleted
        </span>

        <h1 className="mt-6 text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">
          Convert Your Files Easily
        </h1>

        <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-zinc-500 sm:text-lg">
          Fast, simple and secure file conversion. No page limits, no watermarks,
          no sign-up.
        </p>
      </section>

      <div className="mx-auto mt-10 max-w-3xl px-4 sm:px-6 sm:mt-12 lg:px-8">
        <Converter />
      </div>

      <CategoryCards formats={formats} />
      <HowItWorks />
      <SupportedFormats formats={formats} isLoading={isLoading} />
    </>
  );
}
