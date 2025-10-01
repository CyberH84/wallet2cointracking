"""create upsert indexes

Revision ID: 20251001_create_upsert_indexes
Revises: 
Create Date: 2025-10-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251001_create_upsert_indexes'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create unique indexes required for application upsert paths
    # Use IF NOT EXISTS to make this migration safe to run even if indexes were created defensively at runtime
    conn = op.get_bind()
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ux_ethereum_transactions_tx_hash ON ethereum_transactions (tx_hash)"))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ux_token_transfers_tx_hash_log_index ON token_transfers (tx_hash, log_index)"))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ux_wallet_analysis_wallet_chain ON wallet_analysis (wallet_address, chain_id)"))

def downgrade():
    op.drop_index('ux_wallet_analysis_wallet_chain', table_name='wallet_analysis')
    op.drop_index('ux_token_transfers_tx_hash_log_index', table_name='token_transfers')
    op.drop_index('ux_ethereum_transactions_tx_hash', table_name='ethereum_transactions')
