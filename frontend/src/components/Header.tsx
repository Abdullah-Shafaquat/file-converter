"use client";

import Link from "next/link";

import { BoltIcon } from "@/components/icons";

const NAV_LINKS = [
  { href: "#converter", label: "Converter" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#formats", label: "Supported formats" },
] as const;

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-zinc-200/70 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="group flex items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-900"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-zinc-900 text-white transition-transform group-hover:scale-105">
            <BoltIcon className="h-5 w-5" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-[15px] font-semibold tracking-tight text-zinc-900">
              File Converter
            </span>
            <span className="mt-0.5 text-[11px] font-medium text-zinc-500">
              Universal converter
            </span>
          </span>
        </Link>

        <nav aria-label="Main">
          <ul className="flex items-center gap-1 sm:gap-2">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  className="rounded-lg px-2.5 py-2 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 sm:px-3"
                >
                  <span className="hidden sm:inline">{link.label}</span>
                  <span className="sm:hidden">
                    {link.label === "Supported formats" ? "Formats" : link.label}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
