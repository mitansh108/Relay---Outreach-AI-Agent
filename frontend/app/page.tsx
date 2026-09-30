"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useInView, useMotionValueEvent, useReducedMotion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import ProviderLogo from "@/components/ProviderLogo";

type DemoStep = 0 | 1 | 2 | 3;

const steps = [
  { label: "Connect your sales data.", short: "01 · Connect", description: "Bring contacts, company details, and conversation notes into one workspace. Import a CSV or connect HubSpot so every next step starts with customer context.", detail: "Your customer context becomes the agent’s starting point.", tone: "blue" },
  { label: "Let the agent prepare the next move.", short: "02 · Prepare", description: "The agent checks who needs attention, reads the available context, and recommends an email, a call task, or waiting. Each recommendation comes with a reason you can inspect.", detail: "An action, a draft, and the facts behind them.", tone: "peach" },
  { label: "Keep a human in the loop.", short: "03 · Review", description: "Review the proposed action and message side by side with the source context. Edit the words, approve the exact draft, or skip the outreach. You decide what reaches your customer.", detail: "The workflow pauses until you make the decision.", tone: "lime" },
  { label: "Send. Record. Follow through.", short: "04 · Execute", description: "Send an approved email through a configured Gmail connection and keep the outcome in the contact’s timeline. The sample workspace lets you try the same review flow with simulated sends.", detail: "Every recommendation, approval, and outcome stays on record.", tone: "pink" },
] as const;

function Check() {
  return <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="m4 10 4 4 8-8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return diagonal ? (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M4 16 16 4M7 4h9v9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
  ) : (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M3 10h13m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
  );
}

function DemoScene({ step }: { step: DemoStep }) {
  return (
    <div className="landing-demo-scene" >
      <div className="landing-demo-topline">
        <span className="landing-demo-appmark">relay<span>.</span></span>
        <span className="landing-demo-mode"><i /> Workflow preview</span>
      </div>

      {step === 0 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Sales data</span><strong className="crm-source-label"><ProviderLogo provider="hubspot" compact /> CRM context</strong></div>
        <div className="landing-mini-row selected"><span className="landing-avatar">PS</span><span><strong>Priya Sharma</strong><small>Northstar Labs · HubSpot contact</small></span><em>Overdue</em></div>
        <div className="landing-context-block"><span>CONVERSATION NOTE</span><p>“Asked for a product demo and pricing details.”</p></div>
        <div className="landing-context-grid"><div><span>COMPANY</span><strong>Northstar Labs</strong></div><div><span>INTEREST</span><strong>High</strong></div><div><span>FOLLOW-UP</span><strong>Overdue</strong></div></div>
        <p className="landing-scene-explainer">Contacts, notes, and available CRM context become the input to the agent workflow.</p>
      </div>}

      {step === 1 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Agent recommendation</span><strong>Prepare email</strong></div>
        <div className="landing-context-block"><span>WHY THIS ACTION</span><p>Follow-up is due and the contact has conversation context.</p></div>
        <div className="landing-context-grid"><div><span>SOURCE</span><strong>Contact notes</strong></div><div><span>ELIGIBILITY</span><strong>Checked first</strong></div><div><span>NEXT STEP</span><strong>Human review</strong></div></div>
        <p className="landing-scene-explainer">The agent can also recommend a call task, waiting, or no action. Every choice includes a reason.</p>
      </div>}

      {step === 2 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Draft for review</span><strong>Nothing sent yet</strong></div>
        <div className="landing-email-preview"><div><span>TO</span> priya.sharma@example.com</div><div><span>SUBJECT</span> Demo and pricing details</div><p>Hi Priya,<br /><br />You asked for a product demo and pricing details. Would a short walkthrough this week be helpful? I can bring the options that fit your team.<br /><br />Best,</p></div>
        <div className="landing-approval-note"><span className="landing-check"><Check /></span> You can edit or skip this draft. A real send requires your approval.</div>
      </div>}

      {step === 3 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Activity record</span><strong>Sample mode</strong></div>
        <div className="landing-timeline"><div><i /><span><strong>Recommendation prepared</strong><small>Context and reason saved</small></span></div><div><i /><span><strong>Draft reviewed</strong><small>Exact message approved by a person</small></span></div><div><i /><span><strong>Simulated send recorded</strong><small>No real email was delivered</small></span></div></div>
        <p className="landing-scene-explainer">Every decision stays visible in the contact’s timeline.</p>
      </div>}
    </div>
  );
}

