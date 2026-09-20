"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ChevronDown,
  CircleAlert,
  FileText,
  Globe2,
  LayoutGrid,
  ListChecks,
  Settings,
  Users,
  Zap,
} from "lucide-react";

type NavigationItem = {
  label: string;
  href: string;
  icon: typeof LayoutGrid;
  badge?: string;
};

const navigation: NavigationItem[] = [
  { label: "Overview", href: "/overview", icon: LayoutGrid },
  { label: "Clients", href: "/clients", icon: Users },
  { label: "Sites", href: "/sites", icon: Globe2 },
  { label: "Leads", href: "/leads", icon: Zap },
  { label: "Incidents", href: "/incidents", icon: CircleAlert, badge: "1" },
  { label: "Deliveries", href: "/deliveries", icon: ListChecks },
  { label: "Monitoring", href: "/monitoring", icon: Activity },
  { label: "Reports", href: "/reports", icon: FileText },
];

function BrandMark() {
  return <span className="overview-mark" aria-hidden="true"><span /><span /><span /></span>;
}

export function Sidebar() {
  const pathname = usePathname();

  return <aside className="overview-sidebar">
    <Link className="overview-brand" href="/overview"><BrandMark /><span>Ackvia</span></Link>
    <nav className="overview-nav" aria-label="Primary navigation">
      {navigation.map(({ label, href, icon: Icon, badge }) => <Link className={`nav-item ${pathname === href || pathname.startsWith(`${href}/`) ? "nav-item-active" : ""}`} href={href} key={label}>
        <Icon size={15} strokeWidth={1.7} /><span>{label}</span>{badge && <b>{badge}</b>}
      </Link>)}
    </nav>
    <div className="sidebar-bottom">
      <Link className={`nav-item ${pathname === "/settings" || pathname.startsWith("/settings/") ? "nav-item-active" : ""}`} href="/settings"><Settings size={15} strokeWidth={1.7} /><span>Settings</span></Link>
      <button className="workspace-switcher" type="button">
        <span className="avatar">RT</span><span className="workspace-copy"><strong>Rostyslav</strong><small>Acme Agency</small></span><ChevronDown size={13} />
      </button>
    </div>
  </aside>;
}
