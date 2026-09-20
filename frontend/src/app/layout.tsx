import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./globals.css";
import "./dashboard.css";

export const metadata: Metadata = {
  title: "Overview · Ackvia",
  description: "Portfolio lead reliability at a glance.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