function StackNavigation() {
  const [active, setActive] = useState(0);
  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, "change", () => {
    const threshold = Math.max(180, window.innerHeight * 0.35);
    let current = 0;
    steps.forEach((_, index) => {
      const card = document.getElementById(`walkthrough-${index}`);
      if (card && card.getBoundingClientRect().top <= threshold) current = index;
    });
    setActive(current);
  });
  return <nav className="landing-stack-navigation" aria-label="Walkthrough steps"><div>{steps.map((item, index) => <a key={item.label} href={`#walkthrough-${index}`} aria-label={`Step ${index + 1}: ${item.label}`} aria-current={active === index ? "step" : undefined} onClick={() => setActive(index)}><span /></a>)}</div></nav>;
}

function WalkthroughCard({ index }: { index: DemoStep }) {
  const ref = useRef<HTMLElement>(null);
  const reducedMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 100px", "end 100px"] });
  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.94]);
  const filter = useTransform(scrollYProgress, [0, 1], ["brightness(1)", "brightness(0.88)"]);
  const item = steps[index];

  return <motion.article
    ref={ref}
    id={`walkthrough-${index}`}
    className={`landing-stack-card ${item.tone}`}
    aria-labelledby={`walkthrough-title-${index}`}
    style={{ top: `calc(var(--walkthrough-heading-height, 180px) + ${16 + index * 16}px)`, zIndex: index + 1, scale: reducedMotion || index === 3 ? 1 : scale, filter: reducedMotion || index === 3 ? "none" : filter }}
  >
    <div className="landing-stack-copy">
      <div className="landing-stack-intro"><span className="landing-stack-step">{item.short}</span><h3 id={`walkthrough-title-${index}`}>{item.label}<span>{["Context in, guesswork out.", "A reason behind every action.", "Your judgment, at every send.", "A workflow you can trace."][index]}</span></h3><p>{item.description}</p></div>
      <div className="landing-stack-footer"><p>{item.detail}</p>{index < 3 ? <a className="landing-button" href={`#walkthrough-${index + 1}`}>Next: {steps[index + 1].label.toLowerCase()} <Arrow /></a> : <Link className="landing-button" href="/workspace">Try the sample workspace <Arrow /></Link>}</div>
    </div>
    <div className="landing-stack-visual"><DemoScene step={index} /></div>
  </motion.article>;
}

