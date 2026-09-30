import { useRef, useState } from "react";
import ProviderLogo from "@/components/ProviderLogo";
import { Activity, Contact, Recommendation, initials, niceDate } from "@/lib/api";

type Props = {
  contacts: Contact[];
  reviews: Recommendation[];
  activities: Activity[];
  connections: { provider: string; status: string }[];
  sent: number;
  simulated: number;
  mode: string;
  busy: boolean;
  onPrepare: (contact: Contact) => void;
  onReview: (contact: Contact, recommendation: Recommendation) => void;
  onContact: (contact: Contact) => void;
  onNavigate: (view: "contacts" | "review" | "activity" | "connections") => void;
};

function Arrow() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>;
}

const eventLabels: Record<string, string> = {
  recommendation: "Agent prepared a recommendation",
  approved: "You approved a message",
  draft_edited: "You edited a draft",
  simulated_send: "A sample send was recorded",
  sent: "An approved message was sent",
  send: "An approved message was sent",
  skipped: "You skipped a recommendation",
  replied: "A reply was marked",
  converted: "You marked a contact as converted",
  contact_updated: "Contact details were updated",
};

const proposedActions: Record<string, string> = {
  email: "Draft email",
  call_task: "Plan a call",
  wait: "Wait before following up",
  no_action: "No outreach recommended",
};

