---
name: Relay
description: Calm green interfaces for human-reviewed sales outreach agents
colors:
  forest: "#153e35"
  deep: "#102f2a"
  lime: "#d9efb9"
  paper: "#f8faf5"
  white: "#fff"
  ink: "#20352e"
  muted: "#52685c"
  line: "#dce4d8"
  focus: "#6b9655"
  primary-hover: "#255b49"
  quiet-hover: "#e9f1e2"
  preview-header: "#edf2e7"
  preview-surface: "#f7f9f3"
  blue-surface: "#edf6fb"
  blue-accent: "#346b8c"
  peach-surface: "#fff2e9"
  peach-accent: "#99522f"
  lime-surface: "#f3f8d9"
  lime-accent: "#68751c"
  pink-surface: "#fcf0f7"
  pink-accent: "#994776"
  pending-surface: "#f9efdc"
  pending-ink: "#805323"
typography:
  display:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(40px, 4.2vw, 60px)"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(32px, 3.5vw, 48px)"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.035em"
  body:
    fontFamily: "DM Sans, Arial, sans-serif"
    fontSize: "15px"
    lineHeight: 1.75
  hero-body:
    fontFamily: "DM Sans, Arial, sans-serif"
    fontSize: "16px"
    lineHeight: 1.7
  label:
    fontFamily: "DM Sans, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 800
rounded:
  field: "7px"
  control: "8px"
  workflow-row: "10px"
  editor: "14px"
  preview: "16px"
  stack: "28px"
  stack-mobile: "22px"
spacing:
  small: "8px"
  control-gap: "12px"
  medium: "16px"
  panel: "24px"
  large: "30px"
  section: "100px"
components:
  button-primary:
    backgroundColor: "{colors.forest}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "14px 22px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-quiet:
    textColor: "{colors.forest}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "14px 22px"
  input:
    backgroundColor: "#fbfcf8"
    textColor: "{colors.forest}"
    rounded: "{rounded.field}"
    padding: "12px"
  preview:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.preview}"
  config-editor:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.editor}"
    padding: "26px 30px"
  pending-status:
    backgroundColor: "{colors.pending-surface}"
    textColor: "{colors.pending-ink}"
    rounded: "5px"
    padding: "6px 9px"
---

# Design System: Relay

## Overview

**Creative North Star: "The Visible Workflow"**

Relay pairs a calm green identity with visible, inspectable work. Forest green anchors actions and dense workflow regions; warm pale surfaces give context, drafts, and decisions room to breathe. The interface feels professional and approachable through clear typography, gentle corners, and restrained depth.

The implemented landing extends the existing workspace identity. Product-shaped previews show source context, preparation, review, and recorded outcomes. Labels make illustrative, sample, planned, and connected behavior distinguishable; human control remains visible beside the action.

**Key Characteristics:**

- Forest green with warm pale surfaces
- Bold geometric headings and readable supporting text
- Product-shaped evidence with visible status labels
- Gentle corners and restrained ambient depth

## Colors

The palette combines deep botanical greens with warm paper, white product surfaces, and subdued pastel workflow stages. Frontmatter values are normative, extracted from `frontend/app/landing.css`; the workspace has closely related existing tokens in `frontend/app/globals.css`.

### Primary

- **Forest:** brand mark, primary buttons, agent node, and walkthrough backdrop.
- **Deep:** deeper green support within the existing identity.
- **Lime:** selection, agent icon, and light detail against forest surfaces.
- **Primary hover / Quiet hover:** visible control feedback.
- **Focus:** the shared keyboard focus ring.

### Secondary

- **Blue / Peach / Lime / Pink stage pairs:** pale stage backgrounds and corresponding accents for the four walkthrough cards. These distinguish steps rather than replacing the green brand.
- **Pending pair:** warm status treatment for drafts awaiting approval.

### Neutral

- **Paper / White:** page background and product panels.
- **Ink / Muted:** main text and supporting descriptions.
- **Line:** subtle separators and structured boundaries.
- **Preview header / Preview surface:** tonal grouping within product previews.

**The Visible Decision Rule.** Keep the approval state and source context legible beside the proposed action.

## Typography

**Display Font:** Manrope, sans-serif. **Body Font:** DM Sans, Arial, sans-serif. Both are loaded by the global stylesheet.

Bold geometric headings establish confidence; quieter supporting text explains the work without competing with the product proof. The hero uses the display role, section titles use headline, and compact buttons use label. Product preview text is intentionally denser (typically 10–13px); explanatory page copy uses 14–17px with generous line height.

