import { redirect } from "next/navigation";
import { deskUrl, offsetValue } from "@/features/desk/model";

export default async function Forms({ searchParams }: PageProps<"/forms">) {
  const query = await searchParams;
  redirect(deskUrl({ formsOffset: offsetValue(query.offset) }));
}
