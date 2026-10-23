import type { Metadata } from "next";
import Header from "@/components/Header";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Daily Commit",
  description: "Group coding practice: one problem a day, one streak together.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <Providers>
          <Header />
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
