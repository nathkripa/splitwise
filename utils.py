import streamlit as st
import pandas as pd
from decimal import Decimal
from typing import List, Optional
import datetime
from supabase import Client

# --- Guest-mode data initialization ---
def init_guest_data():
    if "guest_members" not in st.session_state:
        st.session_state.guest_members = []  # list of dicts {id:int, name:str}
    if "guest_expenses" not in st.session_state:
        st.session_state.guest_expenses = []  # list of dicts {id:int, payer_id:int, amount:float, description:str, created_at:str, title:str}
    if "guest_transactions" not in st.session_state:
        st.session_state.guest_transactions = []  # list of dicts {expense_id:int, member_id:int, amount:float}

# --------- Guest mode implementations ---------
def fetch_members_guest() -> pd.DataFrame:
    init_guest_data()
    return pd.DataFrame(st.session_state.guest_members)

def create_member_guest(name: str):
    init_guest_data()
    name = name.strip()
    if not name:
        return None
    existing = [m for m in st.session_state.guest_members if m['name'].lower() == name.lower()]
    if existing:
        return existing[0]
    new_id = max([m['id'] for m in st.session_state.guest_members], default=0) + 1
    new_member = {'id': new_id, 'name': name}
    st.session_state.guest_members.append(new_member)
    return new_member

def create_expense_with_transactions_guest(
    payer_id: int,
    amount: Decimal,
    title: str,
    description: str,
    participant_ids: List[int]
):
    init_guest_data()
    new_expense_id = max([e['id'] for e in st.session_state.guest_expenses], default=0) + 1
    new_expense = {
        'id': new_expense_id,
        'payer_id': payer_id,
        'amount': float(amount),
        'description': description,
        'created_at': datetime.datetime.now().isoformat(),
        'title': title,
    }
    st.session_state.guest_expenses.append(new_expense)

    n = len(participant_ids) if participant_ids else 1
    base = round(float(amount) / n, 2)
    rows = []
    for i, mid in enumerate(participant_ids):
        share = base
        if i == n - 1:
            share = round(float(amount) - base*(n-1), 2)
        rows.append({'expense_id': new_expense_id, 'member_id': mid, 'amount': share})
    st.session_state.guest_transactions.extend(rows)
    return new_expense_id

def fetch_history_guest() -> pd.DataFrame:
    init_guest_data()
    members = {m['id']: m['name'] for m in st.session_state.guest_members}
    rows = []
    for e in st.session_state.guest_expenses:
        e_id = e['id']
        e_trans = [t for t in st.session_state.guest_transactions if t['expense_id'] == e_id]
        for t in e_trans:
            rows.append({
                'expense_id': e_id,
                'date': e.get('created_at'),
                'title': e.get('title'),
                'payer': members.get(e.get('payer_id')),
                'member': members.get(t.get('member_id')),
                'share': t.get('amount'),
                'total_amount': e.get('amount'),
                'description': e.get('description')
            })
    if not rows:
        return pd.DataFrame(columns=['expense_id','date','title','payer','member','share','total_amount','description'])
    return pd.DataFrame(rows)

def compute_balances_guest() -> pd.DataFrame:
    init_guest_data()
    members = st.session_state.guest_members
    expenses = st.session_state.guest_expenses
    transactions = st.session_state.guest_transactions

    balances = {m['id']: 0.0 for m in members}
    for e in expenses:
        pid = e['payer_id']
        amt = float(e['amount'])
        balances[pid] = balances.get(pid, 0.0) + amt
    for t in transactions:
        mid = t['member_id']
        balances[mid] = balances.get(mid, 0.0) - float(t['amount'])

    id2name = {m['id']: m['name'] for m in members}
    rows = [{'member_id': mid, 'name': id2name.get(mid,'n/a'), 'balance': round(bal, 2)} for mid, bal in balances.items()]
    return pd.DataFrame(rows).reset_index(drop=True)

