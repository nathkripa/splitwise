import streamlit as st
from supabase import create_client
from decimal import Decimal
import utils

st.set_page_config("🏢 Splitwise — Office Edition", "💸", layout="wide")

# Mode & Login State
if "mode" not in st.session_state:
    st.session_state.mode = "Guest"
st.session_state.mode = st.sidebar.radio("Select Mode", ["Login Mode", "Guest Mode"],
                                         index=0 if st.session_state.mode=="Login Mode" else 1)
is_login = st.session_state.mode == "Login Mode"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Cached Supabase Client
@st.cache_resource
def get_supabase():
    if is_login and st.session_state.logged_in:
        return create_client(st.secrets['url'], st.secrets['key'])
    return None

supabase = get_supabase()

# Cached Data Fetchers
@st.cache_data
def fetch_members_df():
    return utils.fetch_members(supabase)

@st.cache_data
def fetch_history_df():
    return utils.fetch_history(supabase)

@st.cache_data
def fetch_balances_df():
    return utils.compute_balances(supabase)

# Helper function to clear all caches
def clear_all_caches():
    fetch_members_df.clear()
    fetch_history_df.clear()
    fetch_balances_df.clear()

# Login Form
def login_form():
    st.sidebar.markdown("### 🔐 Login Required")
    uid = st.sidebar.text_input("User ID")
    pwd = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if uid == st.secrets['app_username'] and pwd == st.secrets['app_password']:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid credentials")

if is_login and not st.session_state.logged_in:
    login_form()
    st.warning("Please log in to access the app.")
    st.stop()

# Header
st.markdown("<div style='font-size:2.2rem; font-weight:bold; color:#4CAF50;'>💸 Splitwise — Office Edition</div>", unsafe_allow_html=True)
st.caption("Easily manage and split expenses for your team. Powered by Streamlit + Supabase.")

# Danger Zone — delete with caution
if is_login and st.session_state.logged_in:
    with st.sidebar:
        st.button("🔓 Logout", on_click=lambda: st.session_state.update(logged_in=False) or st.rerun())
        st.markdown("---\n### ⚠️ Danger Zone")
        admin_pw = st.text_input("Admin password", type="password", key="flush_pass")
        if st.button("🗑️ Flush Database"):
            if admin_pw == st.secrets['admin_pass']:
                if st.confirm("This will delete ALL data. Continue?"):
                    # Batch delete via multiple .delete().in()
                    for tbl in ['transactions','expenses','members']:
                        supabase.table(tbl).delete().neq('id', None).execute()
                    clear_all_caches()
                    st.success("Database flushed.")
                    st.rerun()
            else:
                st.error("❌ Incorrect admin password")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["👥 Members", "➕ Add Expense", "📜 History", "📊 Balances"])

# Tab 1: Members
with tab1:
    st.markdown("### Manage Members")
    members_df = fetch_members_df()
    with st.form('member_form', clear_on_submit=True):
        name = st.text_input("Member name")
        if st.form_submit_button("Add Member"):
            if not name.strip():
                st.error("Name required")
            else:
                utils.create_member(supabase, name.strip())
                clear_all_caches()
                st.success(f"Added {name.strip()}")
    st.dataframe(members_df, use_container_width=True)

# Tab 2: Add Expense
with tab2:
    st.markdown("### Add Expense")
    members_df = fetch_members_df()
    if members_df.empty:
        st.info("Add members first.")
    else:
        name2id = dict(zip(members_df['name'], members_df['id']))
        with st.form('expense_form', clear_on_submit=True):
            title = st.text_input("Title")
            amount = st.number_input("Total amount (₹)", min_value=0.0, format="%.2f")
            payer = st.selectbox("Payer", members_df['name'])
            participants = st.multiselect("Participants", members_df['name'], default=members_df['name'])
            description = st.text_area("Description (optional)")
            if st.form_submit_button("Create Expense"):
                utils.create_expense_with_transactions(
                    supabase,
                    payer_id=name2id[payer],
                    amount=Decimal(str(amount)),
                    title=title or '',
                    description=description or '',
                    participant_ids=[name2id[p] for p in participants]
                )
                clear_all_caches()
                st.success("Expense created.")

# Tab 3: History
with tab3:
    st.markdown("### Expense History")
    hist_df = fetch_history_df()
    if hist_df.empty:
        st.info("No expenses yet.")
    else:
        for exp_id, group in hist_df.groupby("expense_id"):
            title = group['title'].iloc[0]
            st.markdown(f"#### {title}")
            st.dataframe(group.drop(columns=['expense_id']), use_container_width=True)
            if st.button(f"Delete '{title}'", key=f"del_{exp_id}"):
                utils.delete_expense(supabase, exp_id)
                clear_all_caches()
                st.success(f"Deleted {title}")
                st.rerun()

# Tab 4: Balances & Settlements
with tab4:
    st.markdown("### Balances & Settlements")
    bal_df = fetch_balances_df()
    if bal_df.empty:
        st.info("No balances yet.")
    else:
        bal_df['Balance (₹)'] = bal_df['balance'].apply(lambda x: f"₹{x:.2f}")
        st.dataframe(bal_df[['name','Balance (₹)']], use_container_width=True)

        st.markdown("### Suggested Settlements")
        settlements = utils.compute_settlements(bal_df)
        if not settlements:
            st.info("All balances settled!")
        else:
            if 'paid' not in st.session_state:
                st.session_state.paid = set()
            for idx, row in enumerate(settlements):
                key = f"paid_{idx}"
                is_paid = key in st.session_state.paid
                col1, col2 = st.columns([1,6])
                with col1:
                    if st.button("PAID" if not is_paid else "UNPAID", key=key):
                        st.session_state.paid.symmetric_difference_update({key})
                        st.rerun()
                with col2:
                    style = "text-decoration: line-through; color: gray;" if is_paid else ""
                    st.markdown(f"<div style='{style}'>From: <b>{row['From']}</b> → To: <b>{row['To']}</b> — ₹{row['Amount (₹)']}</div>", unsafe_allow_html=True)
