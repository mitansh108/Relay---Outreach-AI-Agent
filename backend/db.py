"""Request-scoped persistence. All product queries are workspace constrained."""
import os
from pathlib import Path

from fastapi import HTTPException, Request
from sqlalchemy import String, create_engine, event, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker, with_loader_criteria


class Base(DeclarativeBase):
    pass


class WorkspaceOwned:
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True, default="demo")


class WorkspaceSession(Session):
    def get(self, entity, ident, **kwargs):
        # Query instead of an identity-map lookup: enforce ownership even for IDs.
        if issubclass(entity, WorkspaceOwned):
            keys = [c.key for c in inspect(entity).primary_key if c.key != "workspace_id"]
            if len(keys) != 1 or not isinstance(ident, str):
                raise ValueError("Use the resource ID for workspace-scoped lookups")
            return self.scalar(select(entity).where(getattr(entity, keys[0]) == ident))
        return super().get(entity, ident, **kwargs)


@event.listens_for(WorkspaceSession, "do_orm_execute")
def scope_queries(state):
    workspace = state.session.info.get("workspace_id")
    if not workspace:
        raise RuntimeError("Workspace session requires a workspace")
    if state.is_select:
        state.statement = state.statement.options(with_loader_criteria(
            WorkspaceOwned, lambda cls: cls.workspace_id == workspace, include_aliases=True))
    elif state.is_delete or state.is_update:
        model = state.bind_mapper.class_ if state.bind_mapper else None
        if model and issubclass(model, WorkspaceOwned):
            state.statement = state.statement.where(model.workspace_id == workspace)
        else:
            raise RuntimeError("Unscoped bulk mutation is forbidden")


@event.listens_for(WorkspaceSession, "before_flush")
def scope_writes(db, *_):
    workspace = db.info["workspace_id"]
    for row in db.new:
        if isinstance(row, WorkspaceOwned):
            if row.workspace_id not in (None, workspace):
                raise HTTPException(403, "Record belongs to another workspace")
            row.workspace_id = workspace
    for row in db.dirty | db.deleted:
        if isinstance(row, WorkspaceOwned) and (row.workspace_id != workspace or inspect(row).attrs.workspace_id.history.has_changes()):
            raise HTTPException(403, "Record belongs to another workspace")
    # IDs alone must never allow cross-workspace relationships.
    for row in db.new | db.dirty:
        if not isinstance(row, WorkspaceOwned):
            continue
        for column in row.__table__.columns:
            for foreign_key in column.foreign_keys:
                value = getattr(row, column.key)
                if not value:
                    continue
                target = next((m.class_ for m in Base.registry.mappers if m.local_table is foreign_key.column.table), None)
                if target and issubclass(target, WorkspaceOwned):
                    pending = any(isinstance(r, target) and getattr(r, foreign_key.column.key) == value and r.workspace_id == workspace for r in db.new)
                    if not pending:
                        with db.no_autoflush:
                            if db.get(target, value) is None:
                                raise HTTPException(403, "Related record is outside this workspace")


default_db = Path(__file__).resolve().parent / "copilot_workspace.db"
DATABASE_URL = os.getenv("COPILOT_DATABASE_URL", f"sqlite:///{default_db}")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {"options": "-csearch_path=relay"})
SessionLocal = sessionmaker(bind=engine, class_=WorkspaceSession, expire_on_commit=False)


def get_db(request: Request):
    from .auth import identity, supabase_enabled
    from .models import Membership, OAuthPending
    user = None
    workspace = "demo"
    if supabase_enabled():
        # Callback identity is the unguessable, expiring OAuth state created by
        # an authenticated member. It is consumed atomically by exchange_code.
        if request.url.path in {"/api/oauth/gmail/callback", "/api/oauth/hubspot/callback"}:
            with Session(engine, info={"oauth_state": request.query_params.get("state", "")}) as lookup:
                pending = lookup.get(OAuthPending, request.query_params.get("state", ""))
                if not pending:
                    raise HTTPException(400, "OAuth state is invalid or expired")
                workspace = pending.workspace_id
                user = pending.user_id
                lookup.info.update(user_id=user, workspace_id=workspace)
                configure_context(lookup.connection(), lookup.info)
                if not lookup.get(Membership, (workspace, user)):
                    raise HTTPException(403, "Workspace access has been removed")
        else:
            user = identity(request)["id"]
            workspace = request.headers.get("X-Workspace-ID", "")
            with Session(engine, info={"user_id": user}) as lookup:
                if not workspace or not lookup.get(Membership, (workspace, user)):
                    raise HTTPException(403, "Select a workspace you belong to")
    with SessionLocal(info={"workspace_id": workspace, "user_id": user}) as db:
        yield db


def configure_context(connection, info):
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('app.user_id', :user, true), set_config('app.workspace_id', :workspace, true), set_config('app.oauth_state', :state, true)"),
            {"user": info.get("user_id") or "", "workspace": info.get("workspace_id") or "", "state": info.get("oauth_state") or ""})


@event.listens_for(Session, "after_begin")
def transaction_context(db, transaction, connection):
    # Transaction-local settings cannot leak through a pooled connection.
    configure_context(connection, db.info)
