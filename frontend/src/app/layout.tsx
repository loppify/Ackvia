import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./globals.css";
import "./dashboard.css";
import "@/features/desk/desk.css";

export const metadata: Metadata = {
  title: "Evidence · Ackvia",
  description: "Captured leads, delivery outcomes, and attempt history.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
