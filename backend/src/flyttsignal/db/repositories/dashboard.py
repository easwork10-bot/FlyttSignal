import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from geoalchemy2 import Geography
from sqlalchemy import Select, and_, cast, desc, exists, func, select
from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from flyttsignal.db.models import (
    Address,
    AddressEnrichment,
    City,
    Event,
    HousingProvider,
    HousingProviderCity,
    ListingMeasurement,
    PilotSignalFeedback,
    Property,
    ProviderChannel,
    RentalListing,
    RentalListingClassification,
    RentalProject,
    Signal,
    SignalEvidence,
    SignalOutcome,
    Source,
    SourceRun,
    SpatialFeature,
)
from flyttsignal.db.repositories.score_activations import active_dimensions_subquery
from flyttsignal.domains.signals.pilot import (
    PilotCohortPolicy,
    PilotSignalFilters,
    PilotSignalSort,
)

ACTIVE_SCORE_SCOPE = "internal-pilot"


def _advertised_available_from():
    """Return the current advertised date without consulting fabricated signal windows."""

    return (
        select(func.min(RentalListing.available_from))
        .select_from(SignalEvidence)
        .join(Event, Event.id == SignalEvidence.event_id)
        .join(RentalListing, RentalListing.raw_item_id == Event.raw_item_id)
        .where(
            SignalEvidence.signal_id == Signal.id,
            SignalEvidence.superseded_at.is_(None),
            RentalListing.status == "ACTIVE",
        )
        .correlate(Signal)
        .scalar_subquery()
    )


@dataclass(frozen=True)
class PilotSignalSummary:
    total: int
    high: int
    medium: int
    low: int
    next_30_days: int
    mapped: int


