# app.py

import streamlit as st
import pandas as pd
from supabase import create_client, Client
from decimal import Decimal
import utils # Your original utils.py file
from data_handlers import SupabaseDataHandler, SessionStateDataHandler

# ---------- APP CONFIG ----------
st.set_page_config(page_title='🏢 Splitwise — Office Edition', page_icon='💸', layout='wide')

# ---------- STYLES (can be defined once) ----------
st.markdown("""
    <style>
        .main-title { font-size: 2.2rem; font-weight: bold; color: #4CAF50; }
        .sub-title { font-size: 1.4rem; margin-top: 20px; color: #333; }
        .stButton>button { background-color: #4CAF50; color: white; border-radius: 8px; padding: 8px 20px; font-size: 15px; }
    </style>
""", unsafe_allow_html=True)

# ---------- DATA & UI BUILDER ----------
def build_ui(handler):
    """Builds the main application UI using a given data handler."""
    
    # --- HEADER ---
    st.markdown('<div class="main-title">💸 Splitwise — Office Edition</div>', unsafe_allow_html=True)
    st.caption("Easily manage and split expenses for your team. Powered by Streamlit + Supabase.")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Quick Actions")
        if st.button("🔄 Refresh Data"):
            st.rerun()
        
        st.markdown("---")
        if st.button("⬅️ Switch Mode"):
            # Clear session state to go back to the mode selection screen
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()

    # --- TABS ---
    tab1, tab2, tab3, tab4 = st.tabs(["👥 Members", "➕ Add Expense", "📜 History", "📊 Balances"])
    
    # --- MEMBERS TAB ---
    with tab1:
        st.markdown('<div class="sub-title">👥 Manage Members</div>', unsafe_allow_html=True)
        with st.form('member_form', clear_on_submit=True):
            name = st.text_input('Member name')
            if st.form_submit_button('Add Member'):
                if not name.strip():
                    st.error('⚠️ Name required')
                else:
                    u = handler.create_member(name.strip())
                    st.success(f"✅ Added {u['name']}")
        
        members_df = handler.fetch_members()
        st.dataframe(members_df, use_container_width=True)
    
    # --- ADD EXPENSE TAB ---
    with tab2:
        st.markdown('<div class="sub-title">➕ Add New Expense</div>', unsafe_allow_html=True)
        members_df = handler.fetch_members()
        if members_df.empty:
            st.info('ℹ️ Add some members first.')
        else:
            with st.form('expense_form', clear_on_submit=True):
                col1, col2 = st.columns(2)
                title = col1.text_input('Title (e.g., Lunch with team)')
                amount = col2.number_input('Total amount (₹)', min_value=0.0, format='%.2f')
                
                name2id = {row['name']: row['id'] for index, row in members_df.iterrows()}
                id2name = {v: k for k, v in name2id.items()}

                payer_name = st.selectbox('Payer', options=members_df['name'].tolist())
                participant_names = st.multiselect('Participants', options=members_df['name'].tolist(), default=members_df['name'].tolist())
                description = st.text_area('Description (optional)')
                
                if st.form_submit_button('💾 Create Expense'):
                    payer_id = name2id.get(payer_name)
                    participant_ids = [name2id.get(p) for p in participant_names]
                    
                    if payer_id and all(participant_ids) and amount > 0:
                        handler.create_expense(
                            payer_id=payer_id, amount=Decimal(str(amount)),
                            title=title or 'Untitled Expense', description=description or '',
                            participant_ids=participant_ids
                        )
                        st.success('✅ Expense created')
                    else:
                        st.error("Invalid input. Ensure amount is > 0 and all participants are selected.")

    # --- HISTORY TAB ---
    with tab3:
        st.markdown('<div class="sub-title">📜 Expense History</div>', unsafe_allow_html=True)
        hist_df = handler.fetch_history()
        if hist_df.empty:
            st.info('ℹ️ No expenses yet.')
        else:
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
            csv = hist_df.to_csv(index=False).encode('utf-8')
            st.download_button('📥 Download CSV', data=csv, file_name='history.csv')

    # --- BALANCES TAB ---
    with tab4:
        st.markdown('<div class="sub-title">📊 Balances & Settlements</div>', unsafe_allow_html=True)
        bal_df = handler.compute_balances()
        
        if bal_df.empty or bal_df['balance'].abs().sum() < 0.01:
            st.info('ℹ️ No balances to display.')
        else:
            # Show balance table
            st.markdown("### Current Balances")
            bal_table = bal_df.copy()
            bal_table['Balance (₹)'] = bal_table['balance'].apply(lambda x: f"₹{Decimal(x):.2f}")
            st.dataframe(bal_table[['name', 'Balance (₹)']], use_container_width=True, hide_index=True)

            # Settlement suggestion
            st.markdown("### 💱 Suggested Settlements")
            pos = bal_df[bal_df.balance > 0.01].to_dict('records')
            neg = bal_df[bal_df.balance < -0.01].to_dict('records')

            if not pos or not neg:
                st.info("✅ All balances are settled!")
            else:
                transfers = []
                # ... (Settlement logic remains the same)
                i, j = 0, 0
                while i < len(pos) and j < len(neg):
                    p, n = pos[i], neg[j]
                    p_bal, n_bal = Decimal(str(p['balance'])), Decimal(str(n['balance']))
                    amt = min(p_bal, -n_bal)
                    transfers.append({'From': n['name'], 'To': p['name'], 'Amount (₹)': f"{amt:.2f}"})
                    pos[i]['balance'] -= amt
                    neg[j]['balance'] += amt
                    if pos[i]['balance'] < Decimal('0.01'): i += 1
                    if abs(neg[j]['balance']) < Decimal('0.01'): j += 1
                
                st.dataframe(pd.DataFrame(transfers), use_container_width=True, hide_index=True)


# ---------- MODE SELECTION & LOGIN LOGIC ----------
def mode_selection():
    st.header("Welcome to Splitwise — Office Edition")
    st.write("Choose how you want to use the app:")
    
    col1, col2 = st.columns(2)
    if col1.button("🔑 Login as Admin (Permanent Storage)", use_container_width=True):
        st.session_state.mode = 'admin'
        st.rerun()
        
    if col2.button("👤 Continue as Guest (Temporary Session)", use_container_width=True):
        st.session_state.mode = 'guest'
        st.rerun()

def login_page():
    st.header("Admin Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login", type="primary"):
        if username == st.secrets['app_username'] and password == st.secrets['app_password']:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("😕 Incorrect username or password.")
    
    if st.button("⬅️ Back to mode selection"):
        del st.session_state.mode
        st.rerun()


# ---------- SCRIPT EXECUTION ----------
if 'mode' not in st.session_state:
    mode_selection()
elif st.session_state.mode == 'admin':
    if st.session_state.get('authenticated', False):
        supabase: Client = create_client(st.secrets['url'], st.secrets['key'])
        handler = SupabaseDataHandler(supabase, utils)
        build_ui(handler)
    else:
        login_page()
elif st.session_state.mode == 'guest':
    supabase: Client = create_client(st.secrets['url'], st.secrets['key'])
    handler = SessionStateDataHandler(supabase, utils)
    build_ui(handler)
