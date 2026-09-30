"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Contact, Recommendation, asList, initials, niceDate, request, downloadContacts } from "@/lib/api";

import ProviderLogo from "@/components/ProviderLogo";
import WorkspaceAccess from "./components/WorkspaceAccess";
import { usesSupabase } from "@/lib/supabase";

import ModelSettings from "./components/ModelSettings";
import OutreachDesk from "./components/OutreachDesk";
import "./desk.css";

type View = "today" | "contacts" | "review" | "activity" | "insights" | "experiments" | "connections";
type Summary = { total: number; due_today: number; overdue: number; upcoming: number; pending_reviews: number; sent: number; simulated: number };
type Connection = { sender_email?: string | null; provider: string; status: string; last_sync_at?: string | null; last_error?: string | null; sync_count?: number };
type CsvPreview = { valid_rows: Contact[]; errors: { line: number; reason: string }[]; count: number };
type Experiment = { id: string; name: string; status: string; config: { hypothesis?: string; variable: string; variants: { id: string; value: string; weight: number }[]; start_date: string; end_date: string; min_per_variant: number } };
type ExperimentResults = { variants: { variant_id: string; sent: number; replied: number; converted?: number; opted_out: number; reply_rate: number }[]; winner?: string | null; reason?: string; status?: string };
type ContactDetail = Contact & { activities?: Activity[]; recommendations?: Recommendation[] };
const experimentValues: Record<string, [string, string]> = { tone: ["friendly", "professional"], length: ["short", "detailed"], cta: ["soft", "direct"] };
const nav: { id: View; label: string; icon: string }[] = [
  { id: "today", label: "Today", icon: "◫" },
  { id: "contacts", label: "Contacts", icon: "◎" },
  { id: "review", label: "Review inbox", icon: "✎" },
  { id: "activity", label: "Activity", icon: "◷" },
  { id: "insights", label: "Insights", icon: "▥" },
  { id: "experiments", label: "Experiments", icon: "◇" },
  { id: "connections", label: "Connections", icon: "⌘" },
];
const headings: Record<View, { eyebrow: string; title: string; desc: string }> = {
  today: { eyebrow: "YOUR WORKSPACE", title: "Good morning. Let’s follow through.", desc: "A clear view of the relationships that need your attention." },
  contacts: { eyebrow: "YOUR PEOPLE", title: "Every relationship, in one place.", desc: "Find context, review history, and plan the next move." },
  review: { eyebrow: "HUMAN IN THE LOOP", title: "Your review inbox.", desc: "Nothing is sent until you approve the exact message." },
  activity: { eyebrow: "THE RECORD", title: "A timeline of progress.", desc: "Every recommendation, decision, and send in one place." },
  insights: { eyebrow: "WHAT HAPPENED", title: "Measure the follow-through.", desc: "Observed activity from this workspace, without invented outcomes." },
  experiments: { eyebrow: "LEARN WHAT WORKS", title: "Test one idea at a time.", desc: "Run a careful two-variant message test and track observed outcomes." },
  connections: { eyebrow: "YOUR DATA", title: "Connected workspace.", desc: "See where contacts come from and how messages are delivered." },
};

function actionText(action?: string) {
  return ({ email: "Draft email", call_task: "Plan a call", wait: "Wait", no_action: "No action" } as Record<string, string>)[action || ""] || "Review contact";
}
function statusClass(bucket?: string) {
  const label = (bucket || "").toLowerCase();
  return label.includes("overdue") ? "pill danger" : label.includes("today") ? "pill amber" : "pill subtle";
}
function getEmail(contact: Contact) { return contact.contact || contact.email || ""; }

export default function Home() {
  return <WorkspaceAccess><WorkspaceContent /></WorkspaceAccess>;
}

