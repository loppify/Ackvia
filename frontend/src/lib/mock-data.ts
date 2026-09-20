export type StatusTone = "good" | "warn" | "bad" | "neutral";
export type HealthStatus = "Healthy" | "Attention" | "Down" | "Unknown";
export type SiteStatus = HealthStatus;
export type LeadState = "Captured safely" | "Stored";
export type DeliveryState = "Pending" | "Processing" | "Awaiting retry" | "Delivered" | "Failed" | "Unknown";
export type AttemptResult = "Succeeded" | "Retryable failure" | "Permanent failure" | "Unknown result";
export type IncidentState = "Investigating" | "Recovering" | "Resolved automatically";

export type Client = { id: string; name: string; siteIds: string[]; leadPathCount: number; leads: number; deliveryRate: string; incidents: number; health: HealthStatus; lastActivity: string };
export type Site = { id: string; clientId: string; name: string; domain: string; leadPathIds: string[]; leads: number; deliveryRate: string; health: HealthStatus; lastActivity: string };
export type LeadPath = { id: string; siteId: string; name: string; status: HealthStatus; recentLeads: number; destinations: string[]; deliveryHealth: string; lastEvent: string };
export type Lead = { id: string; clientId: string; siteId: string; leadPathId: string; customerName: string; email: string; phone: string; message: string; capturedAt: string; state: LeadState; deliveryIds: string[] };
export type Delivery = { id: string; leadId: string; destination: string; state: DeliveryState; attemptIds: string[]; createdAt: string; deliveredAt?: string; nextRetry?: string; lastError?: string };
export type Attempt = { id: string; deliveryId: string; number: number; result: AttemptResult; trigger: string; startedAt: string; finishedAt: string; duration: string; providerStatus: string; providerMessage: string; nextRetry?: string };
export type Incident = { id: string; clientId: string; siteId: string; destination: string; title: string; state: IncidentState; startedAt: string; resolvedAt?: string; duration: string; affectedLeads: number; peakFailureRate: string; attemptIds: string[] };
export type Activity = { id: string; time: string; title: string; detail: string; status: string; tone: "good" | "warn" | "bad"; category: "capture" | "delivery" | "incident"; target: { type: "lead" | "delivery" | "incident"; id: string } };

export const clients: Client[] = [
  { id: "keller-solar", name: "Keller Solar", siteIds: ["keller-solar-site"], leadPathCount: 2, leads: 48, deliveryRate: "96.2%", incidents: 1, health: "Attention", lastActivity: "08:50" },
  { id: "northwind-dental", name: "Northwind Dental", siteIds: ["northwind-main", "northwind-ortho"], leadPathCount: 3, leads: 142, deliveryRate: "100%", incidents: 0, health: "Healthy", lastActivity: "08:31" },
  { id: "smith-realty", name: "Smith Realty", siteIds: ["smith-realty-site"], leadPathCount: 2, leads: 87, deliveryRate: "99.8%", incidents: 0, health: "Healthy", lastActivity: "Yesterday" },
  { id: "pizza-roma", name: "Pizza Roma", siteIds: ["pizza-roma-site"], leadPathCount: 1, leads: 24, deliveryRate: "100%", incidents: 0, health: "Healthy", lastActivity: "Yesterday" },
  { id: "old-mill-studio", name: "Old Mill Studio", siteIds: ["old-mill-site"], leadPathCount: 1, leads: 31, deliveryRate: "99.7%", incidents: 0, health: "Healthy", lastActivity: "2 days ago" },
];

