import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lenny Growth Assistant",
  description: "A grounded RAG assistant over Lenny's Podcast transcripts.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
