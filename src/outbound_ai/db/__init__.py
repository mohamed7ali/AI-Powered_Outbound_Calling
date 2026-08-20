"""Supabase/PostgreSQL access boundary."""

from outbound_ai.db.connection import Database, TenantContext, get_database

__all__ = ["Database", "TenantContext", "get_database"]