export const sites: Site[] = [
  { id: "keller-solar-site", clientId: "keller-solar", name: "Keller Solar", domain: "kellersolar.com", leadPathIds: ["keller-contact", "keller-quote"], leads: 48, deliveryRate: "96.2%", health: "Attention", lastActivity: "08:50" },
  { id: "northwind-main", clientId: "northwind-dental", name: "Northwind Dental", domain: "northwinddental.com", leadPathIds: ["northwind-contact", "northwind-booking"], leads: 142, deliveryRate: "100%", health: "Healthy", lastActivity: "08:31" },
  { id: "northwind-ortho", clientId: "northwind-dental", name: "Northwind Ortho", domain: "northwindortho.com", leadPathIds: ["northwind-ortho-contact"], leads: 0, deliveryRate: "—", health: "Healthy", lastActivity: "No recent activity" },
  { id: "smith-realty-site", clientId: "smith-realty", name: "Smith Realty", domain: "smithrealty.com", leadPathIds: ["smith-contact", "smith-viewing"], leads: 87, deliveryRate: "99.8%", health: "Healthy", lastActivity: "Yesterday" },
  { id: "pizza-roma-site", clientId: "pizza-roma", name: "Pizza Roma", domain: "pizzaroma.com", leadPathIds: ["pizza-contact"], leads: 24, deliveryRate: "100%", health: "Healthy", lastActivity: "Yesterday" },
  { id: "old-mill-site", clientId: "old-mill-studio", name: "Old Mill Studio", domain: "oldmillstudio.com", leadPathIds: ["old-mill-contact"], leads: 31, deliveryRate: "99.7%", health: "Healthy", lastActivity: "2 days ago" },
];

export const leadPaths: LeadPath[] = [
  { id: "keller-contact", siteId: "keller-solar-site", name: "Contact Us", status: "Attention", recentLeads: 31, destinations: ["Telegram", "CRM Webhook"], deliveryHealth: "96.2%", lastEvent: "08:50" },
  { id: "keller-quote", siteId: "keller-solar-site", name: "Quote Request", status: "Healthy", recentLeads: 17, destinations: ["Telegram", "CRM Webhook"], deliveryHealth: "100%", lastEvent: "Yesterday" },
  { id: "northwind-contact", siteId: "northwind-main", name: "Contact Us", status: "Healthy", recentLeads: 84, destinations: ["CRM Webhook", "Email"], deliveryHealth: "100%", lastEvent: "08:31" },
  { id: "northwind-booking", siteId: "northwind-main", name: "Book an Appointment", status: "Healthy", recentLeads: 58, destinations: ["CRM Webhook"], deliveryHealth: "100%", lastEvent: "Yesterday" },
  { id: "northwind-ortho-contact", siteId: "northwind-ortho", name: "Contact Us", status: "Healthy", recentLeads: 0, destinations: ["CRM Webhook"], deliveryHealth: "—", lastEvent: "No recent activity" },
  { id: "smith-contact", siteId: "smith-realty-site", name: "Contact Us", status: "Healthy", recentLeads: 52, destinations: ["CRM Webhook"], deliveryHealth: "100%", lastEvent: "Yesterday" },
  { id: "smith-viewing", siteId: "smith-realty-site", name: "Book a Viewing", status: "Healthy", recentLeads: 35, destinations: ["CRM Webhook"], deliveryHealth: "99.7%", lastEvent: "Yesterday" },
  { id: "pizza-contact", siteId: "pizza-roma-site", name: "Contact Us", status: "Healthy", recentLeads: 24, destinations: ["Email"], deliveryHealth: "100%", lastEvent: "Yesterday" },
  { id: "old-mill-contact", siteId: "old-mill-site", name: "Project Enquiry", status: "Healthy", recentLeads: 31, destinations: ["CRM Webhook"], deliveryHealth: "99.7%", lastEvent: "2 days ago" },
];