# --------- Login mode implementations ---------
def fetch_members_login(supabase: Client) -> pd.DataFrame:
    resp = supabase.table('members').select('*').execute()
    data = resp.data or []
    return pd.DataFrame(data)

def create_member_login(supabase: Client, name: str):
    name = name.strip()
    if not name:
        return None
    existing = supabase.table('members').select('*').eq('name', name).execute().data or []
    if existing:
        return existing[0]
    resp = supabase.table('members').insert({'name': name}).execute()
    return resp.data[0]

def create_expense_with_transactions_login(supabase: Client, payer_id: int, amount: Decimal, title: str, description: str, participant_ids: List[int]):
    resp = supabase.table('expenses').insert({
        'payer_id': payer_id,
        'amount': float(amount),
        'description': description,
        'title': title
    }).execute()
    if not resp.data:
        raise RuntimeError('failed to create expense')
    expense_id = resp.data[0]['id']

    n = len(participant_ids) if participant_ids else 1
    base = round(float(amount) / n, 2)
    rows = []
    for i, mid in enumerate(participant_ids):
        share = base
        if i == n - 1:
            share = round(float(amount) - base*(n-1), 2)
        rows.append({'expense_id': expense_id, 'member_id': mid, 'amount': share})
    supabase.table('transactions').insert(rows).execute()
    return expense_id

def fetch_history_login(supabase: Client):
    expenses = supabase.table('expenses').select('*').execute().data or []
    transactions = supabase.table('transactions').select('*').execute().data or []
    members = {m['id']: m['name'] for m in (supabase.table('members').select('*').execute().data or [])}
    rows = []
    for e in expenses:
        e_id = e['id']
        e_trans = [t for t in transactions if t['expense_id'] == e_id]
        for t in e_trans:
            rows.append({
                'expense_id': e_id,
                'date': e.get('created_at'),
                'title': e.get('title'),
                'payer': members.get(e.get('payer_id')),
                'member': members.get(t.get('member_id')),
                'share': t.get('amount'),
                'total_amount': e.get('amount'),
                'description': e.get('description')
            })
    if not rows:
        return pd.DataFrame(columns=['expense_id','date','title','payer','member','share','total_amount','description'])
    return pd.DataFrame(rows)

def compute_balances_login(supabase: Client):
    members = supabase.table('members').select('*').execute().data or []
    expenses = supabase.table('expenses').select('*').execute().data or []
    transactions = supabase.table('transactions').select('*').execute().data or []
    balances = {m['id']: 0.0 for m in members}
    for e in expenses:
        pid = e['payer_id']
        amt = float(e['amount'])
        balances[pid] = balances.get(pid, 0.0) + amt
    for t in transactions:
        mid = t['member_id']
        balances[mid] = balances.get(mid, 0.0) - float(t['amount'])

    id2name = {m['id']: m['name'] for m in members}
    rows = [{'member_id': mid, 'name': id2name.get(mid,'n/a'), 'balance': round(bal, 2)} for mid, bal in balances.items()]
    return pd.DataFrame(rows).reset_index(drop=True)

# --------- Dispatcher functions ---------
def fetch_members(supabase: Optional[Client]):
    if supabase is None:
        return fetch_members_guest()
    return fetch_members_login(supabase)

def create_member(supabase: Optional[Client], name: str):
    if supabase is None:
        return create_member_guest(name)
    return create_member_login(supabase, name)

def create_expense_with_transactions(supabase: Optional[Client], payer_id: int, amount: Decimal, title: str, description: str, participant_ids: List[int]):
    if supabase is None:
        return create_expense_with_transactions_guest(payer_id, amount, title, description, participant_ids)
    return create_expense_with_transactions_login(supabase, payer_id, amount, title, description, participant_ids)

def fetch_history(supabase: Optional[Client]):
    if supabase is None:
        return fetch_history_guest()
    return fetch_history_login(supabase)

def compute_balances(supabase: Optional[Client]):
    if supabase is None:
        return compute_balances_guest()
    return compute_balances_login(supabase)
