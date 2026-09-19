"use client";

import { Fault, Mark } from "@/features/desk/primitives";
import Link from "next/link";

export default function Error({ reset }: { reset: () => void }) {
  return <main className="standalone-state"><Link className="brand" href="/"><Mark />ackvia.</Link><Fault error={{ title: "The investigation desk could not load", message: "Your captured evidence is stored separately. Try loading the workspace again." }} onRetry={reset} /><Link className="button" href="/">Open the desk</Link></main>;
}
