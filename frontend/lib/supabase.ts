"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export const usesSupabase = process.env.NEXT_PUBLIC_AUTH_MODE === "supabase";
let client: SupabaseClient | undefined;

export function supabase(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) throw new Error("Sign-in is not configured. Set the Supabase project URL and publishable key.");
  client ??= createClient(url, key);
  return client;
}

export async function sessionHeaders(): Promise<Record<string, string>> {
  if (!usesSupabase) return {};
  const { data, error } = await supabase().auth.getSession();
  if (error || !data.session) throw new Error("Sign in to continue.");
  const workspace = sessionStorage.getItem("relay.workspace") || "";
  return { Authorization: `Bearer ${data.session.access_token}`, "X-Workspace-ID": workspace };
}
