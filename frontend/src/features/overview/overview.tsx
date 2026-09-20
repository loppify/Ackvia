import Link from "next/link";
import { ChevronDown, CircleAlert } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { ActivityFeed, Metric, Panel, PanelHeading, SiteHealthList, StatusBadge } from "./components";
import { activityEvents, deliveryBreakdown, siteHealth } from "./mock-data";

function LeadActivityChart() {
  return <Panel className="activity-chart"><PanelHeading title="Lead activity" /><div className="chart-meta"><span>Captured leads</span><strong>1,284</strong></div><div className="line-chart"><div className="y-labels"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><svg viewBox="0 0 620 160" preserveAspectRatio="none" role="img" aria-label="Captured lead volume over the last 30 days"><defs><linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#6e9cff" stopOpacity=".2" /><stop offset="1" stopColor="#6e9cff" stopOpacity="0" /></linearGradient></defs><path className="chart-area" d="M0 123 L25 111 L50 118 L75 101 L100 106 L125 94 L150 96 L175 82 L200 84 L225 70 L250 60 L275 72 L300 57 L325 62 L350 47 L375 48 L400 35 L425 42 L450 31 L475 35 L500 20 L525 27 L550 13 L575 23 L620 20 L620 160 L0 160Z" /><path className="chart-line" d="M0 123 L25 111 L50 118 L75 101 L100 106 L125 94 L150 96 L175 82 L200 84 L225 70 L250 60 L275 72 L300 57 L325 62 L350 47 L375 48 L400 35 L425 42 L450 31 L475 35 L500 20 L525 27 L550 13 L575 23 L620 20" /></svg><div className="x-labels"><span>Aug 20</span><span>Aug 27</span><span>Sep 3</span><span>Sep 10</span><span>Sep 17</span></div></div></Panel>;
}

function DeliveryHealth() {
  const total = deliveryBreakdown.reduce((sum, item) => sum + item.value, 0);
  const toneColors = { good: "#45d5a3", warn: "#e0a549", bad: "#ed6d73", neutral: "#718297" } as const;
  const segments = deliveryBreakdown.reduce<{ values: string[]; end: number }>(({ values, end }, item) => {
    const nextEnd = end + (item.value / total) * 100;
    return { values: [...values, `${toneColors[item.tone]} ${end}% ${nextEnd}%`], end: nextEnd };
  }, { values: [], end: 0 }).values;

  return <Panel className="delivery-panel"><PanelHeading title="Delivery health" /><div className="delivery-body"><div className="donut" style={{ background: `conic-gradient(${segments.join(", ")})` }}><div><strong>{total.toLocaleString()}</strong><span>Total deliveries</span></div></div><ul className="legend">{deliveryBreakdown.map((item) => <li key={item.label}><i className={`legend-${item.tone}`} /><span>{item.label}</span><b>{item.value.toLocaleString()}</b></li>)}</ul></div></Panel>;
}

export function Overview() {
  return <AppShell><div className="overview-content">
    <header className="page-header"><div><h1>Overview</h1><p className="portfolio-status"><span className="pulse-dot" />30 of 31 lead paths operational</p></div><div className="header-filters"><button className="filter-button" type="button">Last 30 days<ChevronDown size={13} /></button><button className="filter-button" type="button">All clients<ChevronDown size={13} /></button><button className="filter-button" type="button">All sites<ChevronDown size={13} /></button></div></header>
    <section className="metric-grid" aria-label="Portfolio metrics"><Metric label="Captured leads" value="1,284" detail="+12% vs previous 30d" /><Metric label="Protected sites" value="24" /><Metric label="Delivery rate" value="99.8%" detail="+0.3 pp" /><Metric label="Active incidents" value="1" detail="Needs attention" tone="attention" /></section>
    <section className="attention-panel"><div className="attention-icon"><CircleAlert size={16} /></div><div className="attention-copy"><div className="attention-title"><h2>Needs attention</h2><StatusBadge tone="warn">Awaiting retry</StatusBadge></div><p><strong>Keller Solar</strong><span>kellersolar.com</span><b>CRM Webhook delivery failing</b></p></div><div className="attention-time"><span>Started 12 min ago</span><Link href="/incidents/incident-keller-crm">View incident <ChevronDown size={13} /></Link></div></section>
    <div className="visual-grid"><LeadActivityChart /><DeliveryHealth /></div>
    <div className="lower-grid"><Panel className="activity-panel"><PanelHeading title="Recent activity" linkLabel="View all" href="/leads" /><ActivityFeed events={activityEvents} /></Panel><Panel className="sites-panel"><PanelHeading title="Site health" linkLabel="View all" href="/sites" /><SiteHealthList sites={siteHealth} /></Panel></div>
    <footer className="overview-footer"><span><span className="footer-dot" />All systems monitored</span><span>Last updated just now</span></footer>
  </div></AppShell>;
}
