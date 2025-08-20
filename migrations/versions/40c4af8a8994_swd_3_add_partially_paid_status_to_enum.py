"""SWD-3 add partially paid status to enum

Revision ID: 40c4af8a8994
Revises: dcddb980291e
Create Date: 2025-08-20 11:08:58.955162

"""
from alembic import op

# revision identifiers…
revision = "40c4af8a8994"
down_revision = "dcddb980291e"

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # enum type name must match your model's Enum(name="orderstatus")
        op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'PARTIALLY_PAID';")
    else:
        # SQLite/MySQL local dev: nothing to do
        pass

def downgrade():
    # Postgres can't easily drop enum values; leave as no-op
    pass
