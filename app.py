import streamlit as st
import pandas as pd
from supabase import create_client, Client
from decimal import Decimal
import utils

st.set_page_config(page_title='Splitwise (Supabase)', layout='wide')
st.title('🏢 Splitwise — Streamlit + Supabase')

# Initialize Supabase client from Streamlit secrets
SUPABASE_URL = st.secrets.get('SUPABASE_URL')
SUPABASE_ANON_KEY = st.secrets.get('SUPABASE_ANON_KEY')
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error('Please add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets (or .streamlit/secrets.toml for local testing).')
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Layout
col1, col2 = st.columns([2, 1])

with col2:
    st.header('Admin / Quick actions')
    if st.button('Refresh data'):
        st.experimental_rerun()
    st.markdown('**Supabase URL**')
    st.code(SUPABASE_URL)
    st.markdown('---')
    st.write('Note: For production, enable RLS and use Supabase Auth.')

with col1:
    tab = st.tabs(['Members', 'Add Expense', 'History', 'Balances'])[0]

# Members
st.header('Members')
with st.form('member_form', clear_on_submit=True):
    name = st.text_input('Member name', key='member_name')
    add = st.form_submit_button('Add member')
    if add:
        if not name.strip():
            st.error('Name required')
        else:
            u = utils.create_member(supabase, name.strip())
            if u:
                st.success(f"Added {u['name']}")
members_df = utils.fetch_members(supabase)
st.dataframe(members_df)

st.markdown('---')

# Add Expense
st.header('Add Expense')
if members_df.empty:
    st.info('Add some members first.')
else:
    with st.form('expense_form', clear_on_submit=True):
        title = st.text_input('Title (e.g., Lunch with team)')
        payer = st.selectbox('Payer', options=members_df['name'].tolist())
        amount = st.number_input('Total amount (₹)', min_value=0.0, format='%.2f')
        participants = st.multiselect('Participants', options=members_df['name'].tolist(), default=members_df['name'].tolist())
        description = st.text_area('Description (optional)')
        submit = st.form_submit_button('Create expense')
        if submit:
            name2id = {r['name']: r['id'] for r in (supabase.table('members').select('*').execute().data or [])}
            payer_id = name2id[payer]
            participant_ids = [name2id[p] for p in participants] or [payer_id]
            expense_id = utils.create_expense_with_transactions(supabase, payer_id=payer_id, amount=Decimal(str(amount)), title=title or '', description=description or '', participant_ids=participant_ids)
            st.success('Expense created')

st.markdown('---')

# History
st.header('History (latest first)')
hist_df = utils.fetch_history(supabase)
if hist_df.empty:
    st.write('No expenses yet.')
else:
    st.dataframe(hist_df)
    csv = hist_df.to_csv(index=False).encode('utf-8')
    st.download_button('Download history CSV', data=csv, file_name='history.csv', mime='text/csv')

st.markdown('---')

# Balances
st.header('Balances & settlement suggestion')
bal_df = utils.compute_balances(supabase)
if bal_df.empty:
    st.write('No balances yet.')
else:
    st.table(bal_df)
    if st.button('Suggest minimal transfers'):
        pos = bal_df[bal_df.balance > 0][['name','balance']].to_dict('records')
        neg = bal_df[bal_df.balance < 0][['name','balance']].to_dict('records')
        pos = sorted(pos, key=lambda x: x['balance'], reverse=True)
        neg = sorted(neg, key=lambda x: x['balance'])
        i, j = 0, 0
        transfers = []
        while i < len(pos) and j < len(neg):
            p = pos[i]; n = neg[j]
            amt = min(p['balance'], -n['balance'])
            transfers.append({'from': n['name'], 'to': p['name'], 'amount': round(amt,2)})
            p['balance'] -= amt; n['balance'] += amt
            if abs(p['balance']) < 1e-9: i += 1
            if abs(n['balance']) < 1e-9: j += 1
        for t in transfers:
            st.write(f"{t['from']} → {t['to']}: ₹{t['amount']}")