export const leads: Lead[] = [
  { id: "LD-2026-001245", clientId: "keller-solar", siteId: "keller-solar-site", leadPathId: "keller-contact", customerName: "Sarah Mitchell", email: "sarah@example.com", phone: "+49 151 23456789", message: "Hi, I'm interested in getting a quote for a solar panel installation for our house. Please contact me regarding the options and pricing. Thank you!", capturedAt: "Sep 20, 2026 — 08:42:31", state: "Captured safely", deliveryIds: ["delivery-telegram-001245", "delivery-keller-crm"] },
  { id: "lead-northwind-0831", clientId: "northwind-dental", siteId: "northwind-main", leadPathId: "northwind-contact", customerName: "Emily Carter", email: "emily@example.com", phone: "+1 555 0142", message: "I would like to book a consultation.", capturedAt: "Sep 20, 2026 — 08:31:02", state: "Captured safely", deliveryIds: ["delivery-northwind-001"] },
  { id: "lead-smith-001", clientId: "smith-realty", siteId: "smith-realty-site", leadPathId: "smith-contact", customerName: "Daniel Brooks", email: "daniel@example.com", phone: "+1 555 0187", message: "Could I arrange a viewing this week?", capturedAt: "Sep 19, 2026 — 14:22:00", state: "Captured safely", deliveryIds: ["delivery-smith-001"] },
  { id: "lead-pizza-001", clientId: "pizza-roma", siteId: "pizza-roma-site", leadPathId: "pizza-contact", customerName: "Marco Rossi", email: "marco@example.com", phone: "+1 555 0124", message: "I have a question about catering.", capturedAt: "Sep 19, 2026 — 11:04:00", state: "Captured safely", deliveryIds: ["delivery-pizza-001"] },
];

export const deliveries: Delivery[] = [
  { id: "delivery-telegram-001245", leadId: "LD-2026-001245", destination: "Telegram", state: "Delivered", attemptIds: ["attempt-telegram-1"], createdAt: "08:42:31", deliveredAt: "08:42:32" },
  { id: "delivery-keller-crm", leadId: "LD-2026-001245", destination: "CRM Webhook", state: "Delivered", attemptIds: ["attempt-crm-1", "attempt-crm-2", "attempt-crm-3", "attempt-crm-4"], createdAt: "08:42:31", deliveredAt: "08:50:03" },
  { id: "delivery-northwind-001", leadId: "lead-northwind-0831", destination: "CRM Webhook", state: "Delivered", attemptIds: ["attempt-northwind-1"], createdAt: "08:31:02", deliveredAt: "08:31:03" },
  { id: "delivery-smith-001", leadId: "lead-smith-001", destination: "CRM Webhook", state: "Awaiting retry", attemptIds: ["attempt-smith-1"], createdAt: "Yesterday 14:22", nextRetry: "In 4 minutes", lastError: "Connection timeout" },
  { id: "delivery-pizza-001", leadId: "lead-pizza-001", destination: "Email", state: "Failed", attemptIds: ["attempt-pizza-1"], createdAt: "Yesterday 11:04", lastError: "Mailbox unavailable" },
];

export const attempts: Attempt[] = [
  { id: "attempt-telegram-1", deliveryId: "delivery-telegram-001245", number: 1, result: "Succeeded", trigger: "Initial delivery", startedAt: "08:42:32", finishedAt: "08:42:32", duration: "0.8 s", providerStatus: "HTTP 200", providerMessage: "Message accepted" },
  { id: "attempt-crm-1", deliveryId: "delivery-keller-crm", number: 1, result: "Retryable failure", trigger: "Initial delivery", startedAt: "08:42:33", finishedAt: "08:42:38", duration: "5.02 s", providerStatus: "Timeout", providerMessage: "Connection timeout", nextRetry: "08:43:03" },
  { id: "attempt-crm-2", deliveryId: "delivery-keller-crm", number: 2, result: "Retryable failure", trigger: "Automatic retry", startedAt: "08:43:03", finishedAt: "08:43:08", duration: "5.02 s", providerStatus: "Timeout", providerMessage: "Connection timeout", nextRetry: "08:45:03" },
  { id: "attempt-crm-3", deliveryId: "delivery-keller-crm", number: 3, result: "Retryable failure", trigger: "Automatic retry", startedAt: "08:45:03", finishedAt: "08:45:08", duration: "5.02 s", providerStatus: "HTTP 503", providerMessage: "Service Unavailable", nextRetry: "08:50:03" },
  { id: "attempt-crm-4", deliveryId: "delivery-keller-crm", number: 4, result: "Succeeded", trigger: "Automatic retry", startedAt: "08:50:03", finishedAt: "08:50:03", duration: "2.3 s", providerStatus: "HTTP 200", providerMessage: "Lead accepted" },
  { id: "attempt-northwind-1", deliveryId: "delivery-northwind-001", number: 1, result: "Succeeded", trigger: "Initial delivery", startedAt: "08:31:03", finishedAt: "08:31:03", duration: "1.1 s", providerStatus: "HTTP 200", providerMessage: "Lead accepted" },
  { id: "attempt-smith-1", deliveryId: "delivery-smith-001", number: 1, result: "Retryable failure", trigger: "Initial delivery", startedAt: "Yesterday 14:22", finishedAt: "Yesterday 14:22", duration: "5.0 s", providerStatus: "Timeout", providerMessage: "Connection timeout", nextRetry: "In 4 minutes" },
  { id: "attempt-pizza-1", deliveryId: "delivery-pizza-001", number: 1, result: "Permanent failure", trigger: "Initial delivery", startedAt: "Yesterday 11:04", finishedAt: "Yesterday 11:04", duration: "1.4 s", providerStatus: "HTTP 550", providerMessage: "Mailbox unavailable" },
];

