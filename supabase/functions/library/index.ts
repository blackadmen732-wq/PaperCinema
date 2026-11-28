// PaperCinema library gateway (Mark, 28 Nov: the free models turned into paper, stored and catalogued in Supabase).
// Deployed to the project papercinema (ref pkqbqlhgffqatgryofxt) as the edge function 'library', verify_jwt off: it
// does its own check. The pipeline (tools/library.py) never holds the project's secret key: this function runs with
// the service role Supabase gives every edge function and answers only requests carrying the library token, which it
// reads from public.pc_secrets (RLS on, no policies). Files move through signed URLs, straight between caller and Storage.
//   ?op=upload-url&path=P   -> { signedUrl, token, path }   (PUT the file to signedUrl)
//   ?op=download-url&path=P -> { signedUrl }                 (GET it within the hour)
//   ?op=list&path=PREFIX    -> the objects under PREFIX
//   ?op=upsert-row (POST a pc_library row as JSON) -> the stored row
//   ?op=rows[&kind=K][&tag=T] -> the catalogue
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const BUCKET = "pc-library";
const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});
let token: string | null = null;

const json = (o: unknown, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json" } });

Deno.serve(async (req: Request) => {
  if (token === null) {
    const { data, error } = await sb.from("pc_secrets").select("value").eq("name", "library_token").single();
    if (error || !data) return json({ error: "no library token configured" }, 500);
    token = data.value as string;
  }
  if (!token || req.headers.get("x-pc-token") !== token) return json({ error: "forbidden" }, 403);
  const u = new URL(req.url);
  const op = u.searchParams.get("op") ?? "";
  const path = (u.searchParams.get("path") ?? "").replace(/^\/+/, "");
  try {
    if (op === "upload-url") {
      if (!path) return json({ error: "path?" }, 400);
      const { data, error } = await sb.storage.from(BUCKET).createSignedUploadUrl(path, { upsert: true });
      if (error) throw error;
      return json(data);
    }
    if (op === "download-url") {
      if (!path) return json({ error: "path?" }, 400);
      const { data, error } = await sb.storage.from(BUCKET).createSignedUrl(path, 3600);
      if (error) throw error;
      return json(data);
    }
    if (op === "list") {
      const { data, error } = await sb.storage.from(BUCKET).list(path, { limit: 1000, sortBy: { column: "name", order: "asc" } });
      if (error) throw error;
      return json(data);
    }
    if (op === "upsert-row") {
      const row = await req.json();
      if (!row || typeof row.id !== "string" || !row.kind || !row.source) return json({ error: "a row needs id, kind, source" }, 400);
      row.updated_at = new Date().toISOString();
      const { data, error } = await sb.from("pc_library").upsert(row).select();
      if (error) throw error;
      return json(data);
    }
    if (op === "rows") {
      let q = sb.from("pc_library").select("*").order("id");
      const kind = u.searchParams.get("kind");
      if (kind) q = q.eq("kind", kind);
      const tag = u.searchParams.get("tag");
      if (tag) q = q.contains("tags", [tag]);
      const { data, error } = await q;
      if (error) throw error;
      return json(data);
    }
    return json({ error: "op must be upload-url | download-url | list | upsert-row | rows" }, 400);
  } catch (e) {
    return json({ error: String((e as Error)?.message ?? e) }, 500);
  }
});
