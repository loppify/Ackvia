import { redirect } from "next/navigation";
import { offsetValue } from "@/features/desk/model";

export default async function Submission({ params, searchParams }: PageProps<"/forms/[formId]/submissions/[submissionId]">) {
  const { formId, submissionId } = await params;
  const query = new URLSearchParams({ form: formId, submission: submissionId, offset: String(offsetValue((await searchParams).offset)) });
  redirect(`/?${query}`);
}
