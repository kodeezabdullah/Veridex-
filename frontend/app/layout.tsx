import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Veridex — Evidence-led care coverage",
  description: "Explore healthcare capability coverage with evidence and confidence in view.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
