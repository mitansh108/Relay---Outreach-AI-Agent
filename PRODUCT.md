# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Small B2B sales teams evaluating AI agents for sales outreach. A salesperson needs to see who needs attention, understand the reason, review a suggested action, and record the outcome.

## Product Purpose

Relay aims to let sales teams configure outreach agents around their own customer data, goals, and voice while retaining human control. The implemented first release demonstrates an agent workflow through a prioritized queue, contact context, reviewed drafts, activity, and careful message experiments.

## Positioning

AI agents for sales outreach, with a human at the helm. Relay brings customer data, preparation, review, and execution into one inspectable workflow. The durable vision is configurable agents that work from the team’s own data; the current product provides a concrete follow-up workflow and a clearly labeled configuration preview.

## Operating Context

The app has a credential-free sample workspace with fictional contacts and simulated sends. HubSpot and Gmail connectors require configuration and accounts. The older Streamlit prototype remains separate. The Connections screen now offers Groq model configuration and connection testing. Keys stay encrypted on the server when deployment encryption is configured; environment credentials are also supported. Without a configured model, recommendations use clearly labeled rules and templates. Model-backed generation is implemented and tested with mocked provider responses; live-account validation remains outstanding. The landing dashboard is illustrative. Its goal and tone controls change a local preview only; they do not persist agent configuration or alter live recommendations.

## Capabilities and Constraints

The sample app shows Today, Contacts, Review, Activity, Insights, Experiments, and Connections. No real email sends in demo mode. Each real send requires approval. Reply outcomes are marked manually. The work uses Next.js, FastAPI, SQLite, LangGraph, and optional HubSpot and Gmail OAuth connections. CSV preview and import are implemented. HubSpot data import and Gmail sends require configured OAuth credentials and connected accounts.

## Planned Agent Vision

Persisted, configurable agent goals and tone are planned. Broader agent customization and learning from outcomes are product direction, not current demonstrated capabilities. The current app records activity, manually marked replies, and experiment outcomes; it does not establish autonomous learning or automatic reply ingestion.

## Brand Commitments

The existing frontend uses the name Relay, a calm green and warm off-white palette, and a clear, professional voice. The new landing page should retain that recognizable identity.

## Evidence on Hand

The repository includes `sample_leads.csv`, an interactive sample workspace, `PRODUCT_PLAN.md`, and `PRODUCT_DIAGRAMS.md`. There are no customer testimonials, performance benchmarks, or independently verified conversion claims.

## Product Principles

- Show the next useful step with the reason behind it.
- Keep the person in control of every real outbound message.
- Make sample behavior and live connected behavior visibly distinct.
- Show observed outcomes without inventing impact.
