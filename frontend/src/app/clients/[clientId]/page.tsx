import { ClientDetailPage } from "@/features/dashboard/pages";
export default async function Page({ params }: { params: Promise<{ clientId: string }> }) { return <ClientDetailPage clientId={(await params).clientId} />; }
