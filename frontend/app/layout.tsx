import type { Metadata } from "next";
import Link from "next/link";
import { Atkinson_Hyperlegible, Barlow_Condensed } from "next/font/google";
import "./globals.css";

const barlow = Barlow_Condensed({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-barlow" });
const atkinson = Atkinson_Hyperlegible({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-atkinson" });

export const metadata: Metadata = {
  title: "HoopCouncil",
  description: "Five statistical player agents debate a basketball situation; a coach agent makes the call.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${barlow.variable} ${atkinson.variable}`}>
      <body className="board-texture">
        <header className="border-b border-rule/70">
          <div className="mx-auto flex max-w-6xl items-baseline justify-between gap-4 px-4 py-4 sm:px-6">
            <Link href="/" className="font-display text-3xl font-bold text-ink">
              HoopCouncil
            </Link>
            <p className="text-right text-sm text-ink-soft">
              AI simulation based on player statistics and career tendencies.
            </p>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 pb-24 pt-8 sm:px-6">{children}</main>
      </body>
    </html>
  );
}
