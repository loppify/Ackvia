import { SiteDetailPage } from "@/features/dashboard/pages";
export default async function Page({ params }: { params: Promise<{ siteId: string }> }) { return <SiteDetailPage siteId={(await params).siteId} />; }
