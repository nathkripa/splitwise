import streamlit as st
import pandas as pd
from supabase import create_client, Client
from decimal import Decimal
import utils

# ---------- CONFIG ----------
st.set_page_config(page_title='🏢 Splitwise — Office Edition', page_icon='💸', layout='wide')

# ---------- MODE SELECTION ----------
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
        # TODO: Replace below with your real auth check
        if user_id == st.secrets['app_username'] and password == st.secrets['app_password']:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid credentials")

if is_login_mode and not st.session_state.logged_in:
    login_form()
    st.warning("Please log in to access the app.")
    st.stop()
# ---------- INIT SUPABASE ----------
if is_login_mode and st.session_state.logged_in:
    SUPABASE_URL = st.secrets['url']
    SUPABASE_ANON_KEY = st.secrets['key']
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error('Please add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets.')
        st.stop()
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
else:
    supabase = None

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
                supabase.table("transactions").delete().neq('id', -1).execute()
                supabase.table("expenses").delete().neq('id',-1).execute()
                supabase.table("members").delete().neq('id', -1).execute()
                st.success("✅ Database flushed successfully.")
                st.session_state.show_flush_confirm = False
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Error flushing DB: {e}")

        if col2.button("Cancel"):
            st.session_state.show_flush_confirm = False

# ---------- GUEST MODE HELPERS ----------
def guest_fetch_members():
    return pd.DataFrame(st.session_state.get("guest_members", []), columns=["id", "name"])

def guest_create_member(name):
    if "guest_members" not in st.session_state:
        st.session_state.guest_members = []
    new_id = len(st.session_state.guest_members) + 1
    new_member = {"id": new_id, "name": name}
    st.session_state.guest_members.append(new_member)
    return new_member

def guest_fetch_history():
    return pd.DataFrame(st.session_state.get("guest_history", []))

def guest_create_expense(payer_id, amount, title, description, participant_ids):
    if "guest_history" not in st.session_state:
        st.session_state.guest_history = []
    exp_id = len(st.session_state.guest_history) + 1
    st.session_state.guest_history.append({
        "id": exp_id,
        "payer_id": payer_id,
        "amount": float(amount),
        "title": title,
        "description": description,
        "participants": participant_ids
    })
    guest_update_balances(payer_id, amount, participant_ids)

def guest_compute_balances():
    return pd.DataFrame(st.session_state.get("guest_balances", []), columns=["id", "name", "balance"])

def guest_update_balances(payer_id, amount, participants):
    if "guest_balances" not in st.session_state:
        st.session_state.guest_balances = []
    # Ensure all participants are in balances
    member_ids = {m["id"]: m["name"] for m in st.session_state.guest_members}
    balances = {b["id"]: b["balance"] for b in st.session_state.guest_balances}
    for mid in member_ids:
        balances.setdefault(mid, 0.0)

    share = float(amount) / len(participants)
    for pid in participants:
        balances[pid] -= share
    balances[payer_id] += float(amount) - share

    st.session_state.guest_balances = [{"id": mid, "name": member_ids[mid], "balance": bal} for mid, bal in balances.items()]

# ---------- ABSTRACTED FUNCTIONS ----------
def fetch_members():
    return utils.fetch_members(supabase) if is_login_mode else guest_fetch_members()

def create_member(name):
    return utils.create_member(supabase, name) if is_login_mode else guest_create_member(name)

def fetch_history():
    return utils.fetch_history(supabase) if is_login_mode else guest_fetch_history()

def create_expense_with_transactions(payer_id, amount, title, description, participant_ids):
    if is_login_mode:
        return utils.create_expense_with_transactions(
            supabase,
            payer_id=payer_id,
            amount=Decimal(str(amount)),
            title=title,
            description=description,
            participant_ids=participant_ids
        )
    else:
        return guest_create_expense(payer_id, amount, title, description, participant_ids)

def compute_balances():
    return utils.compute_balances(supabase) if is_login_mode else guest_compute_balances()

# ---------- STYLE ----------
st.markdown("""
    <style>
        .main-title { font-size: 2.2rem; font-weight: bold; color: #4CAF50; }
        .sub-title { font-size: 1.4rem; margin-top: 20px; color: #333; }
        .stButton>button { background-color: #4CAF50; color: white; border-radius: 8px; padding: 8px 20px; font-size: 15px; }
        .dataframe { border-radius: 8px; }
        .metric-card { background-color: #f8f9fa; border-radius: 12px; padding: 15px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# ---------- HEADER ----------
st.markdown('<div class="main-title">💸 Splitwise — Office Edition</div>', unsafe_allow_html=True)
st.caption(f"Mode: **{st.session_state.mode}** — {'Connected to Supabase' if is_login_mode else 'Session Only'}")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.info("Thanks for Visiting.")

# ---------- MAIN TABS ----------
tab1, tab2, tab3, tab4 = st.tabs(["👥 Members", "➕ Add Expense", "📜 History", "📊 Balances"])

# ---------- MEMBERS ----------
with tab1:
    st.markdown('<div class="sub-title">👥 Manage Members</div>', unsafe_allow_html=True)
    with st.form('member_form', clear_on_submit=True):
        name = st.text_input('Member name', key='member_name')
        add = st.form_submit_button('Add Member')
        if add:
            if not name.strip():
                st.error('⚠️ Name required')
            else:
                u = create_member(name.strip())
                if u:
                    st.success(f"✅ Added {u['name']}")
    st.dataframe(fetch_members(), use_container_width=True)

# ---------- ADD EXPENSE ----------
with tab2:
    st.markdown('<div class="sub-title">➕ Add New Expense</div>', unsafe_allow_html=True)
    members_df = fetch_members()
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
                name2id = {r['name']: r['id'] for r in members_df.to_dict('records')}
                payer_id = name2id[payer]
                participant_ids = [name2id[p] for p in participants] or [payer_id]
                create_expense_with_transactions(
                    payer_id=payer_id,
                    amount=Decimal(str(amount)),
                    title=title or '',
                    description=description or '',
                    participant_ids=participant_ids
                )
                st.success('✅ Expense created')

# ---------- HISTORY ----------
with tab3:
    st.markdown('<div class="sub-title">📜 Expense History</div>', unsafe_allow_html=True)
    hist_df = fetch_history()
    if hist_df.empty:
        st.info('ℹ️ No expenses yet.')
    else:
        st.dataframe(hist_df, use_container_width=True)
        csv = hist_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            '📥 Download CSV',
            data=csv,
            file_name='history.csv',
            mime='text/csv'
        )

# ---------- BALANCES ----------
with tab4:
    st.markdown('<div class="sub-title">📊 Balances & Settlements</div>', unsafe_allow_html=True)
    bal_df = compute_balances()
    
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
                
                transfers.append({
                    'From': n['name'],
                    'To': p['name'],
                    'Amount (₹)': round(amt, 2)
                })
                
                p['balance'] -= amt
                n['balance'] += amt
                
                if abs(p['balance']) < 1e-9: i += 1
                if abs(n['balance']) < 1e-9: j += 1

            st.dataframe(pd.DataFrame(transfers), use_container_width=True)
