"use client";

import { useState } from "react";
import Link from "next/link";

type DemoStep = 0 | 1 | 2 | 3;

const steps = [
  { label: "Find the moment", short: "01 · Prioritize" },
  { label: "See the context", short: "02 · Understand" },
  { label: "Review the words", short: "03 · Approve" },
  { label: "Keep the record", short: "04 · Track" },
] as const;

function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return diagonal ? (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M4 16 16 4M7 4h9v9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
  ) : (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M3 10h13m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
  );
}

function DemoScene({ step }: { step: DemoStep }) {
  return (
    <div className="landing-demo-scene" aria-live="polite">
      <div className="landing-demo-topline">
        <span className="landing-demo-appmark">relay<span>.</span></span>
        <span className="landing-demo-mode"><i /> Sample workspace</span>
      </div>

      {step === 0 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Today’s queue</span><strong>4 need attention</strong></div>
        <div className="landing-mini-row selected"><span className="landing-avatar">PS</span><span><strong>Priya Sharma</strong><small>Northstar Labs · Product demo and pricing</small></span><em>Overdue</em></div>
        <div className="landing-mini-row"><span className="landing-avatar lavender">ML</span><span><strong>Marcus Lee</strong><small>Bluebird Studio · Proposal requested</small></span><em>Overdue</em></div>
        <div className="landing-mini-row muted"><span className="landing-avatar blue">AK</span><span><strong>Aisha Khan</strong><small>Cedar Health · Follow-up tomorrow</small></span><em>Upcoming</em></div>
        <p className="landing-scene-explainer">Relay puts due contacts first and keeps the reason beside each name.</p>
      </div>}

      {step === 1 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Contact context</span><strong>Priya Sharma</strong></div>
        <div className="landing-context-block"><span>LAST CONVERSATION</span><p>“Asked for a product demo and pricing details.”</p></div>
        <div className="landing-context-grid"><div><span>STATUS</span><strong>Follow-up needed</strong></div><div><span>INTEREST</span><strong>High</strong></div><div><span>NEXT FOLLOW-UP</span><strong>Overdue</strong></div></div>
        <p className="landing-scene-explainer">See what was actually recorded before deciding what to say.</p>
      </div>}

      {step === 2 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Draft for review</span><strong>Nothing sent yet</strong></div>
        <div className="landing-email-preview"><div><span>TO</span> priya.sharma@example.com</div><div><span>SUBJECT</span> Demo and pricing details</div><p>Hi Priya,<br /><br />You asked for a product demo and pricing details. Would a short walkthrough this week be helpful? I can bring the options that fit your team.<br /><br />Best,</p></div>
        <div className="landing-approval-note"><span className="landing-check">✓</span> You can edit or skip this draft. A real send requires your approval.</div>
      </div>}

      {step === 3 && <div className="landing-scene-content">
        <div className="landing-scene-header"><span>Activity record</span><strong>Sample mode</strong></div>
        <div className="landing-timeline"><div><i /><span><strong>Recommendation prepared</strong><small>Context and reason saved</small></span></div><div><i /><span><strong>Draft reviewed</strong><small>Exact message approved by a person</small></span></div><div><i /><span><strong>Simulated send recorded</strong><small>No real email was delivered</small></span></div></div>
        <p className="landing-scene-explainer">Every decision stays visible in the contact’s timeline.</p>
      </div>}
    </div>
  );
}

