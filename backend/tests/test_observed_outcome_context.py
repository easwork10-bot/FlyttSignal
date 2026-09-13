"""Historical observations survive replacement of their inferred signals."""

from sqlalchemy import create_engine, inspect

from flyttsignal.db.models import Event, RentalListing, Signal, SignalOutcome


def test_outcome_signal_link_is_optional_and_never_cascades_outcomes():
    column = SignalOutcome.__table__.c.signal_id
    assert column.nullable
    assert next(iter(column.foreign_keys)).ondelete == "SET NULL"
    relation = inspect(Signal).relationships.outcomes
    assert "delete" not in relation.cascade
    assert "delete-orphan" not in relation.cascade
    assert relation.passive_deletes == "all"


def test_historical_identity_does_not_block_fresh_observation():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table, columns in (
            (RentalListing.__table__, ("source_id", "source_item_id")),
            (Event.__table__, ("raw_item_id", "event_type")),
        ):
            connection.exec_driver_sql(
                f"CREATE TABLE {table.name} "
                f"({columns[0]} TEXT, {columns[1]} TEXT, is_historical BOOLEAN)"
            )
            for index in table.indexes:
                if index.unique:
                    index.create(connection)
            connection.exec_driver_sql(f"INSERT INTO {table.name} VALUES ('source','item',1)")
            connection.exec_driver_sql(f"INSERT INTO {table.name} VALUES ('source','item',0)")
            assert (
                connection.exec_driver_sql(
                    f"SELECT count(*) FROM {table.name} WHERE NOT is_historical"
                ).scalar()
                == 1
            )
