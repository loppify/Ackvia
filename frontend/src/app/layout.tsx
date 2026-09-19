import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./globals.css";
import "@/features/desk/desk.css";

export const metadata: Metadata = {
  title: "Investigation desk · Ackvia",
  description: "Captured submissions. Delivery evidence. Recovery in context.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