export default function LandingPage() {
  const [step, setStep] = useState<DemoStep>(0);
  const next = () => setStep(((step + 1) % 4) as DemoStep);

  return <div className="landing">
    <header className="landing-nav">
      <Link className="landing-brand" href="/" aria-label="Relay home"><span className="landing-brand-symbol"><Arrow diagonal /></span><span>relay<span className="landing-brand-dot">.</span></span></Link>
      <nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#what-it-does">What it does</a><a href="#questions">Questions</a></nav>
      <Link className="landing-nav-cta" href="/workspace">Try the demo <Arrow diagonal /></Link>
    </header>

    <main>
      <section className="landing-hero">
        <div className="landing-hero-copy">
          <h1>Follow up with the right person. <span>Know exactly why.</span></h1>
          <p>Relay turns a scattered lead list into a clear daily queue. See the context, review the message, and keep every decision on the record.</p>
          <div className="landing-hero-actions"><Link className="landing-button solid" href="/workspace">Open the sample workspace <Arrow /></Link><a className="landing-button quiet" href="#how-it-works">See how it works <span>↓</span></a></div>
          <div className="landing-trust-line"><span className="landing-trust-dot" /> No account needed for the sample demo <span className="landing-trust-separator">·</span> No real emails sent</div>
        </div>
        <div className="landing-hero-visual" aria-label="Preview of Relay’s follow-up queue">
          <div className="landing-hero-float landing-float-top"><span>Needs attention</span><strong>4 contacts</strong></div>
          <div className="landing-preview-window"><div className="landing-preview-bar"><span className="landing-preview-logo">relay.</span><span>Today</span><span className="landing-preview-dots">•••</span></div><div className="landing-preview-body"><small>YOUR PRIORITY QUEUE</small><h2>Make the next move count.</h2><div className="landing-preview-contact"><span className="landing-avatar">PS</span><span><strong>Priya Sharma</strong><small>Demo and pricing requested</small></span><em>Overdue</em></div><div className="landing-preview-contact"><span className="landing-avatar lavender">ML</span><span><strong>Marcus Lee</strong><small>Proposal requested</small></span><em>Overdue</em></div><div className="landing-preview-contact"><span className="landing-avatar blue">NW</span><span><strong>Noah Williams</strong><small>Compare plan options</small></span><em>Due today</em></div></div></div>
          <div className="landing-hero-float landing-float-bottom"><span className="landing-float-check">✓</span><span><strong>People stay in control</strong><small>Approve each real message</small></span></div>
        </div>
      </section>

      <section id="how-it-works" className="landing-walkthrough">
        <div className="landing-section-heading"><h2>See the whole follow-up, before you try it.</h2><p>Click through a sample contact’s journey. This preview is illustrative; the workspace lets you do each step yourself.</p></div>
        <div className="landing-demo-layout">
          <div className="landing-step-list" role="tablist" aria-label="Follow-up walkthrough">{steps.map((item, index) => <button key={item.label} type="button" role="tab" aria-selected={step === index} className={step === index ? "active" : ""} onClick={() => setStep(index as DemoStep)}><span>{item.short}</span><strong>{item.label}</strong><Arrow /></button>)}</div>
          <div className="landing-demo-main"><DemoScene step={step} /><div className="landing-demo-controls"><span>Step {step + 1} of 4</span><button type="button" onClick={next}>{step === 3 ? "Start again" : "Next step"}<Arrow /></button></div></div>
        </div>
      </section>

      <section id="what-it-does" className="landing-capabilities">
        <div className="landing-section-heading"><h2>One place to decide, send, and learn.</h2><p>Everything on the page is grounded in the workflow you can explore in sample mode.</p></div>
        <div className="landing-capability-list"><div><span>01</span><h3>A queue with a reason</h3><p>Sort overdue and due-today contacts, then open the notes behind each suggested step.</p></div><div><span>02</span><h3>Your words, your approval</h3><p>Edit a draft or skip it. Real email delivery requires approval of the exact version shown.</p></div><div><span>03</span><h3>A record of what happened</h3><p>See recommendations, decisions, simulated or real sends, and manually marked replies in one timeline.</p></div><div><span>04</span><h3>Careful message tests</h3><p>Compare two variants while keeping each contact on the same version. Results wait for enough evidence.</p></div></div>
      </section>

      <section className="landing-honesty"><div><h2>Start with a safe sample. Connect accounts when you’re ready.</h2><p>The sample workspace uses fictional contacts and simulated sends. HubSpot and Gmail connections require configuration and your own accounts. The new workspace does not yet have an LLM API key field; sample recommendations and drafts currently use rules and templates.</p></div><Link className="landing-button solid" href="/workspace">Explore sample mode <Arrow /></Link></section>

      <section id="questions" className="landing-faq"><div className="landing-section-heading"><h2>Good questions to ask first.</h2></div><div><details><summary>Will Relay send emails automatically?</summary><p>No. Every real outbound email needs approval of its recipient and exact draft. Sample mode never sends a real email.</p></details><details><summary>Do I need HubSpot or Gmail to explore it?</summary><p>No. The sample workspace opens with fictional contacts. Live connections need OAuth setup and accounts.</p></details><details><summary>Where do I enter an LLM API key?</summary><p>The new frontend does not offer an LLM key setting yet. Its sample recommendations and drafts are rule and template based. The older Streamlit prototype has a Groq key field.</p></details></div></section>
    </main>

    <footer className="landing-footer"><span className="landing-footer-logo">relay<span>.</span></span><span>Thoughtful follow-through, with a person in control.</span><Link href="/workspace">Enter the workspace <Arrow diagonal /></Link></footer>
  </div>;
}
