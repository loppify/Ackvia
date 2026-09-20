import { DeliveryDetailPage } from "@/features/dashboard/pages";
export default async function Page({ params }: { params: Promise<{ deliveryId: string }> }) { return <DeliveryDetailPage deliveryId={(await params).deliveryId} />; }
