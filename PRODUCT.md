# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Small B2B sales teams evaluating a follow-up copilot. A salesperson needs to see who needs attention, understand the reason, review a suggested action, and record the outcome.

## Product Purpose

Relay organizes follow-up work around a prioritized queue, contact context, human-reviewed drafts, activity, and careful message experiments. The first release is a single-workspace demo that can be customized for a company.

## Positioning

Relay brings the next contact, supporting context, proposed message, and explicit human approval into one short workflow.

## Operating Context

The app has a credential-free sample workspace with fictional contacts and simulated sends. HubSpot and Gmail connectors require configuration and accounts. The older Streamlit prototype remains separate. The new frontend currently has no field for an LLM API key; its sample recommendations and drafts are rule and template based.

## Capabilities and Constraints

The sample app shows Today, Contacts, Review, Activity, Insights, Experiments, and Connections. No real email sends in demo mode. Each real send requires approval. Reply outcomes are marked manually. The work uses Next.js, FastAPI, SQLite, LangGraph, and optional HubSpot and Gmail OAuth connections.

## Brand Commitments

The existing frontend uses the name Relay, a calm green and warm off-white palette, and a clear, professional voice. The new landing page should retain that recognizable identity.

## Evidence on Hand

The repository includes `sample_leads.csv`, an interactive sample workspace, `PRODUCT_PLAN.md`, and `PRODUCT_DIAGRAMS.md`. There are no customer testimonials, performance benchmarks, or independently verified conversion claims.

## Product Principles

- Show the next useful step with the reason behind it.
- Keep the person in control of every real outbound message.
- Make sample behavior and live connected behavior visibly distinct.
- Show observed outcomes without inventing impact.
