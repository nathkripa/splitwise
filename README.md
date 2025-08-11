# Splitwise — Streamlit + Supabase

This is a deployable, GitHub-ready Streamlit app that functions like a lightweight Splitwise for office teams.
It stores data in **Supabase** (Postgres) and is ready to deploy on **Streamlit Community Cloud**.

## What it includes
- Add members
- Add expenses (payer, participants, amount, description, date)
- Auto-split equally among participants
- Transaction history & CSV export
- Per-member balances & settlement suggestions
- Uses Supabase for persistent storage

## Quick steps to deploy (3–7 minutes)
1. Create a free Supabase project at https://supabase.com and open the SQL editor.
2. Run the SQL in `supabase_schema.sql` (provided) to create required tables (`members`, `expenses`, `transactions`).
3. Create a GitHub repo and push this project, or upload the files directly to GitHub.
4. In Streamlit Cloud, create a new app from this repo and set the app file to `app.py`.
5. Add secrets (Settings → Secrets) in Streamlit Cloud:
   ```toml
   SUPABASE_URL = "https://<your-project>.supabase.co"
   SUPABASE_ANON_KEY = "<your-anon-key>"
   ```
6. Deploy. The app will read/write directly to Supabase.

## Security notes
- The app uses the Supabase **anon key** for simplicity. For internal office use this is OK, but for production consider enabling RLS and using authenticated requests or server-side functions.
- If you want, I can update the app to use Supabase Auth (magic link) so only team members can use it.

## Files in this repo
- `app.py` — Streamlit frontend + Supabase integration
- `utils.py` — helper functions (DB wrappers, balance calc)
- `requirements.txt`
- `supabase_schema.sql` — SQL to create required tables (paste into Supabase SQL editor)
- `.streamlit/secrets.toml.example` — example secrets file for local testing
