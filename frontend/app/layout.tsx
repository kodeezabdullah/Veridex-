import type { Metadata } from "next";
import "./globals.css";
import { AppBootGate } from "@/components/AppBootGate";

export const metadata: Metadata = {
  title: "Veridex — Evidence-led care coverage",
  description: "Explore healthcare capability coverage with evidence and confidence in view.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><AppBootGate>{children}</AppBootGate></body>
    </html>
  );
}
