import { redirect } from "next/navigation";
import { offsetValue } from "@/features/desk/model";

export default async function Delivery({ params, searchParams }: PageProps<"/forms/[formId]/submissions/[submissionId]/deliveries/[deliveryId]">) {
  const { formId, submissionId, deliveryId } = await params;
  const query = new URLSearchParams({ form: formId, submission: submissionId, delivery: deliveryId, offset: String(offsetValue((await searchParams).offset)) });
  redirect(`/?${query}`);
}
