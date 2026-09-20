import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight, CircleAlert, CircleCheck, Globe2, Webhook } from "lucide-react";
import type { ActivityEvent, SiteHealth, SiteStatus, StatusTone } from "./mock-data";

const siteStatusTone = {
  Healthy: "good",
  Attention: "warn",
  Down: "bad",
  Unknown: "neutral",
} satisfies Record<SiteStatus, StatusTone>;

function activityHref(event: ActivityEvent) {
  const routes = { lead: "/leads", delivery: "/deliveries", incident: "/incidents" } as const;
  return `${routes[event.target.type]}/${event.target.id}`;
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}

export function PanelHeading({ title, linkLabel, href }: { title: string; linkLabel?: string; href?: string }) {
  return <div className="panel-heading"><h2>{title}</h2>{linkLabel && href && <Link href={href}>{linkLabel}<ChevronRight size={13} /></Link>}</div>;
}

export function StatusBadge({ children, tone = "good" }: { children: ReactNode; tone?: StatusTone }) {
  return <span className={`status status-${tone}`}><span className="status-dot" />{children}</span>;
}

export function Metric({ label, value, detail, tone = "positive" }: { label: string; value: string; detail?: string; tone?: "positive" | "attention" }) {
  return <div className={`metric ${tone === "attention" ? "metric-attention" : ""}`}><span>{label}</span><strong>{value}</strong>{detail && <em className={tone === "attention" ? "trend-attention" : "trend-positive"}>{detail}</em>}</div>;
}

export function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  return <div className="activity-list">{events.map((event) => <Link className="activity-row" href={activityHref(event)} key={`${event.time}-${event.title}`}><span className={`event-icon event-${event.tone}`} aria-label={event.category}>{event.category === "incident" ? <CircleAlert size={13} /> : event.category === "delivery" ? <Webhook size={13} /> : <CircleCheck size={13} />}</span><time>{event.time}</time><span className="event-copy"><strong>{event.title}</strong><small>{event.detail}</small></span><StatusBadge tone={event.tone}>{event.status}</StatusBadge></Link>)}</div>;
}

export function SiteHealthList({ sites }: { sites: SiteHealth[] }) {
  return <div className="site-list">{sites.map((site) => <Link className="site-row" href={`/sites/${site.id}`} key={site.name}><span className="site-icon"><Globe2 size={14} /></span><span className="site-copy"><strong>{site.name}</strong><small>{site.domain}</small></span><span className="site-leads">{site.leads} leads</span><span className="site-rate">{site.deliveryRate}</span><StatusBadge tone={siteStatusTone[site.status]}>{site.status}</StatusBadge></Link>)}</div>;
}
