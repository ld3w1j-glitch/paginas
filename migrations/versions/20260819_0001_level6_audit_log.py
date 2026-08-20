"""Level 6: audit log bootstrap compatível com bancos existentes."""
from alembic import op
import sqlalchemy as sa

revision = "20260819_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLE = "curso_audit_log"


def _exists() -> bool:
    bind = op.get_bind()
    return TABLE in sa.inspect(bind).get_table_names()


def upgrade():
    if _exists():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("ip_address", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["curso_user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_curso_audit_log_user_id", TABLE, ["user_id"])
    op.create_index("ix_curso_audit_log_action", TABLE, ["action"])
    op.create_index("ix_curso_audit_log_created_at", TABLE, ["created_at"])


def downgrade():
    if _exists():
        op.drop_table(TABLE)
