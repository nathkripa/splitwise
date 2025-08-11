import streamlit as st
import pandas as pd
from supabase import create_client, Client
from decimal import Decimal
import utils

# ---------- CONFIG ----------
st.set_page_config(page_title='🏢 Splitwise — Office Edition', page_icon='💸', layout='wide')

# ---------- STYLE ----------
st.markdown("""
    <style>
        .main-title {
            font-size: 2.2rem;
            font-weight: bold;
            color: #4CAF50;
        }
        .sub-title {
            font-size: 1.4rem;
            margin-top: 20px;
            color: #333;
        }
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            border-radius: 8px;
            padding: 8px 20px;
            font-size: 15px;
        }
        .dataframe {
            border-radius: 8px;
        }
        .metric-card {
            background-color: #f8f9fa;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }
    </style>
""", unsafe_allow_html=True)

# ---------- INIT SUPABASE ----------
# Initialize Supabase client from Streamlit secrets
SUPABASE_URL = st.secrets['url']
SUPABASE_ANON_KEY = st.secrets['key']
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error('Please add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets (or .streamlit/secrets.toml for local testing).')
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ---------- HEADER ----------
st.markdown('<div class="main-title">💸 Splitwise — Office Edition</div>', unsafe_allow_html=True)
st.caption("Easily manage and split expenses for your team. Powered by Streamlit + Supabase.")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("⚙️ Quick Actions")
    if st.button("🔄 Refresh Data"):
        st.experimental_rerun()
    st.markdown("---")
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
                u = utils.create_member(supabase, name.strip())
                if u:
                    st.success(f"✅ Added {u['name']}")
    members_df = utils.fetch_members(supabase)
    st.dataframe(members_df, use_container_width=True)

# ---------- ADD EXPENSE ----------
with tab2:
    st.markdown('<div class="sub-title">➕ Add New Expense</div>', unsafe_allow_html=True)
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
                name2id = {r['name']: r['id'] for r in (supabase.table('members').select('*').execute().data or [])}
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

# ---------- HISTORY ----------
with tab3:
    st.markdown('<div class="sub-title">📜 Expense History</div>', unsafe_allow_html=True)
    hist_df = utils.fetch_history(supabase)
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
# ---------- BALANCES ----------
with tab4:
    st.markdown('<div class="sub-title">📊 Balances & Settlements</div>', unsafe_allow_html=True)
    
    # Fetch history & members
    hist_df = utils.fetch_history(supabase)  # Should have columns: title, payer, participants, amount, etc.
    members_df = utils.fetch_members(supabase)
    members = members_df['name'].tolist()

    if hist_df.empty:
        st.info('ℹ️ No expenses yet.')
    else:
        # Create pivot-like table for each event
        event_balances = []
        for _, row in hist_df.iterrows():
            # Initialize dictionary with 0 for each member
            balances = {m: 0.0 for m in members}
            
            payer = row['payer']
            amount = row['share']
            participants = row['participants'].split(",") if 'participants' in row and row['participants'] else members

            # Per-person share
            share = round(amount / len(participants), 2)
            
            # Deduct share for each participant
            for p in participants:
                balances[p] -= share

            # Add total amount to payer
            balances[payer] += amount

            balances['Event'] = row['title']
            event_balances.append(balances)

        # Convert to DataFrame
        event_df = pd.DataFrame(event_balances)
        cols_order = ['Event'] + members
        event_df = event_df[cols_order]

        # Format as ₹
        for m in members:
            event_df[m] = event_df[m].apply(lambda x: f"₹{x:.2f}")

        st.markdown("### 🧾 Event-wise Balances")
        st.dataframe(event_df, use_container_width=True)

        # Overall balances
        st.markdown("### 📊 Total Balances")
        bal_df = utils.compute_balances(supabase)
        st.dataframe(bal_df, use_container_width=True)
