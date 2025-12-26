"""
This file exists so the rest of the backend has a consistent interface
when we later migrate from SQLite → Supabase Postgres.
"""

class SupabaseClientStub:
    def __init__(self):
        pass

    def upload_file(self, path: str):
        raise NotImplementedError("Supabase not enabled yet.")

supabase = SupabaseClientStub()