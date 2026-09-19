import { getSubmission } from "@/lib/api";
import { readResource } from "@/features/desk/load";
import { numericId } from "@/features/desk/model";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const id = numericId((await params).id);
  const headers = { "Cache-Control": "no-store, max-age=0" };
  if (id === null) return Response.json({ error: "Invalid submission ID" }, { status: 400, headers });
  const result = await readResource("Submission evidence", () => getSubmission(id));
  return Response.json(result, { status: result.error ? result.error.status ?? 502 : 200, headers });
}
