/** Presentation helpers: byte formatting, icons, category grouping. */

import type { Category, FormatInfo, FormatsPayload } from "@/types";

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** exponent;
  const decimals = exponent === 0 ? 0 : value >= 100 ? 0 : value >= 10 ? 1 : 2;
  return `${value.toFixed(decimals)} ${units[exponent]}`;
}

export function formatLimit(bytes: number): string {
  return formatBytes(bytes);
}

/** Short badge text for a file extension, e.g. "PDF". */
export function extensionBadge(extension: string): string {
  return extension.slice(0, 4).toUpperCase();
}

const CATEGORY_STYLES: Record<Category, string> = {
  document: "bg-blue-50 text-blue-700 ring-blue-600/20",
  image: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  archive: "bg-amber-50 text-amber-700 ring-amber-600/20",
};

export function categoryStyle(category: Category | null): string {
  if (!category) return "bg-zinc-100 text-zinc-700 ring-zinc-500/20";
  return CATEGORY_STYLES[category];
}

export const CATEGORY_ORDER: Category[] = ["document", "image", "archive"];

export function sortedCategories(payload: FormatsPayload | null): FormatInfo[] {
  if (!payload) return [];
  const byCategory = new Map<Category, FormatInfo[]>();
  for (const category of payload.categories) {
    byCategory.set(category.id, category.formats);
  }
  return CATEGORY_ORDER.flatMap((category) => byCategory.get(category) ?? []);
}

export function findFormat(
  payload: FormatsPayload | null,
  extension: string,
): FormatInfo | null {
  if (!payload) return null;
  const target = extension.toLowerCase();
  for (const category of payload.categories) {
    const match = category.formats.find((format) => format.extension === target);
    if (match) return match;
  }
  return null;
}

/** Icon name for the uploader/preview badge. */
export function iconForCategory(category: Category | null): string {
  switch (category) {
    case "document":
      return "document";
    case "image":
      return "image";
    case "archive":
      return "archive";
    default:
      return "file";
  }
}

export function friendlyTarget(label: string): string {
  return label.toUpperCase();
}
