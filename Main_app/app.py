import streamlit as st
import pandas as pd
from datetime import date, datetime
import os, sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph import build_graph
from model.llm import FollowUpGenerator
from important_functions.tools import init_state, enrich

# Page config
st.set_page_config(page_title="FollowUp AI", page_icon="🤖", layout="wide")

today = date.today()

STATUSES  = ["New", "Interested", "Follow-up Needed", "Closed"]
INTERESTS = ["Low", "Medium", "High"]
EXPORT_COLS = ["name", "contact", "company", "last_interaction",
               "next_followup", "status", "interest_level", "notes",
               "priority_score", "priority_label"]

# Initialising Session state

init_state()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    cols = [c for c in EXPORT_COLS if c in df.columns]
    return df[cols].to_csv(index=False).encode()


def has_data() -> bool:
    return st.session_state.df is not None and not st.session_state.df.empty



#  UPLOAD GATE — every session starts here, nothing else is shown until a CSV
#  is uploaded. Each browser session is completely independent.

if not has_data():
    st.title("🤖 AI Follow-Up Assistant")
    st.markdown("### Upload your leads CSV to get started")
    st.info(
        "Your lead list is kept in this app's server-side session memory. "
        "Generating messages sends lead details to Groq; sending emails uses Gmail. "
        "Download your CSV to keep your edits.",
        icon="🔒",
    )

    col_up, col_tmpl = st.columns([3, 2])

    with col_up:
        uploaded = st.file_uploader("Upload your CSV", type=["csv"], key=st.session_state.upload_key)
        if uploaded:
            file_key = f"{uploaded.name}_{uploaded.size}"
            if file_key != st.session_state.last_file_key:
                try:
                    raw = pd.read_csv(uploaded)
                    if not {"name", "contact"}.issubset(
                        {str(c).strip().lower().replace(" ", "_") for c in raw.columns}
                    ):
                        st.error("CSV must contain at least a **name** and **contact** column.")
                    else:
                        loaded = enrich(raw)
                        if loaded.empty:
                            st.error("CSV must contain at least one lead.")
                            st.stop()
                        st.session_state.df            = loaded
                        st.session_state.file_name     = uploaded.name
                        st.session_state.last_file_key = file_key
                        st.rerun()
                except Exception as e:
                    st.error(f"Could not read file: {e}")

    with col_tmpl:
        st.markdown("**No CSV yet? Download a template:**")
        template = pd.DataFrame([{
            "name": "Priya Sharma",
            "contact": "priya@example.com",
            "company": "TechCorp",
            "status": "Interested",
            "interest_level": "High",
            "notes": "Wants a demo next week",
            "last_interaction": str(today),
            "next_followup": str(today),
        }])
        st.download_button(
            "📥 Download template CSV",
            template.to_csv(index=False).encode(),
            "followup_template.csv",
            "text/csv",
        )

    st.stop()   # Nothing below runs until a CSV is loaded


#  MAIN APP — only reached after a CSV is uploaded

df = st.session_state.df

