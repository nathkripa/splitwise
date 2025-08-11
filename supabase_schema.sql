-- Run this in Supabase SQL editor

create table if not exists members (
  id bigint generated always as identity primary key,
  name text not null unique
);

create table if not exists expenses (
  id bigint generated always as identity primary key,
  title text,
  payer_id bigint not null references members(id) on delete set null,
  amount numeric not null,
  description text,
  created_at timestamptz default now()
);

-- transactions: one row per person per expense indicating how much that person owes (positive means owes)
create table if not exists transactions (
  id bigint generated always as identity primary key,
  expense_id bigint not null references expenses(id) on delete cascade,
  member_id bigint not null references members(id) on delete cascade,
  amount numeric not null -- positive means this member owes this amount for that expense
);

create index if not exists idx_transactions_expense on transactions(expense_id);
create index if not exists idx_expenses_payer on expenses(payer_id);
