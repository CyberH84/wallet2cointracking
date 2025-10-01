"""convert datetime columns to timestamptz (strict)

Revision ID: 20251001_make_timestamptz_strict
Revises: 20251001_make_timestamptz
Create Date: 2025-10-01 00:00:10.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251001_make_timestamptz_strict'
down_revision = '20251001_make_timestamptz'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    stmts = [
        "ALTER TABLE ethereum_transactions ALTER COLUMN block_time TYPE timestamptz USING block_time AT TIME ZONE 'UTC'",
        "ALTER TABLE ethereum_transactions ALTER COLUMN processed_at TYPE timestamptz USING processed_at AT TIME ZONE 'UTC'",
        "ALTER TABLE token_transfers ALTER COLUMN block_time TYPE timestamptz USING block_time AT TIME ZONE 'UTC'",
        "ALTER TABLE token_transfers ALTER COLUMN processed_at TYPE timestamptz USING processed_at AT TIME ZONE 'UTC'",
        "ALTER TABLE wallet_analysis ALTER COLUMN analysis_date TYPE timestamptz USING analysis_date AT TIME ZONE 'UTC'",
        "ALTER TABLE wallet_analysis ALTER COLUMN last_activity TYPE timestamptz USING last_activity AT TIME ZONE 'UTC'",
    ]
    for s in stmts:
        # Execute and allow exceptions to bubble up (fail-fast in production)
        conn.execute(sa.text(s))


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
        conn.execute(sa.text(s))