function Walkthrough() {
  const sectionRef = useRef<HTMLElement>(null);
  const headingRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const heading = headingRef.current;
    const section = sectionRef.current;
    if (!heading || !section) return;
    const measure = () => section.style.setProperty("--walkthrough-heading-height", `${heading.getBoundingClientRect().height}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(heading);
    return () => observer.disconnect();
  }, []);
  return <section ref={sectionRef} id="how-it-works" className="landing-walkthrough"><div ref={headingRef} className="landing-section-heading"><h2>From customer data<br />to approved outreach.</h2><p>One agent workflow. Four clear steps. Follow an illustrative contact journey, then try the review process yourself in the sample workspace.</p></div><div className="landing-card-stack"><StackNavigation />{steps.map((item, index) => <WalkthroughCard key={item.label} index={index as DemoStep} />)}</div></section>;
}

type PreviewStage = "context" | "draft" | "review" | "record";
const previewTabs = ["context", "draft", "review", "record"] as const;
const initialPreviewBody = "Hi Priya,\n\nYou asked for a product demo and pricing details. Would a short walkthrough this week be helpful? I can bring the options that fit your team.\n\nBest,";

function AgentPreview() {
  const [view, setView] = useState<PreviewStage>("context");
  const [visible, setVisible] = useState(true);
  const [showApproval, setShowApproval] = useState(false);
  const [approved, setApproved] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.3 });
  const reducedMotion = useReducedMotion();
  const animate = inView && visible && !reducedMotion;
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  useEffect(() => {
    if (reducedMotion) {
      if (view === "context" || view === "draft") { setView("review"); setShowApproval(true); }
      return;
    }
    if (!inView || !visible || view === "review" || view === "record") return;
    const timer = setTimeout(() => {
      if (view === "context") setView("draft");
      else { setView("review"); setShowApproval(true); }
    }, view === "context" ? 900 : 1100);
    return () => clearTimeout(timer);
  }, [view, inView, visible, reducedMotion]);
  const decidePreview = (approve: boolean) => { setApproved(approve); setShowApproval(false); setView("record"); };
  const status = view === "context" ? "Reading context" : view === "draft" ? "Draft prepared" : view === "review" ? "Awaiting approval" : approved ? "Simulated send" : "Skipped";
  return <div ref={ref} className="agent-preview" data-stage={view}>
    <div className="agent-preview-top"><span className="agent-preview-brand">relay<span>.</span></span><span className="sample-label">Illustrative workflow · no real send</span></div>
    <div className="agent-preview-body">
      <div className="agent-flow">
        <div className={`agent-data ${view === "context" ? "flow-active" : ""}`}><ProviderLogo provider="hubspot" compact /><div><strong>+ CSV</strong><small>Contacts, companies, notes</small></div></div>
        <div className={`agent-node ${view === "draft" ? "flow-active" : ""}`}><span className="agent-node-icon"><Arrow diagonal /></span><div><strong>Sales follow-up agent</strong><small>Check eligibility → recommend → draft</small></div></div>
        <div className={`agent-human ${view === "review" ? "flow-active" : ""}`}><span className="landing-avatar">YOU</span><div><strong>Human review</strong><small>Review before sending</small></div><Check /></div>
        <div className="hero-handoff" aria-hidden="true"><span className="hero-handoff-line" /><AnimatePresence mode="wait">{animate && (view === "context" || view === "draft") ? <motion.div key={view} className="hero-handoff-packet" initial={{ x: view === "context" ? "-40%" : "0%", opacity: 0 }} animate={{ x: view === "context" ? "0%" : "40%", opacity: [0, 1, 1, 0] }} exit={{ opacity: 0 }} transition={{ duration: view === "context" ? 0.8 : 1, times: [0, 0.12, 0.88, 1], ease: "easeInOut" }}><span>{view === "context" ? "CRM notes" : "Prepared draft"}<Arrow /></span></motion.div> : <div className="hero-handoff-label">{view === "review" ? "The workflow pauses for a person" : view === "record" ? "Human-approved → simulated delivery" : "Context → draft → human review"}</div>}</AnimatePresence></div>
        <div className="workflow-progress" aria-hidden="true"><motion.span initial={false} animate={{ scaleX: view === "context" ? 0.12 : view === "draft" ? 0.5 : view === "review" ? 0.82 : 1 }} transition={{ duration: reducedMotion ? 0 : 0.8, ease: [0.16, 1, 0.3, 1] }} /></div>
      </div>
      <div className="agent-review">
        <div className="agent-review-contact"><span className="landing-avatar">PS</span><div><strong>Priya Sharma</strong><small>Northstar Labs · Demo requested</small></div><span className={`review-status ${view === "record" ? "complete" : ""}`}>{status}</span></div>
        <div className="agent-tabs agent-stage-labels" aria-label="Illustrative workflow stages">{previewTabs.map(tab => <span key={tab} aria-current={view === tab ? "step" : undefined}>{tab === "context" ? "Context" : tab === "draft" ? "Draft" : tab === "review" ? "Human review" : "Record"}</span>)}</div>
        <AnimatePresence mode="wait" initial={false}><motion.div key={view} initial={reducedMotion ? { opacity: 0.8 } : { opacity: 0, x: 14, filter: "blur(2px)" }} animate={{ opacity: 1, x: 0, filter: "blur(0px)" }} exit={reducedMotion ? { opacity: 0.8 } : { opacity: 0, x: -8 }} transition={{ duration: reducedMotion ? 0.1 : 0.3, ease: [0.16, 1, 0.3, 1] }} className="agent-preview-panel">
          {view === "context" && <><div className="preview-field"><span>CRM note</span><p>“Asked for a product demo and pricing details.”</p></div><div className="preview-context-facts">{["Northstar Labs", "High interest", "Follow-up due"].map((fact, index) => <motion.span key={fact} initial={false} animate={animate ? { opacity: [0.3, 1], y: [8, 0] } : { opacity: 1, y: 0 }} transition={{ delay: index * 0.16, duration: 0.4 }}>{fact}</motion.span>)}</div><div className="preview-field"><span>Agent’s recommendation</span><p>Prepare an email. Follow-up is due and the contact has conversation context.</p></div><div className="preview-source"><Check /> Source facts carried into the draft</div></>}
          {view === "draft" && <><div className="preview-field"><span>Subject</span><strong>Demo and pricing details</strong></div><div className="preview-email">{initialPreviewBody.split("\n\n").map((paragraph, index) => <motion.p key={index} initial={false} animate={animate ? { opacity: [0, 1], y: [12, 0], clipPath: ["inset(0 0 100% 0)", "inset(0 0 0% 0)"] } : { opacity: 1, y: 0, clipPath: "inset(0 0 0% 0)" }} transition={{ delay: index * 0.3, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}>{paragraph}</motion.p>)}</div><div className="preview-source"><Check /> Prepared for review. Nothing sent.</div></>}
          {view === "review" && <><div className="preview-review-heading"><h3>A person makes the call.</h3><span className="approval-pause">Human checkpoint</span></div><p className="preview-review-note">The agent prepares. You review the recipient and exact draft.</p><p className="preview-review-message">{initialPreviewBody}</p><div className="preview-source"><span className="approval-wait-dot" /> Waiting for you. The agent cannot continue.</div><p className="preview-sample-note">This is an animation. Real sends require your decision in the workspace.</p></>}
          {view === "record" && <><div className="preview-record-heading"><span className="preview-record-icon"><Check /></span><div><h3>{approved ? "Approved. Recorded." : "Skipped. Recorded."}</h3><p>{approved ? "An illustrative send, with a visible trail." : "Your decision stopped the outreach."}</p></div></div>{approved && <div className="preview-delivery" aria-hidden="true"><span>Approved draft</span><motion.svg viewBox="0 0 24 24" fill="none" initial={false} animate={animate ? { x: [0, 90, 0], opacity: [1, 0, 1] } : { x: 0, opacity: 1 }} transition={{ duration: 0.9, times: [0, 0.7, 1] }}><path d="m3 11 18-8-8 18-2-8-8-2Zm8 2 10-10" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" /></motion.svg><strong className="gmail-delivery-label"><ProviderLogo provider="gmail" compact /> Gmail simulation</strong></div>}<div className="preview-record-timeline">{["Recommendation prepared", approved ? "Draft approved by a person" : "Draft reviewed by a person", approved ? "Simulated send recorded" : "Outreach skipped — nothing sent"].map((event, index) => <motion.div key={event} initial={false} animate={animate ? { opacity: [0, 1], y: [8, 0] } : { opacity: 1, y: 0 }} transition={{ delay: 0.4 + index * 0.2, duration: 0.35 }}><Check /><span>{event}</span></motion.div>)}</div><p className="preview-sample-note">Fictional contact. No email delivered.</p></>}
        </motion.div></AnimatePresence>
      </div>
    </div>
    <AnimatePresence>{showApproval && view === "review" && <motion.div className="hero-approval-layer" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.22 }}>
      <motion.div className="hero-approval-dialog" role="region" aria-labelledby="approval-dialog-title" initial={reducedMotion ? { opacity: 0 } : { opacity: 0, y: 38, scale: 0.88, rotate: -3 }} animate={{ opacity: 1, y: 0, scale: 1, rotate: 0 }} exit={{ opacity: 0, y: reducedMotion ? 0 : -12, scale: reducedMotion ? 1 : 0.96 }} transition={{ duration: reducedMotion ? 0.1 : 0.55, ease: [0.16, 1, 0.3, 1] }}>
        <div className="approval-dialog-person"><span><svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.7" /><path d="M5 21v-3a7 7 0 0 1 14 0v3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg></span><div><strong>Human in the loop</strong><small><i /> Agent paused</small></div></div>
        <h3 id="approval-dialog-title">Your agent is waiting.<br /><span>You make the call.</span></h3>
        <p className="approval-dialog-copy">The draft is ready. It only moves forward with your approval.</p>
        <div className="approval-dialog-email"><div><span>To</span><strong>Priya Sharma <small>· Northstar Labs</small></strong></div><div><span>Subject</span><strong>Demo and pricing details</strong></div></div>
        <motion.button type="button" className="hero-approve-button" onClick={() => decidePreview(true)} initial={false} animate={reducedMotion ? { scale: 1 } : { scale: [0.96, 1.03, 1] }} transition={{ duration: 0.5, delay: reducedMotion ? 0 : 0.3 }}>Approve this email <Check /></motion.button>
        <button type="button" className="approval-dialog-skip" onClick={() => decidePreview(false)}>Skip this email</button>
        <p className="approval-dialog-footnote">Try the checkpoint. No real email will be sent.</p>
      </motion.div>
    </motion.div>}</AnimatePresence>
  </div>;
}

function AgentConfiguration() {
  const [tone, setTone] = useState("Friendly");
  const [goal, setGoal] = useState("Book a product demo");
  const reducedMotion = useReducedMotion();
  const example = tone === "Professional" ? "Hello Priya, following your request for a demo and pricing details, would you be available for a brief product walkthrough this week?" : tone === "Concise" ? "Hi Priya, still interested in a demo? Happy to walk through pricing this week." : "Hi Priya, thanks for your interest! Would a quick walkthrough this week help you explore the product and pricing?";
  return <section className="landing-config" id="agent-config">
    <div className="config-copy"><h2>Your sales process.<br /><span>Your agent’s playbook.</span></h2><p>The next step for Relay: configure an agent around your team’s outreach goals, preferred tone, and connected customer data. Keep human approval built into the workflow.</p><p className="feature-status">Agent configuration · Planned</p><p className="config-note">Explore the setup concept here. These settings preview the planned experience and do not configure the live workspace.</p></div>
    <div className="config-editor"><div className="config-editor-head"><strong>Sales follow-up agent</strong><span>Setup preview</span></div><label htmlFor="agent-goal">Outreach goal<input id="agent-goal" maxLength={100} value={goal} onChange={event => setGoal(event.target.value)} /></label><fieldset><legend>Writing tone</legend><div className="tone-options">{["Friendly", "Professional", "Concise"].map(option => <button type="button" key={option} aria-pressed={tone === option} onClick={() => setTone(option)}>{option}</button>)}</div></fieldset><div className="config-data"><span>Data sources</span><strong className="config-source-logos"><ProviderLogo provider="hubspot" compact /> contacts <span>+</span> CSV imports</strong></div><div className="config-approval"><Check /><div><strong>Human approval required</strong><p>Review every message before it is sent.</p></div></div><div className="config-summary" aria-live="polite"><span>Your playbook</span><p>Prepare <strong>{tone.toLowerCase()}</strong> outreach to <strong>{goal.trim() ? goal.trim().toLowerCase() : "your selected goal"}</strong>, using customer context. Pause for human review before sending.</p></div><div className="config-message-preview"><span>Example message · {tone} tone</span><AnimatePresence mode="wait" initial={false}><motion.p key={tone} initial={{ opacity: 0.7, y: reducedMotion ? 0 : 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>{example}</motion.p></AnimatePresence></div></div>
  </section>;
}

export default function LandingPage() {
  return <div className="landing">
    <header className="landing-nav">
      <Link className="landing-brand" href="/" aria-label="Relay home"><span className="landing-brand-symbol"><Arrow diagonal /></span><span>relay<span className="landing-brand-dot">.</span></span></Link>
      <nav aria-label="Main navigation"><a href="#how-it-works">How agents work</a><a href="#agent-config">Your playbook</a><a href="#connections">Connections</a></nav>
      <Link className="landing-nav-cta" href="/workspace">Explore the demo <Arrow diagonal /></Link>
    </header>
    <main>
      <section className="landing-hero">
        <div className="landing-hero-copy"><h1>AI agents for sales outreach.<br /><span>A human at the helm.</span></h1><p>Turn customer context into your next sales conversation. Relay’s agent workflow prepares the next action and outreach draft, then pauses for you to review, edit, and approve.</p><div className="landing-hero-actions"><Link className="landing-button solid" href="/workspace">Try the agent workflow <Arrow /></Link><a className="landing-button quiet" href="#how-it-works">See how it works <Arrow /></a></div><div className="landing-trust-line"><Check /> Sample data included <span>·</span> No credentials needed <span>·</span> Simulated sends</div></div>
        <AgentPreview />
      </section>
      <section className="landing-mechanism"><p>Your data gives it context.<br /><strong>Your judgment gives it direction.</strong></p><div><span>Connect</span><Arrow /><span>Prepare</span><Arrow /><span>Human review</span><Arrow /><span>Execute</span></div></section>
      <Walkthrough />
      <AgentConfiguration />
      <section className="landing-connections" id="connections"><div className="landing-section-heading"><h2>Give your agent<br />the right context.</h2><p>Start with your contact data. Add the connections that bring your sales workflow together.</p></div><div className="connection-table"><div><ProviderLogo provider="hubspot" /><h3>HubSpot</h3><p>Import contacts and available company, deal, and note context. CRM sync is read-only.</p><span className="connection-feature">OAuth setup required</span></div><div><ProviderLogo provider="gmail" /><h3>Gmail</h3><p>Send the exact email you approved. Keep the send outcome attached to the contact.</p><span className="connection-feature">OAuth setup required</span></div><div><span className="source-mark csv">CSV</span><h3>Your contact list</h3><p>Preview and validate a CSV before importing. Export your contacts when you need them.</p><span className="connection-feature">Available in the workspace</span></div></div><Link className="text-link" href="/connections">Explore data connections <Arrow diagonal /></Link></section>
      <section className="landing-learning"><div><h2>Keep the work visible.<br /><span>Learn from what happens.</span></h2><p>Agent work belongs in a record you can inspect. Review activity, track observed outcomes, and compare outreach variants without losing the human approval step.</p><Link className="text-link" href="/workspace">Explore the sample workspace <Arrow /></Link></div><dl><div><dt>Activity & decisions</dt><dd>Recommendations, draft edits, approvals, and send outcomes stay in the contact’s timeline.</dd></div><div><dt>Outreach experiments</dt><dd>Test one message element with two variants. Each contact keeps its assignment and each email still needs review.</dd></div><div><dt>Reply tracking & insights</dt><dd>Mark replies manually. See counts from recorded activity; experiment results stay inconclusive until there is enough evidence.</dd></div></dl></section>
      <section className="landing-faq" id="questions"><div><h2>Before you put<br />an agent to work.</h2></div><div><details><summary>What can I try today?</summary><p>The sample workspace lets you inspect contacts, request a recommendation, edit and approve a draft, simulate a send, and view the activity record. Without a configured model it uses rules and templates. Connect Groq in Connections to generate model-backed drafts; sample sends remain simulated.</p></details><details><summary>Can I configure my own agents?</summary><p>Agent playbook configuration is planned. Groq model settings are available in the workspace’s Connections screen. The setup preview on this page does not save an agent playbook.</p></details><details><summary>Can I connect my own data and email?</summary><p>The workspace includes CSV import and export, plus HubSpot and Gmail connection flows. Live OAuth connections require deployment configuration and your own accounts.</p></details><details><summary>Does an agent send without my approval?</summary><p>No. Each real email requires approval of the exact recipient and draft version. Sample mode simulates sending. Relay does not run unattended email sequences.</p></details></div></section>
      <section className="landing-close"><h2>Meet your next<br /><span>sales workflow.</span></h2><div><p>See an agent prepare the work.<br />Be the human who makes the call.</p><Link className="landing-button solid" href="/workspace">Explore the sample workspace <Arrow /></Link><small>Fictional contacts. Real review flow. Simulated sends.</small></div></section>
    </main>
    <footer className="landing-footer"><span className="landing-footer-logo">relay<span>.</span></span><span>Sales outreach, with a human in the loop.</span><a href="#questions">Questions <Arrow diagonal /></a></footer>
  </div>;
}
