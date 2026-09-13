"""Consolidated current schema and migration-seeded reference data."""

from pathlib import Path

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql = (Path(__file__).resolve().parents[1] / "baseline.sql").read_text(encoding="utf-8")
    op.get_bind().exec_driver_sql(sql, execution_options={"no_parameters": True})


def downgrade() -> None:
    raise RuntimeError("Baseline downgrade would destroy the application schema; refused.")
