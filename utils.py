import streamlit as st
import pandas as pd
import datetime
from decimal import Decimal
from typing import List, Optional
from supabase import Client

# ---------- Guest Mode Initialization ----------
def init_guest_data():
    st.session_state.setdefault("guest_members", [])
    st.session_state.setdefault("guest_expenses", [])
    st.session_state.setdefault("guest_transactions", [])

# ---------- Internal Data Access Layer ----------
def _get_members(supabase: Optional[Client]):
    if supabase is None:
        init_guest_data()
        return st.session_state.guest_members
    return supabase.table('members').select('*').execute().data or []

def _get_expenses(supabase: Optional[Client]):
    if supabase is None:
        init_guest_data()
        return st.session_state.guest_expenses
    return supabase.table('expenses').select('*').execute().data or []

def _get_transactions(supabase: Optional[Client]):
    if supabase is None:
        init_guest_data()
        return st.session_state.guest_transactions
    return supabase.table('transactions').select('*').execute().data or []

# ---------- Member Operations ----------
def fetch_members(supabase: Optional[Client]) -> pd.DataFrame:
    return pd.DataFrame(_get_members(supabase))

def create_member(supabase: Optional[Client], name: str):
    name = name.strip()
    if not name:
        return None

    if supabase is None:
        members = _get_members(None)
        existing = [m for m in members if m['name'].lower() == name.lower()]
        if existing:
            return existing[0]
        new_id = max((m['id'] for m in members), default=0) + 1
        new_member = {'id': new_id, 'name': name}
        st.session_state.guest_members.append(new_member)
        return new_member
    else:
        existing = supabase.table('members').select('*').eq('name', name).execute().data or []
        if existing:
            return existing[0]
        resp = supabase.table('members').insert({'name': name}).execute()
        return resp.data[0]

# ---------- Expense Operations ----------
def _split_amount(amount: Decimal, participant_ids: List[int]):
    n = len(participant_ids) if participant_ids else 1
    base = round(float(amount) / n, 2)
    shares = [base] * n
    shares[-1] = round(float(amount) - base * (n - 1), 2)
    return shares

def create_expense_with_transactions(
    supabase: Optional[Client],
    payer_id: int,
    amount: Decimal,
    title: str,
    description: str,
    participant_ids: List[int]
):
    shares = _split_amount(amount, participant_ids)

    if supabase is None:
        expenses = _get_expenses(None)
        new_expense_id = max((e['id'] for e in expenses), default=0) + 1
        st.session_state.guest_expenses.append({
            'id': new_expense_id,
            'payer_id': payer_id,
            'amount': float(amount),
            'description': description,
            'created_at': datetime.datetime.now().isoformat(),
            'title': title,
        })
        st.session_state.guest_transactions.extend([
            {'expense_id': new_expense_id, 'member_id': mid, 'amount': share}
            for mid, share in zip(participant_ids, shares)
        ])
        return new_expense_id

    else:
        resp = supabase.table('expenses').insert({
            'payer_id': payer_id,
            'amount': float(amount),
            'description': description,
            'title': title
        }).execute()
        if not resp.data:
            raise RuntimeError('Failed to create expense')
        expense_id = resp.data[0]['id']
        rows = [{'expense_id': expense_id, 'member_id': mid, 'amount': share}
                for mid, share in zip(participant_ids, shares)]
        supabase.table('transactions').insert(rows).execute()
        return expense_id

# ---------- History ----------
def fetch_history(supabase: Optional[Client]) -> pd.DataFrame:
    members = {m['id']: m['name'] for m in _get_members(supabase)}
    expenses = _get_expenses(supabase)
    transactions = _get_transactions(supabase)

    rows = []
    for e in expenses:
        e_trans = [t for t in transactions if t['expense_id'] == e['id']]
        for t in e_trans:
            rows.append({
                'expense_id': e['id'],
                'date': e.get('created_at'),
                'title': e.get('title'),
                'payer': members.get(e.get('payer_id')),
                'member': members.get(t.get('member_id')),
                'share': t.get('amount'),
                'total_amount': e.get('amount'),
                'description': e.get('description')
            })

    if not rows:
        return pd.DataFrame(columns=[
            'expense_id', 'date', 'title', 'payer', 'member', 'share', 'total_amount', 'description'
        ])
    return pd.DataFrame(rows)

# ---------- Balances ----------
def compute_balances(supabase: Optional[Client]) -> pd.DataFrame:
    members = _get_members(supabase)
    expenses = _get_expenses(supabase)
    transactions = _get_transactions(supabase)

    balances = {m['id']: 0.0 for m in members}
    for e in expenses:
        balances[e['payer_id']] += float(e['amount'])
    for t in transactions:
        balances[t['member_id']] -= float(t['amount'])

    return pd.DataFrame([
        {
            'member_id': mid,
            'name': next((m['name'] for m in members if m['id'] == mid), 'n/a'),
            'balance': round(bal, 2)
        }
        for mid, bal in balances.items()
    ]).reset_index(drop=True)
