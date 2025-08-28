import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { jwtVerify } from "jose";

const alg = "HS256";

async function verify(token) {
  const secret = new TextEncoder().encode(process.env.SAC_MANAGER_KEY);
  const { payload } = await jwtVerify(token, secret, { algorithms: [alg] });
  return payload;
}

export default async function ManagerUILayout({ children }) {
  const cookieStore = await cookies();
  const token = cookieStore.get("auth_token")?.value;

  if (!token) {
    redirect(`/ManagerLogin`);
  }

  try {
    await verify(token);
  } catch {
    redirect(`/ManagerLogin`);
  }

  return <>{children}</>;
}
