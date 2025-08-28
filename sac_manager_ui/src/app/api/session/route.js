import { NextResponse } from "next/server";
import { SignJWT } from "jose";

const alg = "HS256";

const SECURE_COOKIE =
  (process.env.COOKIE_SECURE ??
    (process.env.NODE_ENV === "production" ? "true" : "false")) === "true";

async function sign(payload) {
  const secret = new TextEncoder().encode(process.env.SAC_MANAGER_KEY);
  return await new SignJWT(payload)
    .setProtectedHeader({ alg })
    .setIssuedAt()
    .setExpirationTime("8h")
    .sign(secret);
}

export async function POST(req) {
  const { password } = await req.json();

  if (password !== process.env.SAC_MANAGER_KEY) {
    return NextResponse.json(
      { error: "Credenciales inválidas" },
      { status: 401, valor: process.env.SAC_MANAGER_KEY }
    );
  }

  const token = await sign({ sub: "dashboard", role: "admin" });
  const res = NextResponse.json({ ok: true });
  res.cookies.set("auth_token", token, {
    httpOnly: true,
    sameSite: "lax",
    secure: SECURE_COOKIE,
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set("auth_token", "", { path: "/", maxAge: 0 });
  return res;
}
