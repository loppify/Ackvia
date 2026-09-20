import { IncidentDetailPage } from "@/features/dashboard/pages";
export default async function Page({ params }: { params: Promise<{ incidentId: string }> }) { return <IncidentDetailPage incidentId={(await params).incidentId} />; }
