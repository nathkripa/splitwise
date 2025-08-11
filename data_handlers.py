# data_handlers.py

import streamlit as st
import pandas as pd
from decimal import Decimal
import uuid # To generate unique IDs for guest mode

# --- Database Handler (For Admin Mode) ---
class SupabaseDataHandler:
    def __init__(self, supabase_client, utils):
        self.supabase = supabase_client
        self.utils = utils
        st.success("✅ Connected to Database. You are in **Admin Mode**.")

    def fetch_members(self):
        return self.utils.fetch_members(self.supabase)

    def create_member(self, name):
        return self.utils.create_member(self.supabase, name)

    def fetch_history(self):
        return self.utils.fetch_history(self.supabase)
    
    def create_expense(self, payer_id, amount, title, description, participant_ids):
        return self.utils.create_expense_with_transactions(
            self.supabase, payer_id, amount, title, description, participant_ids
        )
    
    def compute_balances(self):
        return self.utils.compute_balances(self.supabase)

# --- Session State Handler (For Guest Mode) ---
class SessionStateDataHandler:
    def __init__(self, supabase_client, utils):
        st.info("ℹ️ You are in **Guest Mode**. All changes are temporary and will be lost on refresh.")
        if 'guest_data' not in st.session_state:
            # On first run, seed the guest session with real data from the DB
            members_df = utils.fetch_members(supabase_client)
            history_df = utils.fetch_history(supabase_client)
            st.session_state.guest_data = {
                'members': members_df.to_dict('records'),
                'history': history_df.to_dict('records')
            }

    def fetch_members(self):
        return pd.DataFrame(st.session_state.guest_data['members'])

    def create_member(self, name):
        new_member = {'id': str(uuid.uuid4()), 'name': name}
        st.session_state.guest_data['members'].append(new_member)
        return new_member

    def fetch_history(self):
        return pd.DataFrame(st.session_state.guest_data['history'])

    def create_expense(self, payer_id, amount, title, description, participant_ids):
        num_participants = len(participant_ids)
        if num_participants == 0: return None
        
        split_amount = amount / Decimal(num_participants)
        
        members_df = self.fetch_members()
        name_map = members_df.set_index('id')['name'].to_dict()

        payer_name = name_map.get(payer_id)
        participant_names = [name_map.get(pid) for pid in participant_ids]

        new_expense_id = str(uuid.uuid4())
        
        for participant_id in participant_ids:
            new_row = {
                'expense_id': new_expense_id,
                'title': title,
                'description': description,
                'amount': float(amount),
                'payer_name': payer_name,
                'participant_name': name_map.get(participant_id),
                'share_amount': float(round(split_amount, 2)),
                'created_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            st.session_state.guest_data['history'].append(new_row)
        return new_expense_id

    def compute_balances(self):
        history_df = self.fetch_history()
        if history_df.empty:
            return pd.DataFrame(columns=['id', 'name', 'balance'])

        balances = {}
        # Populate all members with zero balance first
        for member in st.session_state.guest_data['members']:
            balances[member['name']] = Decimal('0.0')

        for _, row in history_df.iterrows():
            payer = row['payer_name']
            participant = row['participant_name']
            share = Decimal(str(row['share_amount']))
            
            # Payer gets credited
            balances[payer] += share
            # Participant gets debited
            balances[participant] -= share
            
        bal_df = pd.DataFrame(list(balances.items()), columns=['name', 'balance'])
        
        # Merge with members df to get IDs
        members_df = self.fetch_members()
        bal_df = pd.merge(bal_df, members_df, on='name', how='left')
        
        return bal_df[['id', 'name', 'balance']]
