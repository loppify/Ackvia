import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { LoginForm } from "./login-form";

export default async function LoginPage() {
  if ((await cookies()).has("ackvia_session")) redirect("/");

  const setupUrl = process.env.ACKVIA_API_BASE_URL?.replace(/\/$/, "") ?? "#";
  return <LoginForm setupUrl={setupUrl} />;
}