export default function OutreachDesk(props: Props) {
  const { contacts, reviews, busy } = props;
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const decisionRef = useRef<HTMLElement>(null);
  const eligible = contacts.filter(contact => !contact.replied && !contact.do_not_contact && !["closed", "lost", "converted"].includes(contact.status?.toLowerCase()));
  const pendingByContact = new Map<string, Recommendation>();
  for (const review of reviews) if (!pendingByContact.has(review.contact_id)) pendingByContact.set(review.contact_id, review);
  const queue = eligible.filter(contact => pendingByContact.has(contact.id) || ["overdue", "due today"].includes(contact.bucket?.toLowerCase()))
    .sort((a, b) => Number(pendingByContact.has(b.id)) - Number(pendingByContact.has(a.id)) || b.priority_score - a.priority_score);
  const ready = queue.filter(contact => pendingByContact.has(contact.id));
  const toPrepare = queue.filter(contact => !pendingByContact.has(contact.id));
  const visible = filter === "review" ? ready : filter === "prepare" ? toPrepare : queue;
  const selected = visible.find(contact => contact.id === selectedId) || visible[0];
  const draft = selected ? pendingByContact.get(selected.id) : undefined;
  const upcoming = eligible.filter(contact => !queue.some(item => item.id === contact.id) && contact.next_followup)
    .sort((a, b) => (a.next_followup || "").localeCompare(b.next_followup || "")).slice(0, 3);

  return <div className="outreach-desk" id="priority-queue">
    <div className="desk-heading">
      <div><h2>Your outreach desk</h2><p>Agents prepare the next move. You decide what goes out.</p></div>
      <span className="desk-policy"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/></svg>Approval required for every send</span>
    </div>

    <div className="desk-workflow" aria-label="Outreach workflow">
      <button onClick={() => setFilter("prepare")} className={filter === "prepare" ? "active" : ""}><span className="workflow-number">{toPrepare.length}</span><span><strong>To prepare</strong><small>Follow-ups needing an agent recommendation</small></span><Arrow/></button>
      <button onClick={() => setFilter("review")} className={filter === "review" ? "active" : ""}><span className="workflow-number">{ready.length}</span><span><strong>Awaiting your review</strong><small>Proposed actions waiting for your decision</small></span><Arrow/></button>
      <button onClick={() => props.onNavigate("activity")}><span className="workflow-number">{props.sent + props.simulated}</span><span><strong>Sends recorded</strong><small>{props.simulated ? `${props.sent} delivered · ${props.simulated} simulated` : "Approved messages delivered"}</small></span><Arrow/></button>
    </div>

    <div className="desk-layout">
      <section className="desk-queue" aria-labelledby="desk-queue-title">
        <div className="desk-section-heading"><h3 id="desk-queue-title">Next actions <span>{queue.length}</span></h3><span className="desk-sort">Review first, then priority</span></div>
        <div className="desk-filters" aria-label="Filter next actions">
          {[{ id: "all", label: "All actions", count: queue.length }, { id: "review", label: "Ready for review", count: ready.length }, { id: "prepare", label: "To prepare", count: toPrepare.length }].map(item => <button key={item.id} aria-pressed={filter === item.id} className={filter === item.id ? "selected" : ""} onClick={() => setFilter(item.id)}>{item.label}<span>{item.count}</span></button>)}
        </div>
        <div className="desk-rows">
          {visible.map(contact => {
            const rec = pendingByContact.get(contact.id);
            return <button className={`desk-contact ${selected?.id === contact.id ? "selected" : ""}`} key={contact.id} aria-pressed={selected?.id === contact.id} onClick={() => {
              setSelectedId(contact.id);
              if (window.matchMedia("(max-width: 960px)").matches) decisionRef.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
            }}>
              <span className="desk-avatar">{initials(contact.name)}</span>
              <span className="desk-contact-info"><strong>{contact.name}<span className={`desk-status ${rec ? "review" : contact.bucket?.toLowerCase() === "overdue" ? "overdue" : ""}`}>{rec ? "Review needed" : contact.bucket}</span></strong><span className="desk-company">{contact.company || contact.contact || contact.email}</span><span className="desk-contact-context">{rec?.reason || contact.notes || "Add conversation context before preparing outreach."}</span><span className="desk-contact-foot">{rec ? (rec.action === "email" ? "Email draft prepared" : "Suggested action prepared") : `Follow-up ${niceDate(contact.next_followup)}`}</span></span>
              <Arrow/>
            </button>;
          })}
          {!visible.length && <div className="desk-empty"><h4>{filter === "review" ? "No decisions waiting on you" : "You're caught up here"}</h4><p>{filter === "review" ? "Choose a follow-up in To prepare. The agent will suggest an action and bring it back for your review." : "There are no follow-ups to prepare in this queue. Check upcoming contacts or browse your workspace."}</p><button className="button secondary" onClick={() => filter === "review" && toPrepare.length ? setFilter("prepare") : props.onNavigate("contacts")}>{filter === "review" && toPrepare.length ? "See follow-ups to prepare" : "Browse contacts"}<Arrow/></button></div>}
        </div>
        {!!upcoming.length && <div className="desk-upcoming"><div className="desk-section-heading"><h3>Coming up next</h3><button className="desk-link" onClick={() => props.onNavigate("contacts")}>All contacts <Arrow/></button></div>{upcoming.map(contact => <button key={contact.id} onClick={() => props.onContact(contact)} disabled={busy}><span><strong>{contact.name}</strong><small>{contact.company}</small></span><span>{niceDate(contact.next_followup)}</span><Arrow/></button>)}</div>}
      </section>

      <aside className="desk-decision" aria-label="Selected next action" ref={decisionRef}>
        {selected ? <>
          <div className="decision-heading"><span className="decision-state">{draft ? "Waiting for your decision" : "Ready for agent preparation"}</span><h3>{selected.name}</h3><p>{selected.company || "Contact"}</p></div>
          <div className="decision-context"><h4>Conversation context</h4><p>{selected.notes || "No notes available. Add context before drafting a personal message."}</p>{selected.deal_context && <p>{selected.deal_context}</p>}<dl><div><dt>Last interaction</dt><dd>{niceDate(selected.last_interaction)}</dd></div><div><dt>Follow-up due</dt><dd>{niceDate(selected.next_followup)}</dd></div></dl></div>
          {draft ? <div className="decision-proposal"><h4>Agent’s proposed action: {proposedActions[draft.action] || "Review contact"}</h4><p>{draft.reason}</p>{draft.action === "email" && <><div className="decision-subject">{draft.subject || draft.draft?.subject}</div><p className="decision-message">{draft.body || draft.draft?.body}</p><span className="decision-source">{draft.generation_source === "model" ? "Model-generated draft" : "Template / rule fallback"} · Version {draft.version || draft.draft?.version || 1}</span></>}</div> : <div className="decision-proposal"><h4>What happens next</h4><p>The agent checks this contact’s eligibility and context, then proposes an email, a call, or a reason to wait.</p><span className="decision-source">No recommendation prepared yet</span></div>}
          <div className="decision-actions"><button className="button primary" disabled={busy} onClick={() => draft ? props.onReview(selected, draft) : props.onPrepare(selected)}>{busy ? "Opening next step…" : draft ? "Review proposed action" : "Prepare with agent"}<Arrow/></button><button className="desk-link" disabled={busy} onClick={() => props.onContact(selected)}>Open contact history <Arrow/></button><small>{draft ? "Edit, approve, or skip in the review inbox." : "Preparation creates a recommendation for review."} Nothing sends here.</small></div>
        </> : <div className="desk-empty"><h3>A clear place to make the call</h3><p>Select an action to inspect the contact context and the agent’s recommendation.</p></div>}
      </aside>
    </div>

    <div className="desk-bottom">
      <section className="desk-history"><div className="desk-section-heading"><h3>Recent work</h3><button className="desk-link" onClick={() => props.onNavigate("activity")}>Full activity <Arrow/></button></div>{props.activities.length ? props.activities.slice(0, 3).map(item => <div className="desk-event" key={item.id}><span className="event-dot"/><div><strong>{eventLabels[item.kind || item.type] || (item.kind || item.type || "Activity").replaceAll("_", " ")}</strong><p>{contacts.find(contact => contact.id === item.contact_id)?.name || item.contact_name || "Workspace"} · {item.detail || "Activity recorded"}</p></div><time>{niceDate(item.created_at)}</time></div>) : <p className="desk-quiet">Your agent recommendations, edits, and approval decisions will appear here as you work.</p>}</section>
      <section className="desk-setup"><div className="desk-section-heading"><h3>Workspace connections</h3><button className="desk-link" onClick={() => props.onNavigate("connections")}>Manage <Arrow/></button></div><div className="desk-connection"><span>Contact data</span><strong>{props.mode === "demo" ? "Sample workspace" : `${contacts.length} contacts`}</strong></div>{["hubspot", "gmail"].map(provider => { const connection = props.connections.find(item => item.provider.toLowerCase() === provider); return <div className="desk-connection" key={provider}><span className="desk-provider-label"><ProviderLogo provider={provider as "hubspot" | "gmail"} compact />{provider === "hubspot" ? "CRM" : "Gmail delivery"}</span><strong>{connection?.status?.replaceAll("_", " ") || "Not connected"}</strong></div>; })}<p className="desk-quiet">{props.mode === "demo" ? "Sample sends are simulated. Connect your CRM and email to use Relay with your own contacts." : "Every outbound message requires your approval."}</p></section>
    </div>
  </div>;
}
