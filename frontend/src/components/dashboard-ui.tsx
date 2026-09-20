import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight, CircleAlert, CircleCheck, CircleHelp } from "lucide-react";
import type { HealthStatus, StatusTone } from "@/lib/mock-data";

const healthTone: Record<HealthStatus, StatusTone> = { Healthy: "good", Attention: "warn", Down: "bad", Unknown: "neutral" };

export function DashboardPage({ children }: { children: ReactNode }) {
  return <div className="dashboard-content">{children}</div>;
}

export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return <nav className="breadcrumbs" aria-label="Breadcrumb">{items.map((item, index) => <span key={`${item.label}-${index}`}>{index > 0 && <ChevronRight size={12} />}{item.href ? <Link href={item.href}>{item.label}</Link> : <strong>{item.label}</strong>}</span>)}</nav>;
}

export function PageHeader({ title, description, actions, breadcrumbs }: { title: string; description?: string; actions?: ReactNode; breadcrumbs?: { label: string; href?: string }[] }) {
  return <header className="dashboard-header">{breadcrumbs && <Breadcrumbs items={breadcrumbs} />}<div className="dashboard-header-row"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="dashboard-actions">{actions}</div>}</div></header>;
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`dashboard-panel ${className}`}>{children}</section>;
}

export function PanelTitle({ title, action }: { title: string; action?: ReactNode }) {
  return <div className="dashboard-panel-title"><h2>{title}</h2>{action}</div>;
}

export function StatusBadge({ label, tone, status }: { label?: string; tone?: StatusTone; status?: HealthStatus }) {
  const resolvedTone = status ? healthTone[status] : tone ?? "neutral";
  return <span className={`dash-status dash-status-${resolvedTone}`}><span />{label ?? status}</span>;
}

export function HealthBadge({ status }: { status: HealthStatus }) {
  return <StatusBadge status={status} />;
}

export function StatStrip({ items }: { items: { label: string; value: string; detail?: string }[] }) {
  return <div className="dash-stat-strip">{items.map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong>{item.detail && <small>{item.detail}</small>}</div>)}</div>;
}

export function DataTable({ headers, children, empty }: { headers: string[]; children?: ReactNode; empty?: ReactNode }) {
  return <div className="data-table-wrap"><table className="data-table"><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{children ?? <tr><td colSpan={headers.length}>{empty}</td></tr>}</tbody></table></div>;
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return <div className="empty-state"><CircleHelp size={18} /><strong>{title}</strong>{description && <p>{description}</p>}</div>;
}

export function LoadingState() {
  return <div className="loading-state" role="status" aria-label="Loading"><span /><span /><span /></div>;
}

export function DetailFields({ fields }: { fields: { label: string; value: ReactNode; mono?: boolean }[] }) {
  return <dl className="detail-fields">{fields.map((field) => <div key={field.label}><dt>{field.label}</dt><dd className={field.mono ? "mono" : ""}>{field.value}</dd></div>)}</dl>;
}

export function Timeline({ items }: { items: { label: string; time: string; detail?: string; tone?: StatusTone }[] }) {
  return <ol className="evidence-timeline">{items.map((item) => <li key={`${item.label}-${item.time}`}><span className={`timeline-icon timeline-${item.tone ?? "good"}`}>{item.tone === "warn" ? <CircleAlert size={13} /> : <CircleCheck size={13} />}</span><div><strong>{item.label}</strong><time>{item.time}</time>{item.detail && <p>{item.detail}</p>}</div></li>)}</ol>;
}

export function CodeBlock({ title, children }: { title: string; children: ReactNode }) {
  return <div className="code-block"><div className="code-block-title">{title}</div><pre>{children}</pre></div>;
}

export function LinkButton({ href, children }: { href: string; children: ReactNode }) {
  return <Link className="dash-button" href={href}>{children}<ChevronRight size={13} /></Link>;
}