At the mobile breakpoint, hero type uses `clamp(39px, 7.5vw, 54px)` and supporting text becomes 15px. Section headings become 34px in the main lower sections. Copy widths are bounded: hero text to 49ch, workflow descriptions to 42ch, and configuration explanation to 50ch.

**The Two Voices Rule.** Use Manrope for confident headings and DM Sans for supporting copy and interface text.

## Layout

The landing uses a centered 1400px outer container with 5% horizontal gutters; lower sections use a 1260px maximum. The hero places left-aligned text beside an animated dashboard on the right, with a `1fr 1.05fr` grid and 54px gap. The dashboard compresses source, agent, and human review into a three-column flow above its review panel. Two-column product and configuration regions balance explanation with tangible UI. Major lower sections use 100px vertical padding.

At 1400px, lower sections retain 5% side margins. At 1050px, gaps and panel padding tighten. At 760px, product previews, configuration, learning, and FAQ stack into one column; navigation links hide while the brand and CTA remain. At 400px, controls and compact previews tighten further.

The implemented walkthrough is a shared sticky stack: four paired copy/UI cards advance through connect, prepare, review, and execute. The desktop section heading stays pinned at the top; card offsets follow its measured height plus 16px and increase by 16px per card. Four left-side dots track and link to the current card. The cards use a 1:1 grid, 32px gap, 24px padding, and a 540px minimum height. Mobile uses a single column and 24px sticky top. Short mobile viewports and reduced-motion preferences restore ordinary document flow. This is a landing-specific signature, not a requirement for workspace screens.

## Elevation & Depth

Tonal layering and thin boundaries organize ordinary UI. Diffuse shadows lift the product previews, while dark forest sections create larger changes in visual depth. The hero preview uses `0 24px 60px #24483212`; walkthrough scenes use `0 22px 50px #071d1833`, overridden inside stack visuals by `0 20px 45px #173c3414`.

**The Useful Depth Rule.** Reserve substantial shadows for product previews; use borders and tonal surfaces for ordinary fields and rows.

## Shapes

Gentle rectangular corners dominate. Controls use the control radius, inputs the field radius, and workflow rows the workflow-row radius. Larger preview panels and editors use their respective frontmatter values. Sticky cards have the broadest corners, reduced on mobile. Small circular marks are reserved for timeline and status indicators.

## Components

- **Buttons:** solid forest primary and outlined quiet variants. Both use a 48px minimum height, compact bold labels, and inline 20px icons. Hover changes background over 0.18s. Keyboard focus uses a 3px focus-colored outline with 4px offset.
- **Inputs:** pale background, thin green-gray boundary, 7px corners, and 12px padding. A visible label precedes each field. Configuration fields on the landing modify an illustrative preview only.
- **Navigation:** 86px desktop height, a bold Manrope wordmark, compact central links, and an outlined CTA; mobile height is 72px. Link hover uses an underline with 5px offset.
- **Status chips:** compact warm pending-approval treatment and muted green preview labels. Status is communicated in text alongside color.
- **Product preview:** context and draft prepare automatically in 0.9s and 1.1s while visible, then pause indefinitely at human review. A floating white review panel enters over the dimmed draft, with a human icon, explicit paused state, recipient/subject, and “Your agent is waiting. You make the call.” A full-width coral Approve button (#ff633e with #27140d text) and secondary Skip action resolve the checkpoint. Only click, keyboard activation, or tap advances to simulated delivery or a skipped record. The demonstration makes no backend request and sends no email. Reduced motion shows a static review scene with the same working approval gate. Offscreen/hidden preparation pauses. Panel transitions use 0.3s; the button has one bounded 0.55s pop and no repeated pulse.
- **Configuration editor:** white bordered panel with explicit planned/preview status, editable goal, selectable tone, data sources, and an approval reminder. It must remain clear that this interaction does not persist settings.
- **Walkthrough cards:** paired copy and product scenes within distinct pale stage surfaces. Scroll progress scales earlier cards from 1 to 0.94 and dims them to 0.88; the final card stays unchanged. Reduced motion disables these effects and sticky positioning.
- **FAQ:** native disclosure rows with thin separators, clear headings, and supporting body text.

## Do's and Don'ts

### Do:

- Do preserve the existing forest green and warm off-white identity.
- Do place readable status and source context beside workflow actions.
- Do keep keyboard focus visible and honor reduced motion.
- Do use pastel stage colors to distinguish the walkthrough while retaining green as the brand anchor.

### Don't:

- Don't imply a sample, illustration, or configuration preview changes a live workflow.
- Don't replace the established green identity with an unrelated palette.
- Don't make essential content depend on scroll animation or hover.
