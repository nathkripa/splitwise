from supabase import Client
import pandas as pd
from decimal import Decimal
from typing import List, Dict

def fetch_members(supabase: Client) -> pd.DataFrame:
    resp = supabase.table('members').select('*').execute()
    data = resp.data or []
    return pd.DataFrame(data)

def create_member(supabase: Client, name: str):
    name = name.strip()
    if not name:
        return None
    existing = supabase.table('members').select('*').eq('name', name).execute().data or []
    if existing:
        return existing[0]
    resp = supabase.table('members').insert({'name': name}).execute()
    return resp.data[0]

def create_expense_with_transactions(supabase: Client, payer_id: int, amount: Decimal, title: str, description: str, participant_ids: List[int]):
    # Insert expense
    resp = supabase.table('expenses').insert({
        'payer_id': payer_id,
        'amount': float(amount),
        'description': description
    }).execute()
    if not resp.data:
        raise RuntimeError('failed to create expense')
    expense_id = resp.data[0]['id']

    # create transactions: split equally among participants
    n = len(participant_ids) if participant_ids else 1
    base = round(float(amount) / n, 2)
    rows = []
    for i, mid in enumerate(participant_ids):
        share = base
        if i == n - 1:
            # adjust last share to match total
            share = round(float(amount) - base*(n-1), 2)
        rows.append({'expense_id': expense_id, 'member_id': mid, 'amount': share})
    supabase.table('transactions').insert(rows).execute()
    return expense_id

def fetch_history(supabase: Client):
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

def compute_balances(supabase: Client):
    members = supabase.table('members').select('*').execute().data or []
    expenses = supabase.table('expenses').select('*').execute().data or []
    transactions = supabase.table('transactions').select('*').execute().data or []
    balances = {m['id']: 0.0 for m in members}
    # payer gets +amount, each participant gets -share
    for e in expenses:
        pid = e['payer_id']
        amt = float(e['amount'])
        balances[pid] = balances.get(pid, 0.0) + amt
    for t in transactions:
        mid = t['member_id']
        balances[mid] = balances.get(mid, 0.0) - float(t['amount'])

    id2name = {m['id']: m['name'] for m in members}
    rows = []
    for mid, bal in balances.items():
        rows.append({'member_id': mid, 'name': id2name.get(mid,'n/a'), 'balance': round(bal,2)})
    import pandas as pd
    return pd.DataFrame(rows).reset_index(drop=True)
