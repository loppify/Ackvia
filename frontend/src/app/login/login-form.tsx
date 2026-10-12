"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export function LoginForm({ setupUrl }: { setupUrl: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");

    const data = new FormData(event.currentTarget);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: data.get("email"),
        password: data.get("password"),
      }),
    });

    if (response.ok) {
      router.replace("/");
      router.refresh();
      return;
    }

    let message = "Sign in failed.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {}

    setError(message);
    setPending(false);
  }

  return <main className="login-page">
    <section className="login-card">
      <div className="login-brand"><span>AV</span><strong>Ackvia</strong></div>
      <div><p className="eyebrow">LEAD EVIDENCE</p><h1>Sign in</h1><p className="login-intro">Investigate captured submissions, delivery outcomes, and retry history.</p></div>
      <form onSubmit={submit}>
        <label>Email<input name="email" type="email" autoComplete="email" required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
        {error && <p className="login-error" role="alert">{error}</p>}
        <button className="login-submit" type="submit" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="login-setup">Need an account or workspace? <a href={setupUrl}>Open setup</a></p>
    </section>
  </main>;
}
