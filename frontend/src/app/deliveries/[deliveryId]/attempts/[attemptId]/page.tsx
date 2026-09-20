import { AttemptDetailPage } from "@/features/dashboard/pages";
export default async function Page({ params }: { params: Promise<{ deliveryId: string; attemptId: string }> }) { const resolved = await params; return <AttemptDetailPage deliveryId={resolved.deliveryId} attemptId={resolved.attemptId} />; }
