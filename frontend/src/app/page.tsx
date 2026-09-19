import { loadDesk } from "@/features/desk/load";
import { Desk } from "@/features/desk/desk";

export default async function Page({ searchParams }: PageProps<"/">) {
  return <Desk snapshot={await loadDesk(await searchParams)} />;
}
