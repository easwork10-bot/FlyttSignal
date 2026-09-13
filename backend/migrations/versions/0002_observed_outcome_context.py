"""Keep observed lifecycle context independently of replaceable rental inference."""

from alembic import op
import sqlalchemy as sa

revision = "0002_observed_outcome_context"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("signal_outcomes_signal_id_fkey", "signal_outcomes", type_="foreignkey")
    op.alter_column("signal_outcomes", "signal_id", nullable=True)
    op.create_foreign_key(
        "signal_outcomes_signal_id_fkey",
        "signal_outcomes",
        "signals",
        ["signal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for table in ("rental_listings", "events"):
        op.add_column(
            table,
            sa.Column("is_historical", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    op.drop_constraint(
        "rental_listings_source_id_source_item_id_key", "rental_listings", type_="unique"
    )
    op.drop_constraint("events_raw_item_id_event_type_key", "events", type_="unique")
    op.create_index(
        "uq_current_rental_listing_source_item",
        "rental_listings",
        ["source_id", "source_item_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_historical"),
    )
    op.create_index(
        "uq_current_event_raw_type",
        "events",
        ["raw_item_id", "event_type"],
        unique=True,
        postgresql_where=sa.text("NOT is_historical"),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Cannot discard retained outcome context or restore mandatory deleted signal links."
    )
