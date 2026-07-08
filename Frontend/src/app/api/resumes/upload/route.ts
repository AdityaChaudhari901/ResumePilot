import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const formData = await request.formData();
  return proxyBackendResponse("/resumes/upload", {
    method: "POST",
    body: formData
  });
}
