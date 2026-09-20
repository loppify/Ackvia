import "./overview.css";
import { AppShell } from "@/components/app-shell";
import { DashboardPage, LoadingState } from "@/components/dashboard-ui";

export default function Loading() {
  return <AppShell><DashboardPage><LoadingState /></DashboardPage></AppShell>;
}
