import { redirect } from "next/navigation";
import { offsetValue } from "@/features/desk/model";

export default async function Form({ params, searchParams }: PageProps<"/forms/[formId]">) {
  const { formId } = await params;
  const query = new URLSearchParams({ form: formId, offset: String(offsetValue((await searchParams).offset)) });
  redirect(`/?${query}`);
}
