import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Universal File Converter — Convert PDF, CSV, Images & Archives",
  description:
    "Convert documents, spreadsheets, images and archives locally. No page limits, no watermarks, no account required.",
  applicationName: "Universal File Converter",
  keywords: ["file converter", "pdf to csv", "csv to pdf", "image converter", "local"],
  openGraph: {
    title: "Universal File Converter",
    description: "Convert PDF, CSV, Excel, JSON and images locally. Free and unlimited.",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#ffffff",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="flex min-h-dvh flex-col bg-zinc-50 antialiased">
        <a
          href="#converter"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50
            focus:rounded-lg focus:bg-zinc-900 focus:px-4 focus:py-2 focus:text-sm
            focus:font-medium focus:text-white"
        >
          Skip to converter
        </a>

        <Header />
        <main className="flex-1 pb-20">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
