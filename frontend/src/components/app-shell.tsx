import type { ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="overview-shell">
      <Sidebar />
      <main className="overview-main"><TopBar />{children}</main>
    </div>
  );
}
