import { Desk } from "@/features/desk/desk";
import { loadDesk } from "@/features/desk/load";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

export default async function Page({ searchParams }: PageProps<"/">) {
  if (!(await cookies()).has("ackvia_session")) redirect("/login");

  const snapshot = await loadDesk(await searchParams);

  return <Desk snapshot={snapshot} />;
}
