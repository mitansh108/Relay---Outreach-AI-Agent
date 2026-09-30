"use client";

import { useEffect, useState, type ReactNode, type FormEvent } from "react";
import { supabase, usesSupabase } from "@/lib/supabase";
import { request } from "@/lib/api";
import "./access.css";

type Workspace = { id: string; name: string; role: string };

export default function WorkspaceAccess({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(!usesSupabase);
  const [loading, setLoading] = useState(usesSupabase);
  const [signedIn, setSignedIn] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [active, setActive] = useState<Workspace | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [signup, setSignup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!usesSupabase) return;
    let mounted = true;
    let sequence = 0;
    async function load() {
      const current = ++sequence;
      try {
        const { data } = await supabase().auth.getSession();
        if (!mounted || sequence !== current) return;
        setReady(false);
        setSignedIn(Boolean(data.session));
        if (!data.session) {
          setWorkspaces([]); setActive(null); sessionStorage.removeItem("relay.workspace");
          return;
        }
        const result = await request<{ items: Workspace[]; email: string }>("/workspaces");
        if (!mounted || sequence !== current) return;
        setEmail(result.email);
        setWorkspaces(result.items);
        const chosen = result.items.find(w => w.id === sessionStorage.getItem("relay.workspace"));
        if (chosen) { setActive(chosen); setReady(true); }
      } catch (err) {
        if (mounted && sequence === current) setError(err instanceof Error ? err.message : "Could not load your account.");
      } finally { if (mounted && sequence === current) setLoading(false); }
    }
    void load();
    let unsubscribe = () => {};
    try {
      const { data } = supabase().auth.onAuthStateChange((event) => {
        if (event === "SIGNED_OUT" || event === "SIGNED_IN") {
          // Schedule outside the auth callback to avoid SDK lock contention.
          window.setTimeout(() => { if (mounted) void load(); }, 0);
        }
      });
      unsubscribe = () => data.subscription.unsubscribe();
    } catch { /* load() exposes missing configuration */ }
    return () => { mounted = false; unsubscribe(); };
  }, []);

  async function authenticate(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const result = signup
        ? await supabase().auth.signUp({ email, password, options: { emailRedirectTo: `${window.location.origin}/workspace` } })
        : await supabase().auth.signInWithPassword({ email, password });
      if (result.error) throw result.error;
      setPassword("");
      if (signup && !result.data.session) setNotice("Check your email to confirm your account, then sign in.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not sign in. Try again."); }
    finally { setBusy(false); }
  }

  function select(workspace: Workspace) {
    sessionStorage.setItem("relay.workspace", workspace.id);
    setActive(workspace); setReady(true); setError("");
  }

  async function create(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const workspace = await request<Workspace>("/workspaces", { method: "POST", body: JSON.stringify({ name: workspaceName }) });
      setWorkspaces(items => [...items, workspace]); select(workspace); setWorkspaceName("");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create your workspace."); }
    finally { setBusy(false); }
  }

  async function signOut() {
    setBusy(true); setError("");
    try {
      const { error: signOutError } = await supabase().auth.signOut({ scope: "local" });
      if (signOutError) throw signOutError;
      sessionStorage.removeItem("relay.workspace"); setActive(null); setReady(false); setSignedIn(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not sign out."); }
    finally { setBusy(false); }
  }

  if (!usesSupabase) return children;
  if (loading) return <main className="access-screen"><p role="status">Loading your account…</p></main>;
  if (ready && active) return <><div className="account-bar"><span>{active.name} · {email}</span><div><button onClick={() => setReady(false)}>Switch workspace</button><button disabled={busy} onClick={signOut}>Sign out</button></div>{error && <span role="alert">{error}</span>}</div><div key={active.id}>{children}</div></>;
  return <main className="access-screen"><section className="access-form" aria-labelledby="access-title"><a className="access-brand" href="/">relay.</a><h1 id="access-title">{signedIn ? "Your workspace" : signup ? "Create your account" : "Welcome back"}</h1><p>{signedIn ? "Choose a workspace or create one for your contacts and connections." : "Sign in to manage your contacts and connected accounts."}</p>{error && <p className="access-error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {signedIn ? <><ul className="workspace-list">{workspaces.map(w => <li key={w.id}><button onClick={() => select(w)}>{w.name}<span>Open workspace</span></button></li>)}</ul><form onSubmit={create}><label htmlFor="workspace-name">New workspace name</label><input id="workspace-name" required maxLength={100} value={workspaceName} onChange={e => setWorkspaceName(e.target.value)} autoComplete="organization"/><button className="button primary" disabled={busy || !workspaceName.trim()}>{busy ? "Creating…" : "Create workspace"}</button></form><button className="access-link" disabled={busy} onClick={signOut}>Sign out</button></> : <><form onSubmit={authenticate}><label htmlFor="account-email">Email</label><input id="account-email" type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)}/><label htmlFor="account-password">Password</label><input id="account-password" type="password" required minLength={signup ? 8 : undefined} autoComplete={signup ? "new-password" : "current-password"} value={password} onChange={e => setPassword(e.target.value)}/><button className="button primary" disabled={busy}>{busy ? "Please wait…" : signup ? "Create account" : "Sign in"}</button></form><button className="access-link" onClick={() => { setSignup(!signup); setError(""); setNotice(""); }}>{signup ? "Already have an account? Sign in" : "Create an account"}</button></>}
  </section></main>;
}
