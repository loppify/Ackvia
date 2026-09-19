import { Mark } from "@/features/desk/primitives";
import Link from "next/link";

export default function NotFound() {
  return <main className="standalone-state"><Link className="brand" href="/"><Mark />ackvia.</Link><h1>This route doesn’t exist.</h1><p className="muted">Return to the investigation desk to choose a form and submission.</p><Link className="button" href="/">Open the desk</Link></main>;
}
