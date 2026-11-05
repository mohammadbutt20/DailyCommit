import type { Metadata } from "next";
import Header from "@/components/Header";
import { mono, sans } from "@/lib/fonts";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Daily Commit",
  description: "Group coding practice: one problem a day, one streak together.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      {/* Browser extensions often add attributes to <body> before React loads; ignore those
          (this only covers <body>'s own attributes, not its children). */}
      <body className="min-h-screen antialiased" suppressHydrationWarning>
        <Providers>
          <Header />
          <main className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
