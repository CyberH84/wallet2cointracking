"""convert datetime columns to timestamptz

Revision ID: 20251001_make_timestamptz
Revises: 20251001_create_upsert_indexes
Create Date: 2025-10-01 00:00:00.000001
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251001_make_timestamptz'
down_revision = '20251001_create_upsert_indexes'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Convert columns in place to timestamptz (Postgres timestamptz)
    # Use USING to cast existing values to timestamptz assuming they are stored as UTC
    stmts = [
        "ALTER TABLE ethereum_transactions ALTER COLUMN block_time TYPE timestamptz USING block_time AT TIME ZONE 'UTC'",
        "ALTER TABLE ethereum_transactions ALTER COLUMN processed_at TYPE timestamptz USING processed_at AT TIME ZONE 'UTC'",
        "ALTER TABLE token_transfers ALTER COLUMN block_time TYPE timestamptz USING block_time AT TIME ZONE 'UTC'",
        "ALTER TABLE token_transfers ALTER COLUMN processed_at TYPE timestamptz USING processed_at AT TIME ZONE 'UTC'",
        "ALTER TABLE wallet_analysis ALTER COLUMN analysis_date TYPE timestamptz USING analysis_date AT TIME ZONE 'UTC'",
        "ALTER TABLE wallet_analysis ALTER COLUMN last_activity TYPE timestamptz USING last_activity AT TIME ZONE 'UTC'",
    ]
    for s in stmts:
        try:
            conn.execute(sa.text(s))
        except Exception:
            # Best-effort: continue if column already is timestamptz or conversion fails
            continue


def downgrade():
    conn = op.get_bind()
    stmts = [
        "ALTER TABLE ethereum_transactions ALTER COLUMN block_time TYPE timestamp WITHOUT TIME ZONE",
        "ALTER TABLE ethereum_transactions ALTER COLUMN processed_at TYPE timestamp WITHOUT TIME ZONE",
        "ALTER TABLE token_transfers ALTER COLUMN block_time TYPE timestamp WITHOUT TIME ZONE",
        "ALTER TABLE token_transfers ALTER COLUMN processed_at TYPE timestamp WITHOUT TIME ZONE",
        "ALTER TABLE wallet_analysis ALTER COLUMN analysis_date TYPE timestamp WITHOUT TIME ZONE",
        "ALTER TABLE wallet_analysis ALTER COLUMN last_activity TYPE timestamp WITHOUT TIME ZONE",
    ]
    for s in stmts:
        try:
            conn.execute(sa.text(s))
        except Exception:
            continue