export const incidents: Incident[] = [{ id: "incident-keller-crm", clientId: "keller-solar", siteId: "keller-solar-site", destination: "CRM Webhook", title: "CRM Webhook delivery failures — Keller Solar", state: "Resolved automatically", startedAt: "Sep 20, 2026 — 08:43:03", resolvedAt: "Sep 20, 2026 — 08:50:03", duration: "7 minutes", affectedLeads: 31, peakFailureRate: "62%", attemptIds: ["attempt-crm-1", "attempt-crm-2", "attempt-crm-3", "attempt-crm-4"] }];

export const activities: Activity[] = [
  { id: "activity-1", time: "08:50", title: "CRM Webhook recovered", detail: "Keller Solar", status: "Delivered", tone: "good", category: "delivery", target: { type: "delivery", id: "delivery-keller-crm" } },
  { id: "activity-2", time: "08:45", title: "Retry scheduled", detail: "Keller Solar", status: "Awaiting retry", tone: "warn", category: "delivery", target: { type: "delivery", id: "delivery-keller-crm" } },
  { id: "activity-3", time: "08:43", title: "Incident opened", detail: "Keller Solar · CRM Webhook", status: "Investigating", tone: "bad", category: "incident", target: { type: "incident", id: "incident-keller-crm" } },
  { id: "activity-4", time: "08:42", title: "Lead captured", detail: "Keller Solar", status: "Captured safely", tone: "good", category: "capture", target: { type: "lead", id: "LD-2026-001245" } },
  { id: "activity-5", time: "08:31", title: "Lead captured", detail: "Northwind Dental", status: "Captured safely", tone: "good", category: "capture", target: { type: "lead", id: "lead-northwind-0831" } },
];

export const deliveryBreakdown = [
  { label: "Delivered", value: 1401, tone: "good" as const },
  { label: "Awaiting retry", value: 18, tone: "warn" as const },
  { label: "Failed", value: 13, tone: "bad" as const },
  { label: "Unknown", value: 4, tone: "neutral" as const },
];

export const getMockClient = (id: string) => clients.find((item) => item.id === id);
export const getMockSite = (id: string) => sites.find((item) => item.id === id);
export const getMockLeadPath = (id: string) => leadPaths.find((item) => item.id === id);
export const getMockLead = (id: string) => leads.find((item) => item.id === id);
export const getMockDelivery = (id: string) => deliveries.find((item) => item.id === id);
export const getMockAttempt = (id: string) => attempts.find((item) => item.id === id);
export const getMockIncident = (id: string) => incidents.find((item) => item.id === id);

export function getClientForSite(siteId: string) { const site = getMockSite(siteId); return site ? getMockClient(site.clientId) : undefined; }
export function getSiteForLead(leadId: string) { const lead = getMockLead(leadId); return lead ? getMockSite(lead.siteId) : undefined; }
export function getLeadForDelivery(deliveryId: string) { const delivery = getMockDelivery(deliveryId); return delivery ? getMockLead(delivery.leadId) : undefined; }
export function getDeliveryForAttempt(attemptId: string) { const attempt = getMockAttempt(attemptId); return attempt ? getMockDelivery(attempt.deliveryId) : undefined; }