# Top bar 
col_title, col_export, col_reset = st.columns([4, 2, 1])
col_title.title("🤖 AI Follow-Up Assistant")
col_title.caption(
    f"📄 **{st.session_state.file_name}** · {len(df)} customers  "
    f"·  Session data on the app server"
)
col_export.download_button(
    label="📤 Download updated CSV",
    data=to_csv_bytes(df),
    file_name=st.session_state.file_name or "followup_updated.csv",
    mime="text/csv",
    use_container_width=True,
    help="Downloads your full list with all edits and priority scores applied.",
)
if col_reset.button("🔄 New file", use_container_width=True,
                    help="Clear this session and upload a different CSV"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

st.divider()

# Sidebar — Add a new customer 
with st.sidebar:
    st.header("➕ Add Customer")
    with st.form("add_form", clear_on_submit=True):
        f_name    = st.text_input("Name *")
        f_contact = st.text_input("Contact *")
        f_company = st.text_input("Company")
        f_last    = st.date_input("Last Interaction", value=today)
        f_next    = st.date_input("Next Follow-Up",   value=today)
        f_status  = st.selectbox("Status",         STATUSES)# defined a list above
        f_int     = st.selectbox("Interest Level", INTERESTS)
        f_notes   = st.text_area("Notes")
        add_btn   = st.form_submit_button("💾 Save")

    if add_btn:
        if f_name and f_contact:
            new_row = pd.DataFrame([{               #neccessory
                "name": f_name, "contact": f_contact, "company": f_company,
                "last_interaction": str(f_last), "next_followup": str(f_next),
                "status": f_status, "interest_level": f_int, "notes": f_notes,
            }])
            st.session_state.df = enrich(
                pd.concat([df, new_row], ignore_index=True)
            )
            st.success(f"✅ {f_name} added!")
            st.rerun()
        else:
            st.warning("Name and Contact are required.")

    st.divider()
    st.caption(
        "All changes (add / edit / delete) are held in server memory for this session.\n\n"
        "Use **Download updated CSV** at the top to save your work."
    )

    st.header("⚙️ Groq Settings")
    api_key = st.text_input(
        "Groq API Key", 
        type="password", 
        value="", # can be setted in .env file or can be directly setted in web
        help="Get a free key at console.groq.com"
    )
    st.header("📧 Gmail Settings")
    gmail_sender = st.text_input(
        "Gmail address",
        value="",
        help="The Gmail account you'll send from"
    )
    gmail_password = st.text_input(
        "Gmail app password",
        type="password",
        value="",
        help="Google Account -> Security -> 2-Step Verification ->App passwords"
    )
    

    

# Tabs 
tab_dash, tab_all, tab_edit, tab_message, tab_analytics, tab_agent = st.tabs([
    "📊 Dashboard", "👥 All Customers", "✏️ Edit / Delete", "✍️ Draft Message", "📈 Analytics", "📧 Email Agent"
])


# TAB 1 — DASHBOARD

with tab_dash:
    overdue   = (df["bucket"] == "Overdue").sum()
    due_today = (df["bucket"] == "Due Today").sum()
    upcoming  = (df["bucket"] == "Upcoming").sum()
    hot       = (df["priority_label"] == "🔴 Hot").sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Overdue",    int(overdue))
    c2.metric("📅 Due Today",  int(due_today))
    c3.metric("⏳ Upcoming",   int(upcoming))
    c4.metric("🔥 Hot Leads",  int(hot))

    st.subheader("Top Priority Leads")
    top_cols = ["name", "company", "next_followup", "status",
                "interest_level", "priority_score", "priority_label", "bucket"]
    st.dataframe(
        df[top_cols].head(10),
        use_container_width=True, hide_index=True,
    )

    sub_over, sub_today, sub_up = st.tabs(["Overdue", "Due Today", "Upcoming"])
    show_cols = ["name", "company", "status", "interest_level", "priority_score", "priority_label"]
    with sub_over:
        st.dataframe(df[df["bucket"] == "Overdue"][show_cols],
                     use_container_width=True, hide_index=True)
    with sub_today:
        st.dataframe(df[df["bucket"] == "Due Today"][show_cols],
                     use_container_width=True, hide_index=True)
    with sub_up:
        st.dataframe(df[df["bucket"] == "Upcoming"][show_cols],
                     use_container_width=True, hide_index=True)


# TAB 2 — ALL CUSTOMERS + EXPORT

with tab_all:
    st.subheader(f"All Customers ({len(df)})")
    search = st.text_input("Search name, contact, company, or notes", key="lead_search").strip()

    cs, ci, cb = st.columns(3) # remove that if it not really matters
    s_filter = cs.multiselect("Filter by Status",   df["status"].unique().tolist())
    i_filter = ci.multiselect("Filter by Interest", df["interest_level"].unique().tolist())
    b_filter = cb.multiselect("Filter by Bucket",   df["bucket"].unique().tolist())

    filtered = df.copy()
    if s_filter: filtered = filtered[filtered["status"].isin(s_filter)]
    if i_filter: filtered = filtered[filtered["interest_level"].isin(i_filter)]
    if b_filter: filtered = filtered[filtered["bucket"].isin(b_filter)]
    if search:
        searchable = filtered[["name", "contact", "company", "notes"]].fillna("").astype(str)
        matches = searchable.apply(lambda col: col.str.contains(search, case=False, regex=False)).any(axis=1)
        filtered = filtered[matches]

    st.dataframe(filtered.drop(columns=["_lead_id"], errors="ignore"), use_container_width=True, hide_index=True)

    st.download_button(
        "📤 Export filtered list as CSV",
        filtered.drop(columns=["_lead_id"], errors="ignore").to_csv(index=False).encode(),
        f"filtered_{st.session_state.file_name or 'export.csv'}",
        "text/csv",
    )

# TAB 3 — EDIT / DELETE

with tab_edit:
    st.subheader("Edit or Delete a Customer")

    options ={}
    for idx, row in df.iterrows():
        display_text = f"{row['name']} ({row['contact']}) · #{idx + 1}"
        options[display_text] = idx

    selected_label = st.selectbox("Select customer", list(options.keys()), key="edit_sel")
    sel_idx        = options[selected_label]
    row            = df.loc[sel_idx]

    with st.form("edit_form"):
        e_name    = st.text_input("Name",    value=row["name"])
        e_contact = st.text_input("Contact", value=row["contact"])
        e_company = st.text_input("Company", value=row["company"])

        last_date = pd.to_datetime(row["last_interaction"], errors="coerce")
        next_date = pd.to_datetime(row["next_followup"], errors="coerce")
        no_last = st.checkbox("No last interaction date", value=pd.isna(last_date))
        e_last = st.date_input("Last Interaction", value=today if pd.isna(last_date) else last_date.date(),
                               disabled=no_last)
        no_next = st.checkbox("No next follow-up date", value=pd.isna(next_date))
        e_next = st.date_input("Next Follow-Up", value=today if pd.isna(next_date) else next_date.date(),
                               disabled=no_next)
        e_status = st.selectbox("Status", STATUSES,
                                index=STATUSES.index(row["status"])
                                      if row["status"] in STATUSES else 0) # fallback to idx 0 if current value not in list for some reason
        e_int    = st.selectbox("Interest Level", INTERESTS,
                                index=INTERESTS.index(row["interest_level"])
                                      if row["interest_level"] in INTERESTS else 1)
        e_notes  = st.text_area("Notes", value=row["notes"])

        col_s, col_d = st.columns([3, 1])
        save_btn   = col_s.form_submit_button("💾 Save Changes")
        delete_btn = col_d.form_submit_button("🗑️ Delete", type="secondary")

    if save_btn:
        if not e_name.strip() or not e_contact.strip():
            st.warning("Name and Contact are required.")
            st.stop()
        updated = st.session_state.df.copy()
        updated.loc[sel_idx, "name"]             = e_name
        updated.loc[sel_idx, "contact"]          = e_contact
        updated.loc[sel_idx, "company"]          = e_company
        updated.loc[sel_idx, "last_interaction"] = "" if no_last else str(e_last)
        updated.loc[sel_idx, "next_followup"]    = "" if no_next else str(e_next)
        updated.loc[sel_idx, "status"]           = e_status
        updated.loc[sel_idx, "interest_level"]   = e_int
        updated.loc[sel_idx, "notes"]            = e_notes
        st.session_state.df = enrich(updated)
        st.success(f"✅ {e_name} updated.")
        st.rerun()

    if delete_btn:
        name_del = df.loc[sel_idx, "name"]
        updated  = st.session_state.df.drop(index=sel_idx).reset_index(drop=True)
        st.session_state.msg_log.pop(df.loc[sel_idx, "_lead_id"], None)
        if updated.empty:
            st.session_state.df = None
            st.session_state.last_file_key = None
            st.session_state.upload_key = str(uuid.uuid4())
        else:
            st.session_state.df = enrich(updated)
        st.success(f"🗑️ {name_del} removed.")
        st.rerun()




# TAB 4 — DRAFT A MESSAGE FOR ANY LEAD

with tab_message:
    st.subheader("Draft a follow-up message")
    lead_options = {
        f"{row['name']} ({row['contact']}) · #{idx + 1}": row["_lead_id"]
        for idx, row in df.iterrows()
    }
    lead_label = st.selectbox("Customer", list(lead_options), key="draft_lead")
    lead_id = lead_options[lead_label]
    lead = df.loc[df["_lead_id"] == lead_id].iloc[0]
    tone = st.selectbox("Tone", ["Professional", "Friendly", "Polite", "Persuasive"])

    if st.button("Generate message", type="primary"):
        if not api_key.strip():
            st.error("Enter your Groq API key in the sidebar first.")
        else:
            try:
                with st.spinner("Generating message..."):
                    message = FollowUpGenerator(api_key).generate(lead.to_dict(), tone=tone)
                entry = {"tone": tone, "message": message, "ts": datetime.now().strftime("%Y-%m-%d %H:%M")}
                st.session_state.msg_log.setdefault(lead_id, []).append(entry)
            except Exception as exc:
                st.error(f"Could not generate a message: {exc}")

    history = st.session_state.msg_log.get(lead_id, [])
    if history:
        st.text_area("Latest draft (copy or edit here)", value=history[-1]["message"], height=180, key=f"latest_{lead_id}_{len(history)}")
        with st.expander(f"Previous drafts ({len(history)})"):
            for entry in reversed(history):
                st.caption(f"{entry['ts']} · {entry['tone']}")
                st.write(entry["message"])
    else:
        st.caption("No drafts for this customer in this session yet.")


# TAB 5 — ANALYTICS 

with tab_analytics:
    st.subheader("Lead Analytics")
    r1l, r1r = st.columns(2)

    with r1l:
        

        sc = df["status"].value_counts()
        st.subheader("Leads by Status")
        st.bar_chart(sc)
    with r1r:
        st.subheader("Interest Level Breakdown")

        interest_counts = df["interest_level"].value_counts()

        st.bar_chart(interest_counts)

  
    bc = df["bucket"].value_counts().reset_index()
    bc.columns = ["Bucket", "Count"]
    
    st.subheader("Follow-Up Urgency")
    
    st.bar_chart(
    bc.set_index("Bucket")["Count"],
    use_container_width=True
        )
    
with tab_agent:
    st.subheader("📧 AI Email Agent")
    st.info("Generates follow-up emails for overdue customers, lets you review and edit them, then sends them via Gmail.", icon="🤖")

    # Step 1: Customer selection
    overdue_df = df[df["bucket"] == "Overdue"]

    if overdue_df.empty:
        st.info("No overdue customers right now.")

    agent_options = {
        f"{row['name']} ({row['contact']}) · #{idx + 1}": row["_lead_id"]
        for idx, row in overdue_df.iterrows()
    }
    selected_labels = st.multiselect(
        "Select customers to follow up with",
        options=list(agent_options),
        default=list(agent_options),
    )
    selected_ids = {agent_options[label] for label in selected_labels}
    selected_df = overdue_df[overdue_df["_lead_id"].isin(selected_ids)]

    # Step 2: Run agent
    run_btn = st.button("🚀 Run Agent", type="primary",
                        disabled=not selected_labels or "agent_emails" in st.session_state)

    if run_btn: # checking api keys ^^
        if not api_key:
            st.error("Please enter your Groq API key in the sidebar first.")
            st.stop()
        if not gmail_sender or not gmail_password:
            st.error("Please enter your Gmail address and app password in the sidebar.")
            st.stop()
        try:
            llm = FollowUpGenerator(api_key)
        except Exception as e:
            st.error(f"Could not initialize Groq: {e}")
            st.stop()

        # Building graph
        
        graph = build_graph(llm, gmail_sender, gmail_password)
        thread = {"configurable": {"thread_id": st.session_state.session_thread_id}}

        # Preparing customer list from selected dataframe -->[{name:xx,age:yy}]
        customers = selected_df.to_dict(orient="records") #^^

        with st.spinner("Generating emails..."):
            try:
                result = graph.invoke({"customers": customers}, config=thread)
            except Exception as exc:
                st.error(f"Could not generate drafts: {exc}")
                st.stop()

        # Storing graph + thread in session for human-Resume step
        st.session_state["agent_graph"]  = graph
        st.session_state["agent_thread"] = thread
        st.session_state["agent_emails"] = result["__interrupt__"][0].value["emails"]
        st.session_state["agent_draft_id"] = str(uuid.uuid4())
        st.rerun()
    
    # After all generated Drafts
    # Step 3: Review & Edit
    if "agent_emails" in st.session_state:
        st.divider()
        st.subheader("📝 Review & Edit Emails")
        st.caption("Edit any email below. Uncheck to skip sending.")

        edited_emails = []
        draft_id = st.session_state["agent_draft_id"]

        for i, email in enumerate(st.session_state["agent_emails"]):  #^^^^^^^^^^
            with st.expander(
                f"{'✅' if email.get('approved', True) else '❌'} " # ^^^
                f"{email['name']} — {email['company']} ({email['email']})",
                expanded=True
            ):
                if email.get("error"):
                    st.error(f"Draft generation failed: {email['error']}")
                approved = st.checkbox("Approve for sending", value=email.get("approved", False),
                                       key=f"approve_{draft_id}_{i}", disabled=bool(email.get("error")))
                subject  = st.text_input("Subject", value=email["subject"], key=f"subject_{draft_id}_{i}")
                body     = st.text_area("Email body", value=email["body"], height=180, key=f"body_{draft_id}_{i}")

                edited_emails.append({
                    **email,
                    "approved": approved,
                    "subject":  subject,
                    "body":     body,
                }) #^^

        st.divider()
        send_btn = st.button("📤 Approve & Send", type="primary")

        if send_btn:
            from langgraph.types import Command

            if any(e["approved"] and (not e["subject"].strip() or not e["body"].strip())
                   for e in edited_emails):
                st.error("Each approved email needs a subject and body.")
                st.stop()

            graph  = st.session_state["agent_graph"]
            thread = st.session_state["agent_thread"]

            with st.spinner("Sending emails...."):
                final = graph.invoke(
                    Command(resume=edited_emails),
                    config=thread,
                )

            # Step 4: Results
            st.divider()
            st.subheader("📊 Send Results")

            sent    = [r for r in final["sent_results"] if r["status"] == "sent"] #^^^
            skipped = [r for r in final["sent_results"] if r["status"] == "skipped"]
            failed  = [r for r in final["sent_results"] if r["status"] == "failed"]

            c1, c2, c3 = st.columns(3)
            c1.metric("✅ Sent",    len(sent))
            c2.metric("⏭️ Skipped", len(skipped))
            c3.metric("❌ Failed",  len(failed))

            for r in final["sent_results"]:
                if r["status"] == "sent":
                    st.success(f"✅ Sent to {r['name']} ({r['email']})")
                elif r["status"] == "skipped":
                    st.info(f"⏭️ Skipped {r['name']}")
                elif r["status"] == "failed":
                    st.error(f"❌ Failed for {r['name']}: {r['error']}")

            # Clearing agent state after sending mial
            for key in ["agent_graph", "agent_thread", "agent_emails", "agent_draft_id"]:
                del st.session_state[key] #^^
