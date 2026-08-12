"""Initial schema.

This migration is intentionally conservative for MVP usage:
- creates the `vector` extension if needed
- creates the core tables used by the application
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="users_organization_id_fkey"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="documents_organization_id_fkey"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name="documents_uploaded_by_fkey"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="chunks_document_id_fkey"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="chunks_organization_id_fkey"),
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True, server_default=sa.text("'Nouvelle conversation'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="conversations_organization_id_fkey",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="conversations_user_id_fkey"),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name="messages_conversation_id_fkey"),
    )

    op.create_table(
        "exercises",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("exercise_type", sa.String(length=50), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="exercises_organization_id_fkey",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="exercises_document_id_fkey"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="exercises_created_by_fkey"),
    )

    op.create_table(
        "attempts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("weak_topics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="attempts_organization_id_fkey",
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], name="attempts_exercise_id_fkey"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="attempts_user_id_fkey"),
    )


def downgrade() -> None:
    # Keep downgrade empty for MVP simplicity. Production should manage reversibility.
    pass

