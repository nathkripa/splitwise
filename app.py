import streamlit as st
from supabase import create_client
from decimal import Decimal
import utilss as utils
import pandas as pd

# --- Setup page ---
st.set_page_config(page_title='🏢 Splitwise — Office Edition', page_icon='💸', layout='wide')

# --- Mode selection ---
if "mode" not in st.session_state:
    st.session_state.mode = "Guest"
st.session_state.mode = st.sidebar.radio(
    "Select Mode",
    options=["Login Mode", "Guest Mode"],
    index=0 if st.session_state.mode == "Login Mode" else 1
)
is_login_mode = st.session_state.mode == "Login Mode"

# --- Login state ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- Login form for Login Mode ---
def login_form():
    st.sidebar.markdown("### 🔐 Login Required")
    user_id = st.sidebar.text_input("User ID")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        # Replace with your real auth check
        if user_id == st.secrets['app_username'] and password == st.secrets['app_password']:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid credentials")

if is_login_mode and not st.session_state.logged_in:
    login_form()
    st.warning("Please log in to access the app.")
    st.stop()

# --- Initialize Supabase client or None ---
supabase = None
if is_login_mode and st.session_state.logged_in:
    SUPABASE_URL = st.secrets['url']
    SUPABASE_ANON_KEY = st.secrets['key']
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error('Please add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets.')
        st.stop()
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# --- Header ---
st.markdown('<div style="font-size:2.2rem; font-weight:bold; color:#4CAF50;">💸 Splitwise — Office Edition</div>', unsafe_allow_html=True)
st.caption("Easily manage and split expenses for your team. Powered by Streamlit + Supabase.")

# --- Sidebar Danger Zone Flush button in Login Mode ---
if is_login_mode and st.session_state.logged_in:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⚠️ Danger Zone")
        if st.button("🗑️ Flush Entire Database"):
            st.session_state.show_flush_confirm = True

    if st.session_state.get("show_flush_confirm", False):
        st.warning("This will permanently DELETE ALL data from the database! Are you sure?")
        col1, col2 = st.columns(2)
        if col1.button("Yes, Delete Everything"):
            try:
                supabase.table("transactions").delete().neq('id', 0).execute()
                supabase.table("expenses").delete().neq('id', 0).execute()
                supabase.table("members").delete().neq('id', 0).execute()
                st.success("✅ Database flushed successfully.")
                st.session_state.show_flush_confirm = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error flushing DB: {e}")
        if col2.button("Cancel"):
            st.session_state.show_flush_confirm = False

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["👥 Members", "➕ Add Expense", "📜 History", "📊 Balances"])

# --- MEMBERS ---
with tab1:
    st.markdown('<h3>👥 Manage Members</h3>', unsafe_allow_html=True)
    with st.form('member_form', clear_on_submit=True):
        name = st.text_input('Member name', key='member_name')
        add = st.form_submit_button('Add Member')
        if add:
            if not name.strip():
                st.error('⚠️ Name required')
            else:
                u = utils.create_member(supabase, name.strip())
                if u:
                    st.success(f"✅ Added {u['name']}")
    members_df = utils.fetch_members(supabase)
    st.dataframe(members_df, use_container_width=True)

# --- ADD EXPENSE ---
with tab2:
    st.markdown('<h3>➕ Add New Expense</h3>', unsafe_allow_html=True)
    members_df = utils.fetch_members(supabase)
    if members_df.empty:
        st.info('ℹ️ Add some members first.')
    else:
        with st.form('expense_form', clear_on_submit=True):
            col1, col2 = st.columns(2)
            title = col1.text_input('Title (e.g., Lunch with team)')
            amount = col2.number_input('Total amount (₹)', min_value=0.0, format='%.2f')
            payer = st.selectbox('Payer', options=members_df['name'].tolist())
            participants = st.multiselect('Participants', options=members_df['name'].tolist(), default=members_df['name'].tolist())
            description = st.text_area('Description (optional)')
            submit = st.form_submit_button('💾 Create Expense')
            if submit:
                # Map names to IDs
                if is_login_mode:
                    # query fresh from supabase for consistency
                    name2id = {r['name']: r['id'] for r in (supabase.table('members').select('*').execute().data or [])}
                else:
                    # guest mode from session_state
                    name2id = {r['name']: r['id'] for r in st.session_state.guest_members}
                payer_id = name2id[payer]
                participant_ids = [name2id[p] for p in participants] or [payer_id]
                expense_id = utils.create_expense_with_transactions(
                    supabase,
                    payer_id=payer_id,
                    amount=Decimal(str(amount)),
                    title=title or '',
                    description=description or '',
                    participant_ids=participant_ids
                )
                st.success('✅ Expense created')

# --- HISTORY ---
with tab3:
    st.markdown('<h3>📜 Expense History</h3>', unsafe_allow_html=True)
    hist_df = utils.fetch_history(supabase)
    if hist_df.empty:
        st.info('ℹ️ No expenses yet.')
    else:
        st.dataframe(hist_df, use_container_width=True)
        csv = hist_df.to_csv(index=False).encode('utf-8')
        st.download_button('📥 Download CSV', data=csv, file_name='history.csv', mime='text/csv')

# --- BALANCES ---
with tab4:
    st.markdown('<h3>📊 Balances & Settlements</h3>', unsafe_allow_html=True)
    bal_df = utils.compute_balances(supabase)
    if bal_df.empty:
        st.info('ℹ️ No balances yet. Add members and expenses first.')
    else:
        st.markdown("### Current Balances")
        bal_table = bal_df.copy()
        bal_table['Balance (₹)'] = bal_table['balance'].apply(lambda x: f"₹{x:.2f}")
        st.dataframe(bal_table[['name', 'Balance (₹)']], use_container_width=True)

        st.markdown("### 💱 Suggested Settlements")
        pos = bal_df[bal_df.balance > 0.01][['name','balance']].to_dict('records')
        neg = bal_df[bal_df.balance < -0.01][['name','balance']].to_dict('records')
        if not pos or not neg:
            st.info("✅ All balances are settled!")
        else:
            pos = sorted(pos, key=lambda x: x['balance'], reverse=True)
            neg = sorted(neg, key=lambda x: x['balance'])
            i, j = 0, 0
            transfers = []
            while i < len(pos) and j < len(neg):
                p = pos[i]
                n = neg[j]
                amt = min(p['balance'], -n['balance'])
                transfers.append({'From': n['name'], 'To': p['name'], 'Amount (₹)': round(amt, 2)})
                p['balance'] -= amt
                n['balance'] += amt
                if abs(p['balance']) < 1e-9: i += 1
                if abs(n['balance']) < 1e-9: j += 1
            transfers_df = pd.DataFrame(transfers)
            st.dataframe(transfers_df, use_container_width=True)
