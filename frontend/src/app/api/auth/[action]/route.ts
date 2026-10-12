const allowedActions = new Set(["login", "register", "logout"]);

function apiBaseUrl(): string {
  const value = process.env.ACKVIA_API_BASE_URL;

  if (!value) throw new Error("ACKVIA_API_BASE_URL is not configured");
  return value.replace(/\/$/, "");
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const { action } = await params;

  if (!allowedActions.has(action)) {
    return Response.json({ detail: "Auth action not found" }, { status: 404 });
  }

  try {
    const body = action === "logout" ? undefined : await request.text();
    const session = request.headers.get("cookie");
    const backendResponse = await fetch(`${apiBaseUrl()}/api/auth/${action}`, {
      method: "POST",
      cache: "no-store",
      body,
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(session ? { Cookie: session } : {}),
      },
    });
    const responseBody = await backendResponse.text();
    const response = new Response(responseBody || null, {
      status: backendResponse.status,
      headers: {
        "Cache-Control": "no-store, max-age=0",
        ...(responseBody ? { "Content-Type": backendResponse.headers.get("content-type") ?? "application/json" } : {}),
      },
    });
    const setCookie = backendResponse.headers.get("set-cookie");

    if (setCookie) response.headers.append("set-cookie", setCookie);
    return response;
  } catch {
    return Response.json(
      { detail: "Ackvia authentication is unavailable" },
      { status: 502, headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  }
}
