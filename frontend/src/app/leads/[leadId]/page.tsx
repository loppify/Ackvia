import { LeadDetailPage } from "@/features/dashboard/pages";
export default async function Page({ params }: { params: Promise<{ leadId: string }> }) { return <LeadDetailPage leadId={(await params).leadId} />; }