class DashboardRepository:
    def __init__(self, session: Session):
        self.session = session

    def cities(self) -> list[City]:
        return list(self.session.scalars(select(City).order_by(City.name)))

    def sources(self) -> list[Source]:
        return list(self.session.scalars(select(Source).order_by(Source.name)))

    def source_by_key(self, key: str) -> Source | None:
        return self.session.scalar(select(Source).where(Source.key == key))

    def source_runs(
        self, limit: int = 50, source_id: uuid.UUID | None = None, status: str | None = None
    ) -> list[SourceRun]:
        query = select(SourceRun).options(selectinload(SourceRun.source))
        if source_id is not None:
            query = query.where(SourceRun.source_id == source_id)
        if status is not None:
            query = query.where(SourceRun.status == status)
        return list(self.session.scalars(query.order_by(SourceRun.started_at.desc()).limit(limit)))

    def rental_projects(self, city: str = "Uppsala") -> list[tuple[RentalProject, int]]:
        imported_count = (
            select(func.count(RentalListing.id))
            .where(
                RentalListing.rental_project_id == RentalProject.id,
                RentalListing.status == "ACTIVE",
                RentalListing.data_mode == "live",
            )
            .correlate(RentalProject)
            .scalar_subquery()
        )
        return list(
            self.session.execute(
                select(RentalProject, imported_count.label("imported_count"))
                .where(RentalProject.city == city, RentalProject.data_mode == "live")
                .order_by(RentalProject.active_listing_count.desc(), RentalProject.name)
            ).tuples()
        )

    def live_provider_inventory(self, city_id: int = 1) -> list[tuple[str, str, str, int]]:
        return list(
            self.session.execute(
                select(
                    RentalListing.upstream_provider_key,
                    RentalListing.upstream_provider_name,
                    Source.name,
                    func.count(RentalListing.id),
                )
                .join(RentalListing.source)
                .join(RentalListing.property)
                .join(Property.address)
                .where(
                    RentalListing.status == "ACTIVE",
                    RentalListing.data_mode == "live",
                    Address.city_id == city_id,
                )
                .group_by(
                    RentalListing.upstream_provider_key,
                    RentalListing.upstream_provider_name,
                    Source.name,
                )
            ).tuples()
        )

    def spatial_features(self, limit: int = 100) -> list[tuple[SpatialFeature, str]]:
        return list(
            self.session.execute(
                select(SpatialFeature, func.ST_AsGeoJSON(SpatialFeature.geometry))
                .options(selectinload(SpatialFeature.source))
                .order_by(
                    SpatialFeature.source_modified_at.desc().nullslast(),
                    SpatialFeature.updated_at.desc(),
                )
                .limit(limit)
            ).tuples()
        )

    def rental_listings(
        self,
        *,
        status: str | None = "ACTIVE",
        provider: str | None = None,
        data_mode: str | None = None,
        limit: int = 100,
    ) -> list[RentalListing]:
        query = select(RentalListing).options(
            selectinload(RentalListing.source),
            selectinload(RentalListing.property)
            .selectinload(Property.address)
            .selectinload(Address.city),
        )
        if status:
            query = query.where(RentalListing.status == status)
        if provider:
            query = query.where(RentalListing.upstream_provider_key == provider)
        if data_mode:
            query = query.where(RentalListing.data_mode == data_mode)
        return list(
            self.session.scalars(
                query.order_by(
                    RentalListing.application_deadline.asc().nullslast(),
                    RentalListing.last_seen_at.desc(),
                ).limit(limit)
            ).unique()
        )

    def rental_listing(self, listing_id: uuid.UUID) -> RentalListing | None:
        return self.session.get(RentalListing, listing_id)

    def rental_listing_classifications(
        self, listing_id: uuid.UUID
    ) -> list[RentalListingClassification]:
        return list(
            self.session.scalars(
                select(RentalListingClassification)
                .where(RentalListingClassification.listing_id == listing_id)
                .order_by(
                    RentalListingClassification.rule_version,
                    RentalListingClassification.tag,
                )
            )
        )

    def rental_listing_measurements(self, listing_id: uuid.UUID) -> list[ListingMeasurement]:
        return list(
            self.session.scalars(
                select(ListingMeasurement)
                .where(ListingMeasurement.listing_id == listing_id)
                .order_by(ListingMeasurement.rule_version, ListingMeasurement.metric)
            )
        )

    def lead_time_population(
        self,
        *,
        source_key: str | None = None,
        classification_tag: str | None = None,
        listing_status: str | None = "ACTIVE",
    ) -> list[tuple[RentalListing, ListingMeasurement | None]]:
        measurement_join = and_(
            ListingMeasurement.listing_id == RentalListing.id,
            ListingMeasurement.metric == "LEAD_TIME_DAYS",
            ListingMeasurement.rule_version == "lead-time-v1",
        )
        query = (
            select(RentalListing, ListingMeasurement)
            .outerjoin(ListingMeasurement, measurement_join)
            .where(RentalListing.data_mode == "live")
        )
        if source_key is not None:
            query = query.join(Source, RentalListing.source_id == Source.id).where(
                Source.key == source_key
            )
        if classification_tag is not None:
            query = query.where(
                exists(
                    select(RentalListingClassification.id).where(
                        RentalListingClassification.listing_id == RentalListing.id,
                        RentalListingClassification.rule_version == "classification-v1",
                        RentalListingClassification.tag == classification_tag,
                    )
                )
            )
        if listing_status is not None:
            query = query.where(RentalListing.status == listing_status)
        return list(self.session.execute(query.order_by(RentalListing.id)).tuples())

    def housing_providers(self, city_id: int = 1) -> list[HousingProvider]:
        return list(
            self.session.scalars(
                select(HousingProvider)
                .join(HousingProviderCity)
                .where(HousingProviderCity.city_id == city_id, HousingProvider.active.is_(True))
                .options(
                    selectinload(HousingProvider.cities).selectinload(HousingProviderCity.city),
                    selectinload(HousingProvider.channels).selectinload(ProviderChannel.source),
                )
                .order_by(HousingProvider.name)
            ).unique()
        )

    @staticmethod
    def _has_live_evidence() -> object:
        """Keep product signals behind the same live-data boundary as listings."""
        return exists(
            select(SignalEvidence.signal_id)
            .join(Event, Event.id == SignalEvidence.event_id)
            .join(RentalListing, RentalListing.raw_item_id == Event.raw_item_id)
            .where(
                SignalEvidence.signal_id == Signal.id,
                SignalEvidence.superseded_at.is_(None),
                RentalListing.data_mode == "live",
            )
        )

    def signal_query(self, *, product_only: bool = True) -> Select:
        query = select(Signal).where(Signal.current()).options(
            selectinload(Signal.property).selectinload(Property.address).selectinload(Address.city),
            selectinload(Signal.property)
            .selectinload(Property.address)
            .selectinload(Address.enrichments)
            .selectinload(AddressEnrichment.source),
            selectinload(Signal.property)
            .selectinload(Property.address)
            .selectinload(Address.enrichments)
            .selectinload(AddressEnrichment.register_unit_link),
            selectinload(Signal.evidence)
            .selectinload(SignalEvidence.event)
            .selectinload(Event.raw_item),
            selectinload(Signal.evidence)
            .selectinload(SignalEvidence.event)
            .selectinload(Event.source),
            with_loader_criteria(
                SignalEvidence,
                SignalEvidence.superseded_at.is_(None),
                include_aliases=True,
            ),
        )
        if product_only:
            query = query.where(self._has_live_evidence())
        return query

    def signals(
        self,
        *,
        city_id: int | None = None,
        min_strength: int = 0,
        signal_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Signal]:
        active = active_dimensions_subquery(
            scope_key=ACTIVE_SCORE_SCOPE,
            city_id=city_id or 1,
        )
        available_from = _advertised_available_from()
        query = (
            self.signal_query(product_only=False)
            .join(active, active.c.signal_id == Signal.id)
            .add_columns(
                active.c.signal_strength.label("_active_strength"),
                available_from.label("_available_from"),
            )
            .join(Signal.property)
            .join(Property.address)
            .where(self._has_live_evidence(), active.c.signal_strength >= min_strength)
        )
        if city_id is not None:
            query = query.where(Address.city_id == city_id)
        if signal_type:
            query = query.where(Signal.signal_type == signal_type)
        if date_from:
            query = query.where(available_from >= date_from)
        if date_to:
            query = query.where(available_from <= date_to)
        return list(
            self.session.scalars(
                query.order_by(active.c.signal_strength.desc(), Signal.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).unique()
        )

    def pilot_signal_query(
        self,
        *,
        policy: PilotCohortPolicy,
        as_of: date,
        score_run_id: uuid.UUID | None = None,
        filters: PilotSignalFilters | None = None,
        pilot_key: str | None = None,
    ) -> Select:
        """Build the immutable selection boundary shared by pilot pages and metrics."""

        active = active_dimensions_subquery(
            scope_key=ACTIVE_SCORE_SCOPE,
            city_id=policy.city_id,
        )
        available_from = _advertised_available_from()
        query = (
            self.signal_query(product_only=False)
            .join(active, active.c.signal_id == Signal.id)
            .add_columns(
                active.c.signal_strength.label("_active_strength"),
                Address.geometry.is_not(None).label("_mapped"),
                available_from.label("_available_from"),
            )
            .join(Signal.property)
            .join(Property.address)
            .where(
                Address.city_id == policy.city_id,
                self._has_live_evidence(),
                Signal.status == "ACTIVE",
                Signal.created_at >= policy.created_from(as_of),
                available_from.is_not(None),
                available_from >= as_of,
                available_from <= policy.move_horizon_to(as_of),
            )
        )
        if score_run_id is not None:
            query = query.where(active.c.run_id == score_run_id)
        filters = filters or PilotSignalFilters()
        if filters.address_query:
            escaped = (
                filters.address_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            query = query.where(Address.normalized_address.ilike(f"%{escaped}%", escape="\\"))
        if filters.review_status != "ALL":
            if not pilot_key or not score_run_id:
                raise ValueError("pilot_key and score_run_id are required for review filtering")
            has_feedback = exists(
                select(PilotSignalFeedback.id).where(
                    PilotSignalFeedback.signal_id == Signal.id,
                    PilotSignalFeedback.pilot_key == pilot_key,
                    PilotSignalFeedback.cohort_version == policy.cohort_version,
                    PilotSignalFeedback.dimension_scope_key == policy.dimension_scope_key,
                    PilotSignalFeedback.score_run_id == score_run_id,
                    PilotSignalFeedback.cohort_as_of_date == as_of,
                )
            )
            query = query.where(
                has_feedback if filters.review_status == "REVIEWED" else ~has_feedback
            )
        if filters.strength_band == "HIGH":
            query = query.where(active.c.signal_strength >= 60)
        elif filters.strength_band == "MEDIUM":
            query = query.where(
                active.c.signal_strength >= 40,
                active.c.signal_strength < 60,
            )
        elif filters.strength_band == "LOW":
            query = query.where(active.c.signal_strength < 40)
        if filters.signal_type:
            query = query.where(Signal.signal_type == filters.signal_type)
        if filters.date_from:
            query = query.where(available_from >= filters.date_from)
        if filters.date_to:
            query = query.where(available_from <= filters.date_to)
        if filters.property_type:
            query = query.where(Property.property_type == filters.property_type)
        if filters.min_rooms is not None:
            query = query.where(Property.rooms >= filters.min_rooms)
        if filters.max_rooms is not None:
            query = query.where(Property.rooms <= filters.max_rooms)
        if filters.min_area_m2 is not None:
            query = query.where(Property.area_m2 >= filters.min_area_m2)
        if filters.max_area_m2 is not None:
            query = query.where(Property.area_m2 <= filters.max_area_m2)
        if filters.has_radius:
            center = func.ST_SetSRID(
                func.ST_MakePoint(filters.center_longitude, filters.center_latitude), 4326
            )
            query = query.where(
                func.ST_DWithin(
                    cast(Address.geometry, Geography(srid=4326)),
                    cast(center, Geography(srid=4326)),
                    filters.radius_km * 1000,
                )
            )
        return query

    def pilot_signals(
        self,
        *,
        policy: PilotCohortPolicy,
        as_of: date,
        score_run_id: uuid.UUID | None = None,
        filters: PilotSignalFilters | None = None,
        pilot_key: str | None = None,
        sort: PilotSignalSort = "PRIORITY",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Signal], PilotSignalSummary]:
        """Select a reproducible live-only pilot cohort without copying product data."""

        query = self.pilot_signal_query(
            policy=policy,
            as_of=as_of,
            score_run_id=score_run_id,
            filters=filters,
            pilot_key=pilot_key,
        )
        population = query.order_by(None).subquery()
        summary_row = self.session.execute(
            select(
                func.count(population.c.id),
                func.count().filter(population.c._active_strength >= 60),
                func.count().filter(
                    population.c._active_strength >= 40,
                    population.c._active_strength < 60,
                ),
                func.count().filter(population.c._active_strength < 40),
                func.count().filter(population.c._available_from <= as_of + timedelta(days=30)),
                func.count().filter(population.c._mapped.is_(True)),
            )
        ).one()
        summary = PilotSignalSummary(*(int(value or 0) for value in summary_row))
        available_from = _advertised_available_from()
        order_by = {
            "PRIORITY": (
                desc("_active_strength"),
                Signal.created_at.desc(),
                Signal.id,
            ),
            "MOVE_WINDOW": (
                available_from.asc().nulls_last(),
                desc("_active_strength"),
                Signal.id,
            ),
            "NEWEST": (
                Signal.created_at.desc(),
                desc("_active_strength"),
                Signal.id,
            ),
        }[sort]
        items = list(
            self.session.scalars(
                query.order_by(*order_by).limit(limit).offset(offset)
            ).unique()
        )
        return items, summary

    def signal(self, signal_id: uuid.UUID) -> Signal | None:
        return self.session.scalar(self.signal_query().where(Signal.id == signal_id))

    def signal_outcomes(self, signal_id: uuid.UUID) -> list[SignalOutcome]:
        return list(
            self.session.scalars(
                select(SignalOutcome)
                .where(SignalOutcome.signal_id == signal_id)
                .order_by(SignalOutcome.observed_at.desc(), SignalOutcome.id)
            )
        )

    def signal_outcome_population(self) -> tuple[int, list[SignalOutcome]]:
        population_count = self.session.scalar(
            select(func.count(Signal.id)).where(self._has_live_evidence())
        )
        outcomes = list(
            self.session.scalars(
                select(SignalOutcome)
                .join(Signal, Signal.id == SignalOutcome.signal_id)
                .where(self._has_live_evidence())
                .order_by(SignalOutcome.observed_at.desc(), SignalOutcome.id)
            )
        )
        return population_count or 0, outcomes

    def property(self, property_id: uuid.UUID) -> Property | None:
        return self.session.scalar(
            select(Property)
            .options(
                selectinload(Property.address).selectinload(Address.city),
                selectinload(Property.address)
                .selectinload(Address.enrichments)
                .selectinload(AddressEnrichment.source),
                selectinload(Property.address)
                .selectinload(Address.enrichments)
                .selectinload(AddressEnrichment.register_unit_link),
            )
            .where(Property.id == property_id)
        )
