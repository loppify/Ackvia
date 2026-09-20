"use client";

import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { DashboardPage, PageHeader } from "@/components/dashboard-ui";

export default function Error({ reset }: { reset: () => void }) {
  return <AppShell><DashboardPage><PageHeader title="Something went wrong" description="Ackvia could not render this workspace view. Your captured evidence is stored separately." actions={<><button className="dash-button" type="button" onClick={reset}>Try again</button><Link className="dash-button" href="/overview">Open Overview</Link></>} /></DashboardPage></AppShell>;
}
