"""PostgreSQL connection and transaction context for Supabase.

The application uses direct PostgreSQL for repositories and pgvector queries. Each
user-facing transaction must set the actor and organization context before running
queries. System/provider callbacks should use a separate trusted path explicitly.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator
from uuid import UUID

from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from outbound_ai.config.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class TenantContext:
    """The authenticated principal and active organization for one request."""

    actor_id: UUID
    organization_id: UUID | None = None
    actor_role: str | None = None


class Database:
    """Small synchronous pool wrapper with transaction-local RLS context."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.database_url is None:
            raise ValueError("DATABASE_URL is required for database access")
        self.pool = ConnectionPool(
            conninfo=self.settings.database_url.get_secret_value(),
            min_size=self.settings.db_pool_min_size,
            max_size=self.settings.db_pool_max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    def open(self) -> None:
        self.pool.open()

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def transaction(
        self,
        context: TenantContext,
        *,
        enforce_rls: bool = True,
    ) -> Iterator[Connection]:
        """Yield a transaction with actor and organization context set locally.

        ``set_config(..., true)`` makes the values transaction-local. They cannot
        leak to the next pooled request. ``enforce_rls`` switches the connection
        into Supabase's authenticated role when the connection user is allowed to
        assume it. Trusted system callbacks should be isolated and explicit rather
        than silently using this user-facing method.
        """

        with self.pool.connection() as connection:
            with connection.transaction():
                if enforce_rls:
                    if self.settings.db_rls_role != "authenticated":
                        raise ValueError("DB_RLS_ROLE must remain authenticated for user transactions")
                    connection.execute(
                        sql.SQL("set local role {}")
                        .format(sql.Identifier(self.settings.db_rls_role))
                    )
                connection.execute(
                    "select set_config('app.current_user_id', %s, true)",
                    (str(context.actor_id),),
                )
                if context.organization_id is not None:
                    connection.execute(
                        "select set_config('app.current_org_id', %s, true)",
                        (str(context.organization_id),),
                    )
                yield connection

    @contextmanager
    def trusted_transaction(self) -> Iterator[Connection]:
        """Yield a privileged transaction for verified provider callbacks only.

        The caller must validate the Twilio signature before using this path and
        must still resolve the internal call row and organization from the provider
        call ID. Never expose this connection to a browser or ordinary user query.
        """

        with self.pool.connection() as connection:
            with connection.transaction():
                yield connection


_default_database: Database | None = None


def get_database() -> Database:
    """Return the process-level database pool, opened on first use."""

    global _default_database
    if _default_database is None:
        _default_database = Database()
        _default_database.open()
    return _default_database