function WorkspaceContent() {
  const [view, setView] = useState<View>("today");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [mode, setMode] = useState("demo");
  const [activities, setActivities] = useState<Activity[]>([]);
  const [pendingReviews, setPendingReviews] = useState<Recommendation[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [experimentResults, setExperimentResults] = useState<Record<string, ExperimentResults>>({});
  const [testName, setTestName] = useState("A warmer follow-up");
  const [testHypothesis, setTestHypothesis] = useState("A warm, conversational tone will encourage more replies than a direct tone.");
  const [testVariable, setTestVariable] = useState("tone");
  const [variantA, setVariantA] = useState("friendly");
  const [variantB, setVariantB] = useState("professional");
  const [senderEmail, setSenderEmail] = useState("");
  const [connections, setConnections] = useState<Connection[]>([]);
  const [insights, setInsights] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<ContactDetail | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  const [csvText, setCsvText] = useState("");
  const [csvFileName, setCsvFileName] = useState("");
  const [csvPreview, setCsvPreview] = useState<CsvPreview | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [contactData, summaryData, activityData, insightData, connectionData, reviewData, experimentData, healthData] = await Promise.all([
        request<unknown>("/contacts"), request<Summary>("/summary"), request<unknown>("/activity"),
        request<Record<string, number>>("/insights"), request<unknown>("/connections"), request<unknown>("/recommendations?status=pending"), request<unknown>("/experiments"), request<{mode: string}>("/health"),
      ]);
      setContacts(asList<Contact>(contactData, "items"));
      setSummary(summaryData);
      setActivities(asList<Activity>(activityData, "items"));
      setPendingReviews(asList<Recommendation>(reviewData, "items"));
      setExperiments(asList<Experiment>(experimentData, "items"));
      setInsights(insightData);
      const connected = asList<Connection>(connectionData, "items");
      setConnections(connected);
      setSenderEmail(connected.find(c => c.provider === "gmail")?.sender_email || "");
      setMode(healthData.mode || "demo");
      setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load the workspace."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { if (window.location.pathname === "/connections") setView("connections"); }, []);

  const visible = useMemo(() => contacts.filter(contact => {
    const haystack = `${contact.name} ${contact.company} ${getEmail(contact)} ${contact.notes}`.toLowerCase();
    const matchSearch = haystack.includes(search.trim().toLowerCase());
    const matchFilter = filter === "All" || (filter === "Needs attention" ? ["overdue", "due today"].includes((contact.bucket || "").toLowerCase()) : (contact.bucket || "").toLowerCase() === filter.toLowerCase());
    return matchSearch && matchFilter;
  }), [contacts, search, filter]);
  const focusContacts = contacts.filter(contact => ["overdue", "due today"].includes((contact.bucket || "").toLowerCase()) && !contact.replied && !contact.do_not_contact);
  const pending = selected?.recommendations?.find(item => ["pending", "draft", "proposed"].includes(item.status)) || null;

  useEffect(() => { experiments.forEach(experiment => { void request<ExperimentResults>(`/experiments/${experiment.id}/results`).then(result => setExperimentResults(current => ({ ...current, [experiment.id]: result }))).catch(() => {}); }); }, [experiments]);

  async function openContact(contact: Contact) {
    setError(""); setBusy(true);
    try {
      const detail = await request<ContactDetail>(`/contacts/${contact.id}`);
      setSelected(detail); setRecommendation(null); setView("contacts"); setMobileNav(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not open contact."); }
    finally { setBusy(false); }
  }

  async function generate(contact: Contact) {
    setBusy(true); setError(""); setNotice("");
    try {
      const rec = await request<Recommendation>(`/recommendations/${contact.id}`, { method: "POST" });
      setRecommendation(rec); setSubject(rec.subject || rec.draft?.subject || ""); setBody(rec.body || rec.draft?.body || "");
      const detail = await request<ContactDetail>(`/contacts/${contact.id}`);
      setSelected(detail); setView("review"); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not prepare a recommendation."); }
    finally { setBusy(false); }
  }

  async function loadReview(contact: Contact, target?: Recommendation) {
    setBusy(true); setError("");
    try {
      const detail = await request<ContactDetail>(`/contacts/${contact.id}`);
      setSelected(detail);
      const rec = target ? (detail.recommendations || []).find(item => item.id === target.id) : (detail.recommendations || []).find(item => ["pending", "draft", "proposed", "approved"].includes(item.status));
      setRecommendation(rec || null);
      setSubject(rec?.subject || rec?.draft?.subject || ""); setBody(rec?.body || rec?.draft?.body || "");
      setView("review"); setMobileNav(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not open review."); }
    finally { setBusy(false); }
  }

  async function saveDraft() {
    if (!recommendation) return;
    setBusy(true); setError("");
    try {
      const rec = await request<Recommendation>(`/recommendations/${recommendation.id}/draft`, { method: "PATCH", body: JSON.stringify({ subject, body }) });
      setRecommendation(rec); setNotice("Draft saved. Approve this version when it is ready.");
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the draft."); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!recommendation) return;
    setBusy(true); setError("");
    try {
      let current = recommendation;
      if (subject !== (current.subject || current.draft?.subject || "") || body !== (current.body || current.draft?.body || "")) {
        current = await request<Recommendation>(`/recommendations/${current.id}/draft`, { method: "PATCH", body: JSON.stringify({ subject, body }) });
      }
      current = await request<Recommendation>(`/reviews/${current.id}/approve`, { method: "POST", body: JSON.stringify({ version: current.version || current.draft?.version, recipient: selected ? getEmail(selected) : "" }) });
      setRecommendation(current); setNotice("Approved. You can now send this exact draft."); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not approve the draft."); }
    finally { setBusy(false); }
  }

  async function send() {
    if (!recommendation) return;
    setBusy(true); setError("");
    try {
      const result = await request<{ status: string; error?: string }>(`/sends/${recommendation.id}`, { method: "POST", body: "{}" });
      if (result.status === "failed") throw new Error(result.error || "Gmail send was not confirmed. Check Gmail before taking further action.");
      setNotice(result.status === "simulated" ? "Simulated send recorded. No real email was delivered." : "Email sent and recorded.");
      setRecommendation({ ...recommendation, status: result.status }); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not send the approved draft."); }
    finally { setBusy(false); }
  }

  async function skip() {
    if (!recommendation) return;
    setBusy(true); setError("");
    try {
      const rec = await request<Recommendation>(`/reviews/${recommendation.id}/skip`, { method: "POST", body: "{}" });
      setRecommendation(rec); setNotice("Skipped. No message was sent."); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not skip this draft."); }
    finally { setBusy(false); }
  }

  async function markReplied() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      await request(`/contacts/${selected.id}`, { method: "PATCH", body: JSON.stringify({ replied: true }) });
      setSelected({ ...selected, replied: true }); setNotice(`${selected.name} marked as replied.`); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update the contact."); }
    finally { setBusy(false); }
  }

  async function markConverted() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const result = await request<{ recorded: number }>(`/contacts/${selected.id}/converted`, { method: "POST", body: "{}" });
      setNotice(result.recorded ? `${selected.name} marked converted for their experiment.` : "Conversion recorded in activity. No exposed experiment assignment was found.");
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not record conversion."); }
    finally { setBusy(false); }
  }

  async function resetDemo() {
    setBusy(true); setError("");
    try {
      await request("/demo/reset", { method: "POST", body: "{}" });
      setSelected(null); setRecommendation(null); setNotice("Sample workspace reset."); setView("today"); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not reset the sample workspace."); }
    finally { setBusy(false); }
  }

  async function createExperiment() {
    setBusy(true); setError("");
    try {
      const start = new Date(); const end = new Date(start); end.setDate(end.getDate() + 21);
      await request("/experiments", { method: "POST", body: JSON.stringify({ name: testName.trim(), hypothesis: testHypothesis.trim(), variable: testVariable, start_date: start.toISOString().slice(0,10), end_date: end.toISOString().slice(0,10), min_per_variant: 100, response_window_days: 7, variants: [{ id: "A", value: variantA.trim(), weight: 50 }, { id: "B", value: variantB.trim(), weight: 50 }] }) });
      setNotice("Experiment started. New eligible recommendations will be assigned consistently to A or B."); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not start the experiment."); }
    finally { setBusy(false); }
  }

  async function setExperimentStatus(experiment: Experiment) {
    setBusy(true); setError("");
    try { await request(`/experiments/${experiment.id}/${experiment.status === "active" ? "pause" : "start"}`, { method: "POST", body: "{}" }); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not change the experiment."); }
    finally { setBusy(false); }
  }

  async function connect(provider: string) {
    setBusy(true); setError("");
    try { const result = await request<{ authorization_url: string }>(`/oauth/${provider}/start`); window.location.assign(result.authorization_url); }
    catch (err) { setError(err instanceof Error ? err.message : `Could not connect ${provider}.`); setBusy(false); }
  }

  async function disconnect(provider: string) {
    setBusy(true); setError("");
    try { await request(`/connections/${provider}/disconnect`, { method: "POST", body: "{}" }); setNotice(`${provider} disconnected.`); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : `Could not disconnect ${provider}.`); }
    finally { setBusy(false); }
  }

  async function syncHubspot() {
    setBusy(true); setError("");
    try { const result = await request<{ synced: number }>("/connections/hubspot/sync", { method: "POST", body: "{}" }); setNotice(`${result.synced} contacts synced from HubSpot.`); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not sync HubSpot."); }
    finally { setBusy(false); }
  }

  async function previewCsv() {
    setBusy(true); setError("");
    try { const result = await request<CsvPreview>("/import/preview", { method: "POST", body: JSON.stringify({ csv_text: csvText }) }); setCsvPreview(result); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not preview CSV."); }
    finally { setBusy(false); }
  }

  async function importCsv() {
    setBusy(true); setError("");
    try { const result = await request<{ imported: number }>("/import/commit", { method: "POST", body: JSON.stringify({ csv_text: csvText }) }); setNotice(`${result.imported} contacts imported.`); setCsvText(""); setCsvFileName(""); setCsvPreview(null); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not import CSV."); }
    finally { setBusy(false); }
  }

  const setPage = (page: View) => { setView(page); setMobileNav(false); setError(""); setNotice(""); };
  const reviewCount = summary?.pending_reviews || 0;
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
      <div className="brand"><div className="brand-symbol">↗</div><div><strong>relay<span>.</span></strong><small>FOLLOW-UP COPILOT</small></div></div>
      <div className="workspace-card"><span className="workspace-avatar">S</span><div><strong>{usesSupabase ? "Your workspace" : "Sample workspace"}</strong><small>{usesSupabase ? "Connected account" : "Demo environment"}</small></div><span className="workspace-chevron">⌄</span></div>
      <div className="nav-caption">WORKSPACE</div>
      <nav aria-label="Main navigation">{nav.map(item => <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} onClick={() => setPage(item.id)}><span className="nav-icon">{item.icon}</span><span>{item.label}</span>{item.id === "review" && reviewCount > 0 && <span className="nav-count">{reviewCount}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="demo-indicator"><span className="demo-dot"/><div><strong>{mode === "demo" ? "Demo mode is on" : "Live workspace"}</strong><small>{mode === "demo" ? "Messages are simulated" : "Review every send"}</small></div></div><div className="sidebar-foot">Built for meaningful follow-through.</div></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><button className="mobile-menu" onClick={() => setMobileNav(!mobileNav)} aria-label="Toggle menu">☰</button><div className="breadcrumb">Workspace <span>/</span> {nav.find(item => item.id === view)?.label}</div><div className="topbar-right"><span className="mode-chip"><span className="demo-dot"/> {mode === "demo" ? "SAMPLE DATA" : "LIVE MODE"}</span><span className="profile-avatar">S</span></div></header>
      <div className="page-content"><div className="page-heading"><div><div className="eyebrow">{headings[view].eyebrow}</div><h1>{headings[view].title}</h1><p>{headings[view].desc}</p></div><div className="heading-actions">{view === "today" && <button className="button secondary" onClick={() => setPage("contacts")}>View all contacts <span>↗</span></button>}{view === "contacts" && <button className="button secondary" onClick={() => { void downloadContacts().catch(err => setError(err instanceof Error ? err.message : "Could not export contacts.")); }}>↓ Export CSV</button>}</div></div>
      {error && <div className="alert error" role="alert"><span>!</span><div><strong>Something needs attention</strong><p>{error}</p></div><button onClick={() => { setError(""); void refresh(); }}>Retry</button></div>}
      {notice && <div className="alert success" role="status"><span>✓</span><p>{notice}</p><button onClick={() => setNotice("")} aria-label="Dismiss notification">×</button></div>}
      {loading ? <div className="loading-state"><div className="spinner"/>Loading your workspace…</div> : <>
      {view === "today" && <>
        <section className="hero-card"><div className="hero-copy"><span className="hero-kicker">YOUR DAILY BRIEFING <span className="sparkle">✦</span></span><h2>Make every follow-up<br/><em>feel personal.</em></h2><p>{focusContacts.length ? `You have ${focusContacts.length} ${focusContacts.length === 1 ? "relationship" : "relationships"} ready for attention today. Start with the people who have been waiting longest.` : "You're caught up. Browse your contacts or explore the sample workspace."}</p><button className="button light" onClick={() => document.getElementById("priority-queue")?.scrollIntoView({ behavior: "smooth" })}>Explore today’s queue <span>↘</span></button></div><div className="hero-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="hero-note note-one"><span>✉</span><div><strong>Thoughtful outreach</strong><small>Ready for your review</small></div></div><div className="hero-circle">↗</div><div className="hero-note note-two"><span>✓</span><div><strong>Always in control</strong><small>Approve each message</small></div></div></div></section>
        <OutreachDesk contacts={contacts} reviews={pendingReviews} activities={activities} connections={connections} sent={summary?.sent || 0} simulated={summary?.simulated || 0} mode={mode} busy={busy} onPrepare={generate} onReview={loadReview} onContact={openContact} onNavigate={setPage}/>

      </>}
      {view === "contacts" && <><div className="toolbar"><div className="searchbox"><span>⌕</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search name, company, email, or notes" aria-label="Search contacts"/></div><div className="filter-row">{["All", "Needs attention", "Overdue", "Due Today", "Upcoming"].map(item => <button key={item} onClick={() => setFilter(item)} className={`filter-chip ${filter === item ? "selected" : ""}`}>{item}</button>)}</div></div><div className="content-grid"><section className="contact-list panel"><div className="panel-heading"><h2>Contacts <span>{visible.length}</span></h2><small>Select a person to see the full picture</small></div>{visible.length ? visible.map(contact => <button className={`contact-row ${selected?.id === contact.id ? "selected" : ""}`} key={contact.id} onClick={() => openContact(contact)}><div className="avatar small">{initials(contact.name)}</div><div className="contact-row-main"><strong>{contact.name}</strong><small>{contact.company || getEmail(contact)}</small></div><span className={statusClass(contact.bucket)}>{contact.bucket || "Upcoming"}</span><span className="row-arrow">→</span></button>) : <Empty title="No matching contacts" body="Try another search or filter."/>}</section><section className="detail-panel panel">{selected ? <><div className="detail-top"><div className="avatar large">{initials(selected.name)}</div><div><span className="eyebrow">CONTACT PROFILE</span><h2>{selected.name}</h2><p>{selected.company || "Independent"}</p></div></div><div className="detail-tags"><span className={statusClass(selected.bucket)}>{selected.bucket || "Upcoming"}</span><span className="pill subtle">{selected.status || "Lead"}</span>{selected.replied && <span className="pill green">Replied</span>}</div><div className="detail-actions"><button className="button primary" disabled={busy || selected.replied || selected.do_not_contact} onClick={() => generate(selected)}>Prepare next step ↗</button><button className="button secondary" disabled={busy || selected.replied} onClick={markReplied}>Mark replied</button><button className="button secondary" disabled={busy} onClick={markConverted}>Mark converted</button></div><div className="detail-section"><h3>Relationship details</h3><Info label="Email" value={getEmail(selected)}/><Info label="Interest" value={selected.interest_level || "Not set"}/><Info label="Last interaction" value={niceDate(selected.last_interaction)}/><Info label="Next follow-up" value={niceDate(selected.next_followup)}/><Info label="Source" value={selected.source || "Sample workspace"}/></div><div className="detail-section"><h3>Context the agent can use</h3><p className="context-text">{selected.notes || "No notes yet."}</p>{selected.deal_context && <p className="context-text">{selected.deal_context}</p>}</div>{(selected.recommendations || []).length > 0 && <div className="detail-section"><h3>Latest recommendation</h3><div className="rec-summary"><span className="pill lavender">{actionText(selected.recommendations![selected.recommendations!.length - 1].action)}</span><p>{selected.recommendations![selected.recommendations!.length - 1].reason}</p><button className="text-button" onClick={() => loadReview(selected)}>Open review →</button></div></div>}</> : <div className="detail-empty"><div className="empty-icon">◎</div><h2>Start with a person</h2><p>Select a contact to see their context and plan the next touchpoint.</p></div>}</section></div></>}
      {view === "review" && <><div className="review-banner"><span className="review-banner-icon">✦</span><div><strong>You’re the final decision maker.</strong><p>Read the context, edit the message, and approve the exact version before it can be sent.</p></div><span className="pill lavender">Human approved</span></div>{!recommendation && pendingReviews.length > 0 && <div className="pending-strip panel"><strong>{pendingReviews.length} draft{pendingReviews.length === 1 ? "" : "s"} ready to review</strong>{pendingReviews.map(item => { const contact = contacts.find(c => c.id === item.contact_id); return contact ? <button className="button secondary" key={item.id} onClick={() => loadReview(contact)}>{contact.name} →</button> : null; })}</div>}{recommendation && selected ? <div className="review-layout"><section className="panel review-editor"><div className="panel-heading"><div><span className="eyebrow">RECOMMENDED ACTION</span><h2>{actionText(recommendation.action)}</h2></div><span className="pill lavender">{recommendation.status}</span></div><div className="recipient-line"><span>TO</span><div className="avatar tiny">{initials(selected.name)}</div><strong>{selected.name}</strong><small>&lt;{getEmail(selected)}&gt;</small></div>{recommendation.experiment_id && <div className="experiment-assignment">◇ Experiment variant {recommendation.variant_id} · Test assignment retained for this contact</div>}{recommendation.action === "email" ? <><label className="field-label" htmlFor="subject">SUBJECT</label><input id="subject" className="draft-input" value={subject} onChange={event => setSubject(event.target.value)} disabled={recommendation.status !== "pending" && recommendation.status !== "draft" && recommendation.status !== "proposed"}/><label className="field-label" htmlFor="body">MESSAGE</label><textarea id="body" className="draft-textarea" value={body} onChange={event => setBody(event.target.value)} disabled={recommendation.status !== "pending" && recommendation.status !== "draft" && recommendation.status !== "proposed"}/><div className="generation-note"><strong>{recommendation.generation_source === "model" ? "Model-generated draft" : "Template / rule fallback"}</strong><span>{recommendation.model_id || "Credential-free sample"}</span>{recommendation.generation_error && <p>{recommendation.generation_error}</p>}</div><div className="draft-footer"><span>Version {recommendation.version || recommendation.draft?.version || 1}</span><span>Review every detail before approval</span></div></> : <div className="non-email"><span className="empty-icon">◷</span><h3>{actionText(recommendation.action)}</h3><p>{recommendation.reason}</p></div>}<div className="review-actions">{["pending", "draft", "proposed"].includes(recommendation.status) && <><button className="button secondary" onClick={skip} disabled={busy}>Skip</button>{recommendation.action === "email" && <><button className="button secondary" onClick={saveDraft} disabled={busy || !subject.trim() || !body.trim()}>Save draft</button><button className="button primary" onClick={approve} disabled={busy || !subject.trim() || !body.trim()}>Approve this version ↗</button></>}</>}{recommendation.status === "approved" && recommendation.action === "email" && <button className="button primary" onClick={send} disabled={busy}>{mode === "demo" || selected.source === "demo" ? "Simulate send ↗" : "Send approved email ↗"}</button>}{["simulated", "sent", "skipped"].includes(recommendation.status) && <span className="completed-label">✓ {recommendation.status === "simulated" ? "Simulated send recorded" : recommendation.status === "sent" ? "Sent" : "Skipped"}</span>}</div></section><aside className="review-context"><div className="panel context-panel"><span className="eyebrow">WHY THIS ACTION</span><h3>Agent’s reasoning</h3><p>{recommendation.reason}</p><div className="source-list"><strong>Based on</strong>{(recommendation.sources || []).length ? recommendation.sources.map((source, index) => <div className="source-row" key={index}><span>↳</span>{typeof source === "string" ? source : `${source.field}: ${source.value}`}</div>) : <div className="source-row">Contact details and notes</div>}</div></div><div className="panel context-panel"><span className="eyebrow">CONTACT SNAPSHOT</span><h3>{selected.name}</h3><Info label="Company" value={selected.company || "—"}/><Info label="Status" value={selected.status || "—"}/><Info label="Last interaction" value={niceDate(selected.last_interaction)}/><Info label="Next follow-up" value={niceDate(selected.next_followup)}/><button className="text-button" onClick={() => openContact(selected)}>Open full profile →</button></div></aside></div> : <div className="review-empty panel"><div className="empty-icon">✎</div><h2>Nothing on your desk yet</h2><p>Pick a contact to prepare a recommendation and draft for review.</p><button className="button primary" onClick={() => setPage("today")}>Explore today’s queue ↗</button></div>}</>}
      {view === "activity" && <section className="panel activity-panel"><div className="panel-heading"><h2>Recent activity</h2><small>{activities.length} recorded events</small></div>{activities.length ? activities.map((item, index) => <div className="activity-row" key={item.id || index}><div className="timeline-mark">{item.kind === "send" || item.type === "send" ? "↗" : "•"}</div><div><strong>{(item.kind || item.type || "Activity").replaceAll("_", " ")}</strong><p>{item.detail || "Activity recorded"}</p><small>{niceDate(item.created_at)}</small></div></div>) : <Empty title="Your story starts here" body="Recommendations and decisions will appear as you use the workspace." action="Explore your queue" onClick={() => setPage("today")}/>}</section>}
      {view === "insights" && <><div className="metrics-grid insights-metrics"><Metric label="CONTACTS" value={summary?.total || 0} note="In workspace" icon="◎" tone="blue"/><Metric label="PENDING REVIEWS" value={reviewCount} note="Awaiting your decision" icon="✎" tone="violet"/><Metric label="SENDS RECORDED" value={(summary?.sent || 0) + (summary?.simulated || 0)} note="Includes simulated sends" icon="↗" tone="green"/><Metric label="OVERDUE" value={summary?.overdue || 0} note="Need attention" icon="◷" tone="coral"/></div><div className="panel insight-panel"><span className="eyebrow">OBSERVED ACTIVITY</span><h2>A transparent view of progress.</h2><p>These numbers come from events recorded in this workspace. Sample sends are simulated and do not represent real deliveries or replies.</p><div className="insight-bars">{Object.entries(insights).filter(([, value]) => typeof value === "number").slice(0, 6).map(([key, value]) => <div className="insight-bar" key={key}><span>{key.replaceAll("_", " ")}</span><div><i style={{ width: `${Math.min(100, (value / Math.max(1, ...Object.values(insights).filter(v => typeof v === "number"))) * 100)}%` }}/></div><strong>{value}</strong></div>)}</div></div></>}
      {view === "experiments" && <><div className="review-banner"><span className="review-banner-icon">◇</span><div><strong>Run a fair 50/50 test.</strong><p>Change one message variable, assign contacts consistently, and wait for enough observed sends before drawing a conclusion.</p></div></div><div className="experiment-grid"><section className="panel experiment-form"><div className="panel-heading"><h2>Start a new experiment</h2><span className="pill subtle">ONE VARIABLE</span></div><div className="experiment-fields"><label>Name<input value={testName} onChange={e => setTestName(e.target.value)}/></label><label>Hypothesis<textarea value={testHypothesis} onChange={e => setTestHypothesis(e.target.value)}/></label><label>Variable<select value={testVariable} onChange={e => { setTestVariable(e.target.value); setVariantA(experimentValues[e.target.value][0]); setVariantB(experimentValues[e.target.value][1]); }}><option value="tone">Tone</option><option value="length">Length</option><option value="cta">Call to action</option></select></label><div className="variant-fields"><label>Variant A · 50%<select value={variantA} onChange={e => setVariantA(e.target.value)}>{experimentValues[testVariable].map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Variant B · 50%<select value={variantB} onChange={e => setVariantB(e.target.value)}>{experimentValues[testVariable].map(value => <option key={value} value={value}>{value}</option>)}</select></label></div><div className="experiment-rule">21-day run · minimum 100 sends per variant · 7-day response window. Outcomes are marked manually in this demo.</div><button className="button primary" disabled={busy || experiments.some(item => item.status === "active") || !testName.trim() || !variantA.trim() || !variantB.trim()} onClick={createExperiment}>Start 50/50 test ↗</button>{experiments.some(item => item.status === "active") && <small>Pause the active experiment before starting another.</small>}</div></section><section className="experiment-list"><div className="section-heading"><div><span className="eyebrow">LEARNING LOG</span><h2>Experiments</h2></div></div>{experiments.length ? experiments.map(test => { const result = experimentResults[test.id]; return <article className="panel experiment-card" key={test.id}><div className="experiment-card-head"><div><h3>{test.name}</h3><small>{test.config.variable} · {test.config.start_date} to {test.config.end_date}</small></div><span className={`pill ${test.status === "active" ? "green" : "subtle"}`}>{test.status}</span></div>{test.config.hypothesis && <p className="experiment-hypothesis">{test.config.hypothesis}</p>}<div className="variant-results">{test.config.variants.map(variant => { const stats = result?.variants?.find(item => item.variant_id === variant.id); return <div key={variant.id}><strong>{variant.id}: {variant.value}</strong><small>{variant.weight}% split</small><div className="result-numbers"><span>{stats?.sent || 0} sends</span><span>{stats?.replied || 0} replies</span><span>{stats?.converted || 0} conversions</span></div></div>; })}</div><p className="result-caution">{result?.reason || "Collect the planned sample and wait for the response window before choosing a winner."}</p><button className="button secondary" disabled={busy} onClick={() => setExperimentStatus(test)}>{test.status === "active" ? "Pause test" : "Resume test"}</button></article>; }) : <div className="panel"><Empty title="No experiments yet" body="Start with one clear hypothesis and compare two message versions."/></div>}</section></div></>}
      {view === "connections" && <><ModelSettings /><div className="connection-intro panel"><div className="connection-mark">⌘</div><div><span className="eyebrow">SAFE BY DESIGN</span><h2>Know what’s connected.</h2><p>The sample workspace is ready immediately. Real integrations require their own credentials and setup.</p></div></div><div className="connection-grid">{["hubspot", "gmail"].map(provider => { const connection = connections.find(item => item.provider?.toLowerCase() === provider); return <div className="panel connection-card" key={provider}><div className={`provider-icon ${provider}`}>{<ProviderLogo provider={provider as "hubspot" | "gmail"} />}</div><h3>{provider === "hubspot" ? "HubSpot CRM" : "Gmail"}</h3><p>{provider === "hubspot" ? "Bring contact and deal context into your queue." : "Send approved messages from a connected mailbox."}</p><span className={`pill ${connection?.status === "connected" ? "green" : "subtle"}`}>{connection?.status || "Not connected"}</span>{connection?.last_sync_at && <small>Last sync: {niceDate(connection.last_sync_at)}</small>}{connection?.last_error && <small className="connection-error">{connection.last_error}</small>}{provider === "gmail" && <form onSubmit={async e => { e.preventDefault(); setBusy(true); setError(""); try { await request("/connections/gmail/settings", { method: "PUT", body: JSON.stringify({ sender_email: senderEmail }) }); setNotice("Gmail sender address saved."); } catch (err) { setError(err instanceof Error ? err.message : "Could not save sender address."); } finally { setBusy(false); } }}><label htmlFor="gmail-sender">Sender email</label><input id="gmail-sender" type="email" required value={senderEmail} onChange={e => setSenderEmail(e.target.value)} autoComplete="email"/><button className="button secondary" disabled={busy}>Save sender address</button></form>}<div className="connection-actions">{connection?.status === "connected" ? <><button className="button secondary" disabled={busy} onClick={() => disconnect(provider)}>Disconnect</button>{provider === "hubspot" && <button className="button primary" disabled={busy} onClick={syncHubspot}>Sync contacts ↻</button>}</> : <button className="button secondary" disabled={busy} onClick={() => connect(provider)}>Connect {provider === "hubspot" ? "HubSpot" : "Gmail"} ↗</button>}</div></div>; })}</div>{!usesSupabase && <div className="panel sample-card"><div><span className="eyebrow">EXPLORE FREELY</span><h3>Sample workspace</h3><p>Fictional contacts, real review flow, and simulated delivery. Reset the sample to start a fresh walkthrough.</p></div><button className="button secondary" disabled={busy} onClick={resetDemo}>Reset sample data ↺</button></div>}<div className="panel csv-card"><div><span className="eyebrow">BRING YOUR CONTACTS</span><h3>Import a CSV</h3><p>Preview valid rows and duplicates before adding them to this workspace. The CSV needs name and contact columns.</p></div><div className="csv-controls"><input type="file" accept=".csv,text/csv" aria-label="Choose CSV" onChange={async e => { const file = e.target.files?.[0]; if (file) { setCsvFileName(file.name); setCsvText(await file.text()); setCsvPreview(null); } }}/>{csvFileName && <small>{csvFileName}</small>}<button className="button secondary" disabled={busy || !csvText} onClick={previewCsv}>Preview import</button></div>{csvPreview && <div className="csv-preview"><strong>{csvPreview.count} valid rows · {csvPreview.errors.length} issues</strong>{csvPreview.errors.map((issue, index) => <p key={index}>Line {issue.line}: {issue.reason}</p>)}<button className="button primary" disabled={busy || csvPreview.count === 0} onClick={importCsv}>Import {csvPreview.count} contacts ↗</button></div>}</div></>}
      </>}</div>
    </main>
  </div>;
}

function Metric({ label, value, note, icon, tone }: { label: string; value: number; note: string; icon: string; tone: string }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-label">{label}</div><strong>{value}</strong><small>{note}</small></div>; }
function Info({ label, value }: { label: string; value: string }) { return <div className="info-row"><span>{label}</span><strong>{value}</strong></div>; }
function Empty({ title, body, action, onClick }: { title: string; body: string; action?: string; onClick?: () => void }) { return <div className="empty-state"><div className="empty-icon">✦</div><h3>{title}</h3><p>{body}</p>{action && <button className="button secondary" onClick={onClick}>{action} →</button>}</div>; }
