"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ChevronDown, CircleAlert, FileText, Globe2, LayoutGrid, ListChecks, Settings, Users, Zap } from "lucide-react";

type NavigationItem = { label: string; href: string; icon: typeof LayoutGrid; badge?: string };
type NavigationSection = { label: "Portfolio" | "Operations" | "Analytics"; items: NavigationItem[] };

const navigationSections: NavigationSection[] = [
  { label: "Portfolio", items: [{ label: "Clients", href: "/clients", icon: Users }, { label: "Sites", href: "/sites", icon: Globe2 }] },
  { label: "Operations", items: [{ label: "Leads", href: "/leads", icon: Zap }, { label: "Incidents", href: "/incidents", icon: CircleAlert, badge: "1" }, { label: "Deliveries", href: "/deliveries", icon: ListChecks }, { label: "Monitoring", href: "/monitoring", icon: Activity }] },
  { label: "Analytics", items: [{ label: "Reports", href: "/reports", icon: FileText }] },
];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function BrandMark() {
  return <span className="overview-mark" aria-hidden="true"><span /><span /><span /></span>;
}

export function Sidebar() {
  const pathname = usePathname();
  const overviewActive = isActive(pathname, "/overview");
  const settingsActive = isActive(pathname, "/settings");

  return <aside className="overview-sidebar">
    <Link className="overview-brand" href="/overview"><BrandMark /><span>Ackvia</span></Link>
    <nav className="overview-nav" aria-label="Primary navigation">
      <Link className={`nav-item nav-overview ${overviewActive ? "nav-item-active" : ""}`} href="/overview" aria-current={overviewActive ? "page" : undefined}><LayoutGrid size={15} strokeWidth={1.7} /><span>Overview</span></Link>
      {navigationSections.map((section) => <div className="nav-section" key={section.label}>
        <span className="nav-section-label">{section.label}</span>
        {section.items.map(({ label, href, icon: Icon, badge }) => { const active = isActive(pathname, href); return <Link className={`nav-item ${active ? "nav-item-active" : ""}`} href={href} key={label} aria-current={active ? "page" : undefined}><Icon size={15} strokeWidth={1.7} /><span>{label}</span>{badge && <b>{badge}</b>}</Link>; })}
      </div>)}
    </nav>
    <div className="sidebar-bottom">
      <Link className={`nav-item ${settingsActive ? "nav-item-active" : ""}`} href="/settings" aria-current={settingsActive ? "page" : undefined}><Settings size={15} strokeWidth={1.7} /><span>Settings</span></Link>
      <button className="workspace-switcher" type="button"><span className="avatar">RT</span><span className="workspace-copy"><strong>Rostyslav</strong><small>Acme Agency</small></span><ChevronDown size={13} /></button>
    </div>
  </aside>;
}
