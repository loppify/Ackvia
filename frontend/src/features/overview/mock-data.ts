import { activities, deliveryBreakdown, sites } from "@/lib/mock-data";

export type { SiteStatus, StatusTone } from "@/lib/mock-data";
export type ActivityEvent = (typeof activities)[number];
export type SiteHealth = { id: string; name: string; domain: string; leads: string; deliveryRate: string; status: "Healthy" | "Attention" | "Down" | "Unknown" };

export { deliveryBreakdown };
export const activityEvents = activities;
export const siteHealth: SiteHealth[] = sites.slice(0, 5).map((site) => ({ id: site.id, name: site.name, domain: site.domain, leads: site.leads.toLocaleString(), deliveryRate: site.deliveryRate, status: site.health }));
