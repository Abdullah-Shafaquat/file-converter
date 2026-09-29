import { CATEGORY_ICONS } from "@/components/icons";
import type { Category, FormatsPayload } from "@/types";

const CATEGORY_COPY: Record<
  Category,
  { title: string; blurb: string; tint: string }
> = {
  document: {
    title: "Documents",
    blurb:
      "PDF, Word, spreadsheets and text. PDF to CSV recovers ruled tables automatically.",
    tint: "text-blue-700 bg-blue-50 ring-blue-600/20",
  },
  image: {
    title: "Images",
    blurb:
      "Every raster format to every other, plus SVG rasterising. No size cap surprise.",
    tint: "text-emerald-700 bg-emerald-50 ring-emerald-600/20",
  },
  archive: {
    title: "Archives",
    blurb: "Repack between ZIP, TAR and compressed formats, with traversal protection.",
    tint: "text-amber-700 bg-amber-50 ring-amber-600/20",
  },
};

interface CategoryCardsProps {
  formats: FormatsPayload | null;
}

/** Popular conversion categories, driven by the backend format list. */
export function CategoryCards({ formats }: CategoryCardsProps) {
  // The backend is the source of truth, but the UI only has copy and icons
  // for the three categories it knows about, so ignore anything unexpected
  // rather than rendering a card with undefined text.
  const categories = (formats?.categories ?? []).filter(
    (category) => category.id in CATEGORY_COPY && category.id in CATEGORY_ICONS
  );

  return (
    <section aria-labelledby="categories-heading" className="mt-20 sm:mt-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2
          id="categories-heading"
          className="text-center text-2xl font-semibold tracking-tight text-zinc-900 sm:text-3xl"
        >
          What you can convert
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-base text-zinc-500">
          Everything runs on your own machine. No page limits, no watermarks, no account.
        </p>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map((category) => {
            const copy = CATEGORY_COPY[category.id];
            const Icon = CATEGORY_ICONS[category.id];
            const names = category.formats.map((format) => format.extension.toUpperCase());

            return (
              <article
                key={category.id}
                className="group rounded-2xl border border-zinc-200 bg-white p-5 transition-all
                  hover:-translate-y-0.5 hover:border-zinc-300 hover:shadow-md
                  focus-within:border-zinc-400"
              >
                <span
                  className={`inline-flex h-11 w-11 items-center justify-center rounded-xl ring-1 ${copy.tint}`}
                >
                  <Icon className="h-5.5 w-5.5" />
                </span>

                <h3 className="mt-4 text-base font-semibold text-zinc-900">
                  {copy.title}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-zinc-500">
                  {copy.blurb}
                </p>

                <p className="mt-4 flex flex-wrap gap-1.5">
                  {names.slice(0, 8).map((name) => (
                    <span
                      key={name}
                      className="rounded-md bg-zinc-100 px-2 py-0.5 font-mono text-[11px] font-medium text-zinc-600"
                    >
                      {name}
                    </span>
                  ))}
                  {names.length > 8 && (
                    <span className="rounded-md bg-zinc-100 px-2 py-0.5 font-mono text-[11px] font-medium text-zinc-400">
                      +{names.length - 8}
                    </span>
                  )}
                </p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
