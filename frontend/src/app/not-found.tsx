import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { DashboardPage, PageHeader } from "@/components/dashboard-ui";

export default function NotFound() {
  return <AppShell><DashboardPage><PageHeader title="Page not found" description="This route does not exist in the Ackvia workspace." actions={<Link className="dash-button" href="/overview">Return to Overview</Link>} /></DashboardPage></AppShell>;
}
