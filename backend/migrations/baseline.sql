--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5 (Debian 17.5-1.pgdg110+1)
-- Dumped by pg_dump version 17.5 (Debian 17.5-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: tiger; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger;


--
-- Name: tiger_data; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tiger_data;


--
-- Name: topology; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA topology;


--
-- Name: SCHEMA topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA topology IS 'PostGIS Topology schema';


--
-- Name: fuzzystrmatch; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch WITH SCHEMA public;


--
-- Name: EXTENSION fuzzystrmatch; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION fuzzystrmatch IS 'determine similarities and distance between strings';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_tiger_geocoder; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder WITH SCHEMA tiger;


--
-- Name: EXTENSION postgis_tiger_geocoder; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_tiger_geocoder IS 'PostGIS tiger geocoder and reverse geocoder';


--
-- Name: postgis_topology; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;


--
-- Name: EXTENSION postgis_topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_topology IS 'PostGIS topology spatial types and functions';


--
-- Name: event_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.event_type AS ENUM (
    'RENTAL_LISTED',
    'LISTING_REMOVED',
    'NEW_BUILD_MOVE_IN',
    'SALE_LISTED',
    'SALE_SOLD',
    'LEASE_TERMINATED',
    'PROPERTY_TRANSFERRED'
);


--
-- Name: run_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.run_status AS ENUM (
    'RUNNING',
    'SUCCESS',
    'FAILED'
);


--
-- Name: signal_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.signal_type AS ENUM (
    'LIKELY_TENANT_MOVE_OUT',
    'LIKELY_HOMEOWNER_MOVE',
    'NEW_BUILD_MOVE_IN',
    'POTENTIAL_RENTAL_TENANCY_CHANGE',
    'POTENTIAL_NEW_BUILD_MOVE_IN',
    'LIKELY_RENTAL_TURNOVER'
);


--
-- Name: source_scope; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.source_scope AS ENUM (
    'LOCAL',
    'REGIONAL',
    'NATIONAL'
);


--
-- Name: source_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.source_type AS ENUM (
    'PUBLIC_API',
    'OPEN_DATA',
    'PUBLIC_WEB',
    'PARTNER_API',
    'FILE',
    'FAKE'
);


--
-- Name: reject_rental_listing_revision_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reject_rental_listing_revision_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          RAISE EXCEPTION 'rental_listing_revisions is append-only';
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: address_enrichments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.address_enrichments (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    raw_item_id uuid NOT NULL,
    address_id uuid NOT NULL,
    external_address_id uuid NOT NULL,
    canonical_address character varying(250) NOT NULL,
    municipality_code character varying(4) NOT NULL,
    postal_code character varying(5),
    postal_town character varying(100),
    status character varying(30) NOT NULL,
    source_srid integer NOT NULL,
    source_easting numeric(12,3) NOT NULL,
    source_northing numeric(12,3) NOT NULL,
    attribution text NOT NULL,
    source_attributes jsonb NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: address_register_unit_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.address_register_unit_links (
    id uuid NOT NULL,
    address_enrichment_id uuid NOT NULL,
    external_register_unit_id uuid NOT NULL,
    designation character varying(250) NOT NULL,
    register_unit_type character varying(30) NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT address_register_unit_links_register_unit_type_check CHECK (((register_unit_type)::text = ANY ((ARRAY['Fastighet'::character varying, 'Samfällighet'::character varying])::text[])))
);


--
-- Name: addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.addresses (
    id uuid NOT NULL,
    raw_address character varying(250) NOT NULL,
    normalized_address character varying(250) NOT NULL,
    city_id integer NOT NULL,
    municipality_code character varying(4) NOT NULL,
    latitude numeric(9,6),
    longitude numeric(9,6),
    geometry public.geometry(Point,4326),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: benchmark_observations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.benchmark_observations (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    raw_item_id uuid NOT NULL,
    dataset_key character varying(100) NOT NULL,
    dimension_key character varying(64) NOT NULL,
    metric_key character varying(100) NOT NULL,
    municipality_code character varying(4) NOT NULL,
    period character varying(30) NOT NULL,
    value numeric(20,4),
    unit character varying(50) NOT NULL,
    dimensions jsonb NOT NULL,
    source_updated_at timestamp with time zone,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: cities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cities (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    municipality_code character varying(4) NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: cities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cities_id_seq OWNED BY public.cities.id;


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id uuid NOT NULL,
    property_id uuid NOT NULL,
    source_id uuid NOT NULL,
    raw_item_id uuid NOT NULL,
    event_type public.event_type NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    effective_date date,
    metadata jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    upstream_provider_key character varying(120) NOT NULL
);


--
-- Name: housing_provider_cities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.housing_provider_cities (
    provider_id uuid NOT NULL,
    city_id integer NOT NULL,
    discovery_source character varying(120) NOT NULL,
    evidence_url text NOT NULL,
    verified_at timestamp with time zone NOT NULL
);


--
-- Name: housing_providers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.housing_providers (
    id uuid NOT NULL,
    key character varying(120) NOT NULL,
    name character varying(200) NOT NULL,
    provider_type character varying(30) NOT NULL,
    official_url text NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: listing_measurements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.listing_measurements (
    id uuid NOT NULL,
    listing_id uuid NOT NULL,
    metric character varying(50) NOT NULL,
    value numeric(12,3),
    unit character varying(20) NOT NULL,
    status character varying(30) NOT NULL,
    rule_version character varying(50) NOT NULL,
    inputs jsonb NOT NULL,
    measured_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT listing_measurements_check CHECK (((((status)::text = 'MEASURED'::text) AND (value IS NOT NULL)) OR (((status)::text <> 'MEASURED'::text) AND (value IS NULL)))),
    CONSTRAINT listing_measurements_status_check CHECK (((status)::text = ANY ((ARRAY['MEASURED'::character varying, 'MISSING_INPUT'::character varying, 'INVALID_INPUT'::character varying])::text[])))
);


--
-- Name: pilot_signal_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pilot_signal_activity (
    id uuid NOT NULL,
    signal_id uuid NOT NULL,
    pilot_key character varying(80) NOT NULL,
    cohort_version character varying(50) NOT NULL,
    score_rule_version character varying(50),
    cohort_as_of_date date NOT NULL,
    activity_type character varying(20) NOT NULL,
    occurrence_count integer NOT NULL,
    first_occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    last_occurred_at timestamp with time zone NOT NULL,
    dimension_scope_key character varying(100),
    score_run_id uuid,
    score_as_of_date date,
    definition_set_hash character varying(64),
    signal_strength_at_activity integer,
    data_confidence_at_activity integer,
    timing_at_activity integer,
    CONSTRAINT ck_pilot_activity_snapshot_mode CHECK ((((score_rule_version IS NOT NULL) AND (dimension_scope_key IS NULL) AND (score_run_id IS NULL) AND (score_as_of_date IS NULL) AND (definition_set_hash IS NULL) AND (signal_strength_at_activity IS NULL) AND (data_confidence_at_activity IS NULL) AND (timing_at_activity IS NULL)) OR ((score_rule_version IS NULL) AND (dimension_scope_key IS NOT NULL) AND (score_run_id IS NOT NULL) AND (score_as_of_date IS NOT NULL) AND (definition_set_hash IS NOT NULL) AND (signal_strength_at_activity IS NOT NULL) AND (data_confidence_at_activity IS NOT NULL) AND (timing_at_activity IS NOT NULL)))),
    CONSTRAINT ck_pilot_signal_activity_data_confidence_at_activity_range CHECK (((data_confidence_at_activity IS NULL) OR ((data_confidence_at_activity >= 0) AND (data_confidence_at_activity <= 100)))),
    CONSTRAINT ck_pilot_signal_activity_signal_strength_at_activity_range CHECK (((signal_strength_at_activity IS NULL) OR ((signal_strength_at_activity >= 0) AND (signal_strength_at_activity <= 100)))),
    CONSTRAINT ck_pilot_signal_activity_timing_at_activity_range CHECK (((timing_at_activity IS NULL) OR ((timing_at_activity >= 0) AND (timing_at_activity <= 100)))),
    CONSTRAINT pilot_signal_activity_activity_type_check CHECK (((activity_type)::text = ANY ((ARRAY['SHOWN'::character varying, 'OPENED'::character varying])::text[]))),
    CONSTRAINT pilot_signal_activity_occurrence_count_check CHECK ((occurrence_count > 0))
);


--
-- Name: pilot_signal_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pilot_signal_feedback (
    id uuid NOT NULL,
    signal_id uuid NOT NULL,
    pilot_key character varying(80) NOT NULL,
    cohort_version character varying(50) NOT NULL,
    score_rule_version character varying(50),
    cohort_as_of_date date NOT NULL,
    score_at_review integer,
    verdict character varying(20) NOT NULL,
    reason character varying(50) NOT NULL,
    note text,
    reviewed_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    dimension_scope_key character varying(100),
    score_run_id uuid,
    score_as_of_date date,
    definition_set_hash character varying(64),
    signal_strength_at_review integer,
    data_confidence_at_review integer,
    timing_at_review integer,
    CONSTRAINT ck_pilot_feedback_snapshot_mode CHECK ((((score_rule_version IS NOT NULL) AND (score_at_review IS NOT NULL) AND (dimension_scope_key IS NULL) AND (score_run_id IS NULL) AND (score_as_of_date IS NULL) AND (definition_set_hash IS NULL) AND (signal_strength_at_review IS NULL) AND (data_confidence_at_review IS NULL) AND (timing_at_review IS NULL)) OR ((score_rule_version IS NULL) AND (score_at_review IS NULL) AND (dimension_scope_key IS NOT NULL) AND (score_run_id IS NOT NULL) AND (score_as_of_date IS NOT NULL) AND (definition_set_hash IS NOT NULL) AND (signal_strength_at_review IS NOT NULL) AND (data_confidence_at_review IS NOT NULL) AND (timing_at_review IS NOT NULL)))),
    CONSTRAINT ck_pilot_signal_feedback_data_confidence_at_review_range CHECK (((data_confidence_at_review IS NULL) OR ((data_confidence_at_review >= 0) AND (data_confidence_at_review <= 100)))),
    CONSTRAINT ck_pilot_signal_feedback_signal_strength_at_review_range CHECK (((signal_strength_at_review IS NULL) OR ((signal_strength_at_review >= 0) AND (signal_strength_at_review <= 100)))),
    CONSTRAINT ck_pilot_signal_feedback_timing_at_review_range CHECK (((timing_at_review IS NULL) OR ((timing_at_review >= 0) AND (timing_at_review <= 100)))),
    CONSTRAINT pilot_signal_feedback_reason_check CHECK (((reason)::text = ANY ((ARRAY['GOOD_OPPORTUNITY'::character varying, 'TOO_EARLY'::character varying, 'TOO_LATE'::character varying, 'WRONG_PROPERTY'::character varying, 'WEAK_SIGNAL'::character varying, 'DUPLICATE'::character varying, 'OUTSIDE_SERVICE_AREA'::character varying, 'INSUFFICIENT_CONTEXT'::character varying])::text[]))),
    CONSTRAINT pilot_signal_feedback_score_at_review_check CHECK (((score_at_review >= 0) AND (score_at_review <= 100))),
    CONSTRAINT pilot_signal_feedback_verdict_check CHECK (((verdict)::text = ANY ((ARRAY['USEFUL'::character varying, 'MAYBE'::character varying, 'NOT_USEFUL'::character varying])::text[])))
);


--
-- Name: properties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.properties (
    id uuid NOT NULL,
    address_id uuid NOT NULL,
    property_type character varying(50) NOT NULL,
    rooms numeric(4,1),
    area_m2 numeric(8,2),
    new_construction boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    unit_identifier character varying(50)
);


--
-- Name: provider_channels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.provider_channels (
    id uuid NOT NULL,
    provider_id uuid NOT NULL,
    city_id integer NOT NULL,
    source_id uuid,
    channel_key character varying(160) NOT NULL,
    channel_type character varying(30) NOT NULL,
    publisher_name character varying(200) NOT NULL,
    url text NOT NULL,
    coverage character varying(20) NOT NULL,
    collection_status character varying(30) NOT NULL,
    is_primary boolean DEFAULT false NOT NULL,
    requires_auth boolean DEFAULT false NOT NULL,
    requires_agreement boolean DEFAULT false NOT NULL,
    next_action text
);


--
-- Name: raw_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_items (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    source_item_id character varying(200) NOT NULL,
    source_url text,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL,
    content_hash character varying(64) NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rental_listing_classifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_listing_classifications (
    id uuid NOT NULL,
    listing_id uuid NOT NULL,
    tag character varying(50) NOT NULL,
    confidence numeric(4,3) NOT NULL,
    reason character varying(100) NOT NULL,
    evidence jsonb NOT NULL,
    rule_version character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rental_listing_revisions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_listing_revisions (
    id uuid NOT NULL,
    listing_id uuid NOT NULL,
    source_run_id uuid,
    raw_item_id uuid,
    revision_number integer NOT NULL,
    operation_key character varying(200) NOT NULL,
    change_kind character varying(30) NOT NULL,
    provenance_kind character varying(20) NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    content_hash character varying(64),
    raw_payload jsonb,
    normalization_revision character varying(80) NOT NULL,
    normalized_payload_hash character varying(64) NOT NULL,
    listing_status character varying(30) NOT NULL,
    available_from date,
    application_deadline date,
    new_construction boolean,
    categories jsonb NOT NULL,
    unit_identifier character varying(50),
    extra_normalized_facts jsonb NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT rental_listing_revisions_change_kind_check CHECK (((change_kind)::text = ANY ((ARRAY['CONTENT_OBSERVED'::character varying, 'LISTING_REMOVED'::character varying, 'LISTING_RELISTED'::character varying])::text[]))),
    CONSTRAINT rental_listing_revisions_provenance_kind_check CHECK (((provenance_kind)::text = ANY ((ARRAY['DIRECT'::character varying, 'RECONSTRUCTED'::character varying])::text[]))),
    CONSTRAINT rental_listing_revisions_revision_number_check CHECK ((revision_number > 0))
);


--
-- Name: rental_listings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_listings (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    raw_item_id uuid NOT NULL,
    property_id uuid NOT NULL,
    source_item_id character varying(200) NOT NULL,
    canonical_url text,
    upstream_provider_key character varying(120) NOT NULL,
    upstream_provider_name character varying(200) NOT NULL,
    monthly_rent numeric(10,2),
    application_deadline date,
    available_from date,
    categories jsonb NOT NULL,
    data_mode character varying(20) NOT NULL,
    attribution text NOT NULL,
    status character varying(30) DEFAULT 'ACTIVE'::character varying NOT NULL,
    consecutive_misses integer DEFAULT 0 NOT NULL,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    removed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    rental_project_id uuid,
    project_source_item_id character varying(200),
    unit_identifier character varying(50),
    rooms numeric(4,1),
    area_m2 numeric(8,2),
    new_construction boolean,
    CONSTRAINT rental_listings_consecutive_misses_check CHECK ((consecutive_misses >= 0)),
    CONSTRAINT rental_listings_data_mode_check CHECK (((data_mode)::text = ANY ((ARRAY['fixture'::character varying, 'live'::character varying])::text[]))),
    CONSTRAINT rental_listings_status_check CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'REMOVAL_CANDIDATE'::character varying, 'REMOVED'::character varying])::text[])))
);


--
-- Name: rental_projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_projects (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    raw_item_id uuid NOT NULL,
    source_item_id character varying(200) NOT NULL,
    canonical_url text NOT NULL,
    name character varying(200) NOT NULL,
    upstream_provider_key character varying(120) NOT NULL,
    upstream_provider_name character varying(200) NOT NULL,
    address character varying(250) NOT NULL,
    city character varying(100) NOT NULL,
    municipality_code character varying(4) NOT NULL,
    planned_unit_count integer,
    active_listing_count integer DEFAULT 0 NOT NULL,
    rent_min numeric(10,2),
    rent_max numeric(10,2),
    rooms_min numeric(4,1),
    rooms_max numeric(4,1),
    area_min numeric(8,2),
    area_max numeric(8,2),
    available_from date,
    latitude numeric(9,6),
    longitude numeric(9,6),
    status character varying(30) NOT NULL,
    data_mode character varying(20) NOT NULL,
    attribution text NOT NULL,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: score_activations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.score_activations (
    id uuid NOT NULL,
    scope_type character varying(30) NOT NULL,
    scope_key character varying(100) NOT NULL,
    city_id integer NOT NULL,
    dimension character varying(40) NOT NULL,
    definition_id uuid NOT NULL,
    decision_run_id uuid NOT NULL,
    decision_reason text NOT NULL,
    activated_at timestamp with time zone DEFAULT now() NOT NULL,
    retired_at timestamp with time zone,
    CONSTRAINT ck_score_activations_dimension CHECK (((dimension)::text = ANY ((ARRAY['SIGNAL_STRENGTH'::character varying, 'DATA_CONFIDENCE'::character varying, 'TIMING'::character varying])::text[]))),
    CONSTRAINT ck_score_activations_retirement CHECK (((retired_at IS NULL) OR (retired_at >= activated_at))),
    CONSTRAINT ck_score_activations_scope_type CHECK (((scope_type)::text = ANY ((ARRAY['INTERNAL_PILOT'::character varying, 'CUSTOMER_PILOT'::character varying, 'PRODUCTION'::character varying])::text[])))
);


--
-- Name: score_components; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.score_components (
    id uuid NOT NULL,
    signal_id uuid NOT NULL,
    component character varying(100) NOT NULL,
    points integer NOT NULL,
    reason text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: score_definitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.score_definitions (
    id uuid NOT NULL,
    dimension character varying(40) NOT NULL,
    definition_revision character varying(80) NOT NULL,
    parameters jsonb NOT NULL,
    parameter_hash character varying(64) NOT NULL,
    feature_schema_revision character varying(80) NOT NULL,
    engine_revision character varying(100) NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_score_definitions_dimension CHECK (((dimension)::text = ANY ((ARRAY['SIGNAL_STRENGTH'::character varying, 'DATA_CONFIDENCE'::character varying, 'TIMING'::character varying])::text[]))),
    CONSTRAINT ck_score_definitions_status CHECK (((status)::text = ANY ((ARRAY['CANDIDATE'::character varying, 'ACTIVE'::character varying, 'RETIRED'::character varying])::text[])))
);


--
-- Name: score_evaluation_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.score_evaluation_runs (
    id uuid NOT NULL,
    city_id integer NOT NULL,
    baseline_rule_version character varying(50) NOT NULL,
    candidate_rule_version character varying(50) NOT NULL,
    as_of_date date NOT NULL,
    population_size integer NOT NULL,
    status character varying(20) NOT NULL,
    summary jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    input_fingerprint character varying(64) NOT NULL,
    CONSTRAINT score_evaluation_runs_population_size_check CHECK ((population_size > 0)),
    CONSTRAINT score_evaluation_runs_status_check CHECK (((status)::text = 'COMPLETE'::text))
);


--
-- Name: score_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.score_runs (
    id uuid NOT NULL,
    city_id integer NOT NULL,
    as_of_date date NOT NULL,
    feature_schema_revision character varying(80) NOT NULL,
    definition_set_hash character varying(64) NOT NULL,
    population_fingerprint character varying(64) NOT NULL,
    population_size integer NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_score_runs_population_size CHECK ((population_size > 0)),
    CONSTRAINT ck_score_runs_status CHECK (((status)::text = 'COMPLETE'::text))
);


--
-- Name: signal_dimension_evaluations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_dimension_evaluations (
    id uuid NOT NULL,
    run_id uuid NOT NULL,
    signal_id uuid NOT NULL,
    feature_snapshot_id uuid NOT NULL,
    definition_id uuid NOT NULL,
    dimension character varying(40) NOT NULL,
    score integer NOT NULL,
    components jsonb NOT NULL,
    warnings jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_signal_dimension_evaluations_dimension CHECK (((dimension)::text = ANY ((ARRAY['SIGNAL_STRENGTH'::character varying, 'DATA_CONFIDENCE'::character varying, 'TIMING'::character varying])::text[]))),
    CONSTRAINT ck_signal_dimension_evaluations_score CHECK (((score >= 0) AND (score <= 100)))
);


--
-- Name: signal_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_evidence (
    signal_id uuid NOT NULL,
    event_id uuid NOT NULL,
    weight integer DEFAULT 1 NOT NULL,
    reason text NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    superseded_at timestamp with time zone,
    superseded_by_event_id uuid,
    supersession_reason text,
    CONSTRAINT ck_signal_evidence_supersession_complete CHECK ((((superseded_at IS NULL) AND (superseded_by_event_id IS NULL) AND (supersession_reason IS NULL)) OR ((superseded_at IS NOT NULL) AND (superseded_by_event_id IS NOT NULL) AND (supersession_reason IS NOT NULL) AND (superseded_at >= valid_from))))
);


--
-- Name: signal_feature_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_feature_snapshots (
    id uuid NOT NULL,
    signal_id uuid NOT NULL,
    feature_schema_revision character varying(80) NOT NULL,
    as_of_date date NOT NULL,
    payload jsonb NOT NULL,
    payload_hash character varying(64) NOT NULL,
    captured_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: signal_outcomes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_outcomes (
    id uuid NOT NULL,
    signal_id uuid NOT NULL,
    listing_id uuid,
    event_id uuid,
    outcome_type character varying(50) NOT NULL,
    subject character varying(30) NOT NULL,
    verification_level character varying(20) NOT NULL,
    observed_at timestamp with time zone NOT NULL,
    confidence numeric(4,3) NOT NULL,
    evidence jsonb NOT NULL,
    rule_version character varying(50) NOT NULL,
    dedupe_key character varying(200) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT signal_outcomes_check CHECK (((((outcome_type)::text = 'CONFIRMED_MOVE'::text) AND ((subject)::text = 'HOUSEHOLD_MOVE'::text) AND ((verification_level)::text = 'CONFIRMED'::text)) OR (((outcome_type)::text <> 'CONFIRMED_MOVE'::text) AND ((subject)::text <> 'HOUSEHOLD_MOVE'::text) AND ((verification_level)::text = 'OBSERVED'::text)))),
    CONSTRAINT signal_outcomes_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
    CONSTRAINT signal_outcomes_outcome_type_check CHECK (((outcome_type)::text = ANY ((ARRAY['LISTING_REMOVED'::character varying, 'LISTING_RELISTED'::character varying, 'AVAILABLE_DATE_CHANGED'::character varying, 'CROSS_SOURCE_CONFIRMED'::character varying, 'UNKNOWN'::character varying, 'CONFIRMED_MOVE'::character varying])::text[]))),
    CONSTRAINT signal_outcomes_subject_check CHECK (((subject)::text = ANY ((ARRAY['LISTING'::character varying, 'SIGNAL'::character varying, 'HOUSEHOLD_MOVE'::character varying])::text[]))),
    CONSTRAINT signal_outcomes_verification_level_check CHECK (((verification_level)::text = ANY ((ARRAY['OBSERVED'::character varying, 'CONFIRMED'::character varying])::text[])))
);


--
-- Name: signal_score_evaluations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_score_evaluations (
    id uuid NOT NULL,
    run_id uuid NOT NULL,
    signal_id uuid NOT NULL,
    baseline_score integer NOT NULL,
    candidate_score integer NOT NULL,
    delta integer NOT NULL,
    inputs jsonb NOT NULL,
    components jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: signal_validations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_validations (
    id uuid NOT NULL,
    batch_id uuid NOT NULL,
    signal_id uuid NOT NULL,
    score_at_selection integer,
    score_stratum character varying(20),
    inclusion_reasons jsonb NOT NULL,
    source_keys jsonb NOT NULL,
    provider_keys jsonb NOT NULL,
    classification_tags jsonb NOT NULL,
    review_status character varying(20) NOT NULL,
    verdict character varying(20),
    issue_codes jsonb NOT NULL,
    notes text,
    reviewer character varying(120),
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    signal_strength_at_selection integer,
    data_confidence_at_selection integer,
    timing_at_selection integer,
    strength_stratum character varying(20),
    CONSTRAINT ck_signal_validations_data_confidence_at_selection_range CHECK (((data_confidence_at_selection IS NULL) OR ((data_confidence_at_selection >= 0) AND (data_confidence_at_selection <= 100)))),
    CONSTRAINT ck_signal_validations_dimension_snapshot CHECK ((((signal_strength_at_selection IS NULL) AND (data_confidence_at_selection IS NULL) AND (timing_at_selection IS NULL) AND (strength_stratum IS NULL)) OR ((signal_strength_at_selection IS NOT NULL) AND (data_confidence_at_selection IS NOT NULL) AND (timing_at_selection IS NOT NULL) AND (strength_stratum IS NOT NULL)))),
    CONSTRAINT ck_signal_validations_legacy_score_stratum CHECK (((score_stratum IS NULL) OR ((score_stratum)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying])::text[])))),
    CONSTRAINT ck_signal_validations_signal_strength_at_selection_range CHECK (((signal_strength_at_selection IS NULL) OR ((signal_strength_at_selection >= 0) AND (signal_strength_at_selection <= 100)))),
    CONSTRAINT ck_signal_validations_strength_stratum CHECK (((strength_stratum IS NULL) OR ((strength_stratum)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying])::text[])))),
    CONSTRAINT ck_signal_validations_timing_at_selection_range CHECK (((timing_at_selection IS NULL) OR ((timing_at_selection >= 0) AND (timing_at_selection <= 100)))),
    CONSTRAINT signal_validations_check CHECK (((((review_status)::text = 'PENDING'::text) AND (verdict IS NULL) AND (reviewed_at IS NULL)) OR (((review_status)::text = 'REVIEWED'::text) AND (verdict IS NOT NULL) AND (reviewed_at IS NOT NULL)))),
    CONSTRAINT signal_validations_review_status_check CHECK (((review_status)::text = ANY ((ARRAY['PENDING'::character varying, 'REVIEWED'::character varying])::text[]))),
    CONSTRAINT signal_validations_verdict_check CHECK (((verdict IS NULL) OR ((verdict)::text = ANY ((ARRAY['GOOD'::character varying, 'QUESTIONABLE'::character varying, 'BAD'::character varying])::text[]))))
);


--
-- Name: signals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signals (
    id uuid NOT NULL,
    property_id uuid NOT NULL,
    signal_type public.signal_type NOT NULL,
    status character varying(30) DEFAULT 'ACTIVE'::character varying NOT NULL,
    score integer,
    estimated_move_from date,
    estimated_move_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    superseded_at timestamp with time zone,
    superseded_by_signal_id uuid,
    supersession_reason text,
    CONSTRAINT ck_signal_supersession_complete CHECK ((((superseded_at IS NULL) AND (superseded_by_signal_id IS NULL) AND (supersession_reason IS NULL)) OR ((superseded_at IS NOT NULL) AND (superseded_by_signal_id IS NOT NULL) AND (supersession_reason IS NOT NULL) AND (superseded_at >= created_at)))),
    CONSTRAINT signals_score_check CHECK (((score >= 0) AND (score <= 100)))
);


--
-- Name: source_cities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_cities (
    source_id uuid NOT NULL,
    city_id integer NOT NULL,
    enabled boolean DEFAULT true NOT NULL
);


--
-- Name: source_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_runs (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    status public.run_status NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    items_seen integer DEFAULT 0 NOT NULL,
    items_new integer DEFAULT 0 NOT NULL,
    items_changed integer DEFAULT 0 NOT NULL,
    error_message text,
    items_unchanged integer DEFAULT 0 NOT NULL,
    removal_candidates integer DEFAULT 0 NOT NULL,
    items_removed integer DEFAULT 0 NOT NULL,
    duration_ms integer,
    snapshot_status character varying(20) DEFAULT 'UNKNOWN'::character varying NOT NULL,
    requests_attempted integer,
    requests_succeeded integer,
    requests_failed integer,
    pages_expected integer,
    pages_received integer,
    items_reported integer,
    items_received integer,
    pagination_complete boolean,
    hit_result_limit boolean,
    snapshot_reasons jsonb DEFAULT '[]'::jsonb NOT NULL,
    snapshot_evidence jsonb DEFAULT '{}'::jsonb NOT NULL,
    completeness_rule_version character varying(50),
    inventory_scope_complete boolean,
    trigger_type character varying(20) DEFAULT 'UNKNOWN'::character varying NOT NULL
);


--
-- Name: sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sources (
    id uuid NOT NULL,
    key character varying(100) NOT NULL,
    name character varying(200) NOT NULL,
    source_type public.source_type NOT NULL,
    scope public.source_scope NOT NULL,
    access_method character varying(100) NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    poll_interval_minutes integer DEFAULT 1440 NOT NULL,
    last_run_at timestamp with time zone,
    last_success_at timestamp with time zone,
    next_run_at timestamp with time zone,
    status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: spatial_features; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.spatial_features (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    raw_item_id uuid NOT NULL,
    dataset_key character varying(100) NOT NULL,
    source_item_id character varying(200) NOT NULL,
    municipality_code character varying(4) NOT NULL,
    feature_type character varying(50) NOT NULL,
    subtype_code integer NOT NULL,
    subtype_label character varying(100) NOT NULL,
    status_code integer NOT NULL,
    status_label character varying(100) NOT NULL,
    activity_code integer,
    activity_label character varying(100),
    source_modified_at timestamp with time zone,
    geometry public.geometry(Geometry,4326) NOT NULL,
    attribution text NOT NULL,
    source_attributes jsonb NOT NULL,
    data_mode character varying(20) NOT NULL,
    is_baseline boolean DEFAULT true NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT spatial_features_data_mode_check CHECK (((data_mode)::text = ANY ((ARRAY['fixture'::character varying, 'live'::character varying])::text[]))),
    CONSTRAINT spatial_features_feature_type_check CHECK (((feature_type)::text = 'building'::text)),
    CONSTRAINT spatial_features_geometry_check CHECK ((public.geometrytype(geometry) = ANY (ARRAY['POLYGON'::text, 'MULTIPOLYGON'::text]))),
    CONSTRAINT spatial_features_municipality_code_check CHECK (((municipality_code)::text = '0380'::text))
);


--
-- Name: validation_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.validation_batches (
    id uuid NOT NULL,
    name character varying(120) NOT NULL,
    city_id integer NOT NULL,
    rule_version character varying(50) NOT NULL,
    seed character varying(120) NOT NULL,
    target_size integer NOT NULL,
    population_size integer NOT NULL,
    status character varying(20) NOT NULL,
    selection_manifest jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    dimension_scope_key character varying(100),
    score_run_id uuid,
    score_as_of_date date,
    definition_set_hash character varying(64),
    CONSTRAINT ck_validation_batches_dimension_provenance CHECK ((((score_run_id IS NULL) AND (score_as_of_date IS NULL) AND (definition_set_hash IS NULL) AND (dimension_scope_key IS NULL)) OR ((score_run_id IS NOT NULL) AND (score_as_of_date IS NOT NULL) AND (definition_set_hash IS NOT NULL) AND (dimension_scope_key IS NOT NULL)))),
    CONSTRAINT validation_batches_check CHECK ((population_size >= target_size)),
    CONSTRAINT validation_batches_status_check CHECK (((status)::text = ANY ((ARRAY['IN_REVIEW'::character varying, 'COMPLETE'::character varying])::text[]))),
    CONSTRAINT validation_batches_target_size_check CHECK ((target_size > 0))
);


--
-- Name: cities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cities ALTER COLUMN id SET DEFAULT nextval('public.cities_id_seq'::regclass);


--
-- Data for Name: address_enrichments; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: address_register_unit_links; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: addresses; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: benchmark_observations; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: cities; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.cities VALUES (1, 'Uppsala', '0380', true, CURRENT_TIMESTAMP);


--
-- Data for Name: events; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: housing_provider_cities; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000101', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000102', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000103', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000104', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000105', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000106', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000107', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000108', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-000000000109', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-00000000010a', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-00000000010b', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-00000000010c', 1, 'hyresgastforeningen-landlord-directory', 'https://www.hyresgastforeningen.se/om-oss/hyresvardar/hyresvardar-i-uppsala/', '2026-08-27 22:00:00+00');
INSERT INTO public.housing_provider_cities VALUES ('00000000-0000-0000-0000-00000000010d', 1, 'homeq-public-search', 'https://www.homeq.se/search?selectedShapes=urban_area.656%3B95530a7d4e4c6b6775fe60d90d678cd09707fa748d79d93da68aae7188bb1c15%3BUppsala', '2026-08-27 22:00:00+00');


--
-- Data for Name: housing_providers; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000101', 'uppsalahem', 'Uppsalahem', 'PUBLIC', 'https://www.uppsalahem.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000102', 'nationsgardarna', 'Nationsgårdarna', 'STUDENT', 'https://www.nationsgardarna.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000103', 'byggvesta', 'ByggVesta', 'PRIVATE', 'https://byggvesta.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000104', 'heimstaden', 'Heimstaden', 'PRIVATE', 'https://heimstaden.com/se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000105', 'ikano-bostad', 'Ikano Bostad', 'PRIVATE', 'https://www.ikanobostad.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000106', 'hsb-uppsala', 'HSB Uppsala', 'COOPERATIVE', 'https://www.hsb.se/uppsala/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000107', 'newsec', 'Newsec', 'MANAGER', 'https://hyresgaster.newsec.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000108', 'stena-fastigheter', 'Stena Fastigheter', 'PRIVATE', 'https://www.stenafastigheter.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-000000000109', 'rikshem', 'Rikshem', 'PRIVATE', 'https://www.rikshem.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-00000000010a', 'riksbyggen', 'Riksbyggen', 'COOPERATIVE', 'https://www.riksbyggen.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-00000000010b', 'victoriahem', 'Victoriahem', 'PRIVATE', 'https://www.victoriahem.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-00000000010c', 'balder', 'Balder', 'PRIVATE', 'https://www.balder.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.housing_providers VALUES ('00000000-0000-0000-0000-00000000010d', 'lansa', 'Lansa', 'PRIVATE', 'https://www.lansa.se/', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);


--
-- Data for Name: listing_measurements; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: pilot_signal_activity; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: pilot_signal_feedback; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: properties; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: provider_channels; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000101', 1, '00000000-0000-0000-0000-000000000006', 'uppsala-bostadsformedling', 'MARKETPLACE', 'Uppsala Bostadsförmedling', 'https://www.bostad.uppsala.se/', 'FULL', 'COLLECTED_FIXTURE', true, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000204', '00000000-0000-0000-0000-000000000104', 1, '00000000-0000-0000-0000-000000000007', 'heimstaden-direct', 'DIRECT', 'Heimstaden', 'https://heimstaden.com/se/lediga-lagenheter-uppsala/', 'PARTIAL', 'READY_FIXTURE', true, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000205', '00000000-0000-0000-0000-000000000104', 1, '00000000-0000-0000-0000-000000000006', 'uppsala-bostadsformedling', 'MARKETPLACE', 'Uppsala Bostadsförmedling', 'https://www.bostad.uppsala.se/', 'PARTIAL', 'COLLECTED_FIXTURE', false, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-00000000020e', '00000000-0000-0000-0000-00000000010a', 1, '00000000-0000-0000-0000-000000000006', 'uppsala-bostadsformedling', 'MARKETPLACE', 'Uppsala Bostadsförmedling', 'https://www.bostad.uppsala.se/', 'PARTIAL', 'COLLECTED_FIXTURE', false, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-00000000020f', '00000000-0000-0000-0000-00000000010b', 1, '00000000-0000-0000-0000-000000000006', 'uppsala-bostadsformedling', 'MARKETPLACE', 'Uppsala Bostadsförmedling', 'https://www.bostad.uppsala.se/', 'FULL', 'COLLECTED_FIXTURE', true, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000102', 1, NULL, 'nationsgardarna-portal', 'AUTHENTICATED', 'Nationsgårdarna', 'https://www.nationsgardarna.se/', 'FULL', 'RESTRICTED', true, true, true, 'Obtain an approved partner feed or an explicitly permitted account scope.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000203', '00000000-0000-0000-0000-000000000103', 1, NULL, 'byggvesta-direct', 'DIRECT', 'ByggVesta', 'https://minasidor.byggvesta.se/', 'FULL', 'WAIT_PARTNER', true, true, true, 'Request an approved listing feed or API; do not collect through an applicant account.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000206', '00000000-0000-0000-0000-000000000105', 1, NULL, 'homeq-partner-api', 'PARTNER_API', 'HomeQ Partner API', 'https://api.homeq.se/api-docs/', 'EXPECTED', 'WAIT_PARTNER', true, true, true, 'Confirm listing-read scope, retention, provenance, lifecycle semantics and operational limits with HomeQ.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000208', '00000000-0000-0000-0000-000000000106', 1, NULL, 'homeq-partner-api', 'PARTNER_API', 'HomeQ Partner API', 'https://api.homeq.se/api-docs/', 'PARTIAL', 'WAIT_PARTNER', false, true, true, 'Confirm listing-read scope, retention, provenance, lifecycle semantics and operational limits with HomeQ.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-00000000020d', '00000000-0000-0000-0000-00000000010a', 1, NULL, 'homeq-partner-api', 'PARTNER_API', 'HomeQ Partner API', 'https://api.homeq.se/api-docs/', 'PRIMARY', 'WAIT_PARTNER', true, true, true, 'Confirm listing-read scope, retention, provenance, lifecycle semantics and operational limits with HomeQ.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000210', '00000000-0000-0000-0000-00000000010c', 1, NULL, 'homeq-partner-api', 'PARTNER_API', 'HomeQ Partner API', 'https://api.homeq.se/api-docs/', 'FULL', 'WAIT_PARTNER', true, true, true, 'Confirm listing-read scope, retention, provenance, lifecycle semantics and operational limits with HomeQ.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000209', '00000000-0000-0000-0000-000000000107', 1, '00000000-0000-0000-0000-000000000006', 'uppsala-bostadsformedling', 'MARKETPLACE', 'Uppsala Bostadsförmedling', 'https://www.bostad.uppsala.se/for-hyresvardar/vara-hyresvardar/newsec', 'FULL', 'COLLECTED_FIXTURE', true, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-00000000020a', '00000000-0000-0000-0000-000000000108', 1, '00000000-0000-0000-0000-000000000006', 'uppsala-bostadsformedling', 'MARKETPLACE', 'Uppsala Bostadsförmedling', 'https://www.bostad.uppsala.se/for-hyresvardar/vara-hyresvardar/stena-fastigheter', 'FULL', 'COLLECTED_FIXTURE', true, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-00000000020b', '00000000-0000-0000-0000-000000000108', 1, NULL, 'stena-internal-queue', 'AUTHENTICATED', 'Stena Fastigheter', 'https://www.stenafastigheter.se/bostader/hyra-bostad/', 'INTERNAL', 'RESTRICTED', false, true, true, 'Keep the existing-tenant internal queue out of collection; use the public Uppsala Bostadsförmedling channel.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-00000000020c', '00000000-0000-0000-0000-000000000109', 1, '00000000-0000-0000-0000-000000000006', 'uppsala-bostadsformedling', 'MARKETPLACE', 'Uppsala Bostadsförmedling', 'https://www.bostad.uppsala.se/for-hyresvardar/vara-hyresvardar/rikshem', 'FULL', 'COLLECTED_FIXTURE', true, false, false, NULL);
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000211', '00000000-0000-0000-0000-000000000105', 1, '00000000-0000-0000-0000-00000000000b', 'homeq-public-search', 'MARKETPLACE', 'HomeQ', 'https://www.homeq.se/search?selectedShapes=urban_area.656%3B95530a7d4e4c6b6775fe60d90d678cd09707fa748d79d93da68aae7188bb1c15%3BUppsala', 'PARTIAL', 'CONTROLLED_LIVE', false, false, true, 'Observe the bounded public search and detail-page adapter; retain partner/API as a future reliability upgrade.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000212', '00000000-0000-0000-0000-000000000106', 1, '00000000-0000-0000-0000-00000000000b', 'homeq-public-search', 'MARKETPLACE', 'HomeQ', 'https://www.homeq.se/search?selectedShapes=urban_area.656%3B95530a7d4e4c6b6775fe60d90d678cd09707fa748d79d93da68aae7188bb1c15%3BUppsala', 'PARTIAL', 'CONTROLLED_LIVE', false, false, true, 'Observe the bounded public search and detail-page adapter; retain partner/API as a future reliability upgrade.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000213', '00000000-0000-0000-0000-00000000010a', 1, '00000000-0000-0000-0000-00000000000b', 'homeq-public-search', 'MARKETPLACE', 'HomeQ', 'https://www.homeq.se/search?selectedShapes=urban_area.656%3B95530a7d4e4c6b6775fe60d90d678cd09707fa748d79d93da68aae7188bb1c15%3BUppsala', 'PARTIAL', 'CONTROLLED_LIVE', false, false, true, 'Observe the bounded public search and detail-page adapter; retain partner/API as a future reliability upgrade.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000214', '00000000-0000-0000-0000-00000000010c', 1, '00000000-0000-0000-0000-00000000000b', 'homeq-public-search', 'MARKETPLACE', 'HomeQ', 'https://www.homeq.se/search?selectedShapes=urban_area.656%3B95530a7d4e4c6b6775fe60d90d678cd09707fa748d79d93da68aae7188bb1c15%3BUppsala', 'PARTIAL', 'CONTROLLED_LIVE', false, false, true, 'Observe the bounded public search and detail-page adapter; retain partner/API as a future reliability upgrade.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000215', '00000000-0000-0000-0000-00000000010d', 1, '00000000-0000-0000-0000-00000000000b', 'homeq-public-search', 'MARKETPLACE', 'HomeQ', 'https://www.homeq.se/search?selectedShapes=urban_area.656%3B95530a7d4e4c6b6775fe60d90d678cd09707fa748d79d93da68aae7188bb1c15%3BUppsala', 'PARTIAL', 'CONTROLLED_LIVE', true, false, true, 'Observe the bounded public search and detail-page adapter; retain partner/API as a future reliability upgrade.');
INSERT INTO public.provider_channels VALUES ('00000000-0000-0000-0000-000000000207', '00000000-0000-0000-0000-000000000106', 1, '00000000-0000-0000-0000-00000000000c', 'hsb-direct', 'DIRECT', 'HSB Uppsala', 'https://www.hsb.se/sok-bostad/sok-hyresratter/uppsala/', 'PARTIAL', 'CONTROLLED_LIVE', true, false, true, 'Observe the bounded direct public search independently from HSB listings distributed through HomeQ.');


--
-- Data for Name: raw_items; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: rental_listing_classifications; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: rental_listing_revisions; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: rental_listings; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: rental_projects; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: score_activations; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: score_components; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: score_definitions; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: score_evaluation_runs; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: score_runs; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: signal_dimension_evaluations; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: signal_evidence; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: signal_feature_snapshots; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: signal_outcomes; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: signal_score_evaluations; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: signal_validations; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: signals; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: source_cities; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000001', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000002', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000003', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000004', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000005', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000006', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000007', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000008', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-000000000009', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-00000000000a', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-00000000000b', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-00000000000c', 1, true);
INSERT INTO public.source_cities VALUES ('00000000-0000-0000-0000-00000000000d', 1, true);


--
-- Data for Name: source_runs; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: sources; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000003', 'scb_pxweb_migration', 'SCB PxWeb migration benchmark', 'PUBLIC_API', 'NATIONAL', 'pxwebapi_v2_json_stat2', false, 10080, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000004', 'lantmateriet_belagenhetsadress', 'Lantmäteriet Belägenhetsadress Direkt 4.2', 'PARTNER_API', 'NATIONAL', 'oauth2_rest_json_basinfo_berorkrets', false, 1440, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000005', 'uppsala_open_data_buildings', 'Uppsala Open Data — Byggnader', 'OPEN_DATA', 'LOCAL', 'public_arcgis_geojson', false, 1440, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000007', 'heimstaden_uppsala_rentals', 'Heimstaden — Uppsala direkt', 'PUBLIC_WEB', 'LOCAL', 'bounded_public_html_or_fixture', true, 60, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-00000000000a', 'uppsala_bostadsformedling_live_rentals', 'Uppsala Bostadsförmedling — live hyresrätter', 'PUBLIC_WEB', 'LOCAL', 'public_graphql_kill_switch', false, 60, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-00000000000b', 'homeq_public_uppsala_live_rentals', 'HomeQ — live publik Uppsala-sökning', 'PUBLIC_WEB', 'LOCAL', 'public_search_and_detail_pages', false, 180, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-00000000000c', 'hsb_public_uppsala_live_rentals', 'HSB — live publik Uppsala-sökning', 'PUBLIC_WEB', 'LOCAL', 'public_html_kill_switch', false, 180, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-00000000000d', 'homeq_public_uppsala_projects', 'HomeQ — publika Uppsala-projekt', 'PUBLIC_WEB', 'LOCAL', 'public_project_search_and_detail_pages', false, 180, NULL, NULL, NULL, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000001', 'fake_uppsala_rentals', 'Fake Uppsala Rentals', 'FAKE', 'LOCAL', 'repository_fixture', false, 1440, NULL, NULL, NULL, 'DISABLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000002', 'fake_uppsala_partner', 'Fake Uppsala Partner', 'FAKE', 'LOCAL', 'repository_fixture', false, 1440, NULL, NULL, NULL, 'DISABLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000006', 'uppsala_bostadsformedling_rentals', 'Uppsala Bostadsförmedling — hyresrätter', 'PUBLIC_WEB', 'LOCAL', 'reviewed_fixture', false, 60, NULL, NULL, NULL, 'DISABLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000008', 'homeq_public_uppsala_rentals', 'HomeQ — publik Uppsala-sökning', 'PUBLIC_WEB', 'LOCAL', 'reviewed_public_fixture', false, 60, NULL, NULL, NULL, 'DISABLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO public.sources VALUES ('00000000-0000-0000-0000-000000000009', 'hsb_public_uppsala_rentals', 'HSB — publik Uppsala-sökning', 'PUBLIC_WEB', 'LOCAL', 'reviewed_public_fixture', false, 60, NULL, NULL, NULL, 'DISABLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);


--
-- Data for Name: spatial_features; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: validation_batches; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: geocode_settings; Type: TABLE DATA; Schema: tiger; Owner: -
--



--
-- Data for Name: pagc_gaz; Type: TABLE DATA; Schema: tiger; Owner: -
--



--
-- Data for Name: pagc_lex; Type: TABLE DATA; Schema: tiger; Owner: -
--



--
-- Data for Name: pagc_rules; Type: TABLE DATA; Schema: tiger; Owner: -
--



--
-- Data for Name: topology; Type: TABLE DATA; Schema: topology; Owner: -
--



--
-- Data for Name: layer; Type: TABLE DATA; Schema: topology; Owner: -
--



--
-- Name: cities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.cities_id_seq', 1, true);


--
-- Name: topology_id_seq; Type: SEQUENCE SET; Schema: topology; Owner: -
--

SELECT pg_catalog.setval('topology.topology_id_seq', 1, false);


--
-- Name: address_enrichments address_enrichments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_enrichments
    ADD CONSTRAINT address_enrichments_pkey PRIMARY KEY (id);


--
-- Name: address_enrichments address_enrichments_source_id_address_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_enrichments
    ADD CONSTRAINT address_enrichments_source_id_address_id_key UNIQUE (source_id, address_id);


--
-- Name: address_enrichments address_enrichments_source_id_external_address_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_enrichments
    ADD CONSTRAINT address_enrichments_source_id_external_address_id_key UNIQUE (source_id, external_address_id);


--
-- Name: address_register_unit_links address_register_unit_links_address_enrichment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_register_unit_links
    ADD CONSTRAINT address_register_unit_links_address_enrichment_id_key UNIQUE (address_enrichment_id);


--
-- Name: address_register_unit_links address_register_unit_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_register_unit_links
    ADD CONSTRAINT address_register_unit_links_pkey PRIMARY KEY (id);


--
-- Name: addresses addresses_normalized_address_city_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_normalized_address_city_id_key UNIQUE (normalized_address, city_id);


--
-- Name: addresses addresses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_pkey PRIMARY KEY (id);


--
-- Name: benchmark_observations benchmark_observations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benchmark_observations
    ADD CONSTRAINT benchmark_observations_pkey PRIMARY KEY (id);


--
-- Name: benchmark_observations benchmark_observations_source_id_dataset_key_dimension_key__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benchmark_observations
    ADD CONSTRAINT benchmark_observations_source_id_dataset_key_dimension_key__key UNIQUE (source_id, dataset_key, dimension_key, metric_key, period);


--
-- Name: cities cities_municipality_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cities
    ADD CONSTRAINT cities_municipality_code_key UNIQUE (municipality_code);


--
-- Name: cities cities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cities
    ADD CONSTRAINT cities_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: events events_raw_item_id_event_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_raw_item_id_event_type_key UNIQUE (raw_item_id, event_type);


--
-- Name: housing_provider_cities housing_provider_cities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.housing_provider_cities
    ADD CONSTRAINT housing_provider_cities_pkey PRIMARY KEY (provider_id, city_id);


--
-- Name: housing_providers housing_providers_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.housing_providers
    ADD CONSTRAINT housing_providers_key_key UNIQUE (key);


--
-- Name: housing_providers housing_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.housing_providers
    ADD CONSTRAINT housing_providers_pkey PRIMARY KEY (id);


--
-- Name: listing_measurements listing_measurements_listing_id_metric_rule_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_measurements
    ADD CONSTRAINT listing_measurements_listing_id_metric_rule_version_key UNIQUE (listing_id, metric, rule_version);


--
-- Name: listing_measurements listing_measurements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_measurements
    ADD CONSTRAINT listing_measurements_pkey PRIMARY KEY (id);


--
-- Name: pilot_signal_activity pilot_signal_activity_pilot_key_signal_id_cohort_version_sc_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_activity
    ADD CONSTRAINT pilot_signal_activity_pilot_key_signal_id_cohort_version_sc_key UNIQUE (pilot_key, signal_id, cohort_version, score_rule_version, cohort_as_of_date, activity_type);


--
-- Name: pilot_signal_activity pilot_signal_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_activity
    ADD CONSTRAINT pilot_signal_activity_pkey PRIMARY KEY (id);


--
-- Name: pilot_signal_feedback pilot_signal_feedback_pilot_key_signal_id_cohort_version_sc_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_feedback
    ADD CONSTRAINT pilot_signal_feedback_pilot_key_signal_id_cohort_version_sc_key UNIQUE (pilot_key, signal_id, cohort_version, score_rule_version, cohort_as_of_date);


--
-- Name: pilot_signal_feedback pilot_signal_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_feedback
    ADD CONSTRAINT pilot_signal_feedback_pkey PRIMARY KEY (id);


--
-- Name: properties properties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_pkey PRIMARY KEY (id);


--
-- Name: provider_channels provider_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_channels
    ADD CONSTRAINT provider_channels_pkey PRIMARY KEY (id);


--
-- Name: provider_channels provider_channels_provider_id_city_id_channel_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_channels
    ADD CONSTRAINT provider_channels_provider_id_city_id_channel_key_key UNIQUE (provider_id, city_id, channel_key);


--
-- Name: raw_items raw_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_items
    ADD CONSTRAINT raw_items_pkey PRIMARY KEY (id);


--
-- Name: raw_items raw_items_source_id_source_item_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_items
    ADD CONSTRAINT raw_items_source_id_source_item_id_key UNIQUE (source_id, source_item_id);


--
-- Name: rental_listing_classifications rental_listing_classifications_listing_id_tag_rule_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_classifications
    ADD CONSTRAINT rental_listing_classifications_listing_id_tag_rule_version_key UNIQUE (listing_id, tag, rule_version);


--
-- Name: rental_listing_classifications rental_listing_classifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_classifications
    ADD CONSTRAINT rental_listing_classifications_pkey PRIMARY KEY (id);


--
-- Name: rental_listing_revisions rental_listing_revisions_listing_id_operation_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_revisions
    ADD CONSTRAINT rental_listing_revisions_listing_id_operation_key_key UNIQUE (listing_id, operation_key);


--
-- Name: rental_listing_revisions rental_listing_revisions_listing_id_revision_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_revisions
    ADD CONSTRAINT rental_listing_revisions_listing_id_revision_number_key UNIQUE (listing_id, revision_number);


--
-- Name: rental_listing_revisions rental_listing_revisions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_revisions
    ADD CONSTRAINT rental_listing_revisions_pkey PRIMARY KEY (id);


--
-- Name: rental_listings rental_listings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listings
    ADD CONSTRAINT rental_listings_pkey PRIMARY KEY (id);


--
-- Name: rental_listings rental_listings_source_id_source_item_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listings
    ADD CONSTRAINT rental_listings_source_id_source_item_id_key UNIQUE (source_id, source_item_id);


--
-- Name: rental_projects rental_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_projects
    ADD CONSTRAINT rental_projects_pkey PRIMARY KEY (id);


--
-- Name: rental_projects rental_projects_raw_item_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_projects
    ADD CONSTRAINT rental_projects_raw_item_id_key UNIQUE (raw_item_id);


--
-- Name: score_activations score_activations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_activations
    ADD CONSTRAINT score_activations_pkey PRIMARY KEY (id);


--
-- Name: score_components score_components_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_components
    ADD CONSTRAINT score_components_pkey PRIMARY KEY (id);


--
-- Name: score_definitions score_definitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_definitions
    ADD CONSTRAINT score_definitions_pkey PRIMARY KEY (id);


--
-- Name: score_evaluation_runs score_evaluation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_evaluation_runs
    ADD CONSTRAINT score_evaluation_runs_pkey PRIMARY KEY (id);


--
-- Name: score_runs score_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_runs
    ADD CONSTRAINT score_runs_pkey PRIMARY KEY (id);


--
-- Name: signal_dimension_evaluations signal_dimension_evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_dimension_evaluations
    ADD CONSTRAINT signal_dimension_evaluations_pkey PRIMARY KEY (id);


--
-- Name: signal_evidence signal_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_evidence
    ADD CONSTRAINT signal_evidence_pkey PRIMARY KEY (signal_id, event_id);


--
-- Name: signal_feature_snapshots signal_feature_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_feature_snapshots
    ADD CONSTRAINT signal_feature_snapshots_pkey PRIMARY KEY (id);


--
-- Name: signal_feature_snapshots signal_feature_snapshots_signal_id_feature_schema_revision__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_feature_snapshots
    ADD CONSTRAINT signal_feature_snapshots_signal_id_feature_schema_revision__key UNIQUE (signal_id, feature_schema_revision, as_of_date, payload_hash);


--
-- Name: signal_outcomes signal_outcomes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_outcomes
    ADD CONSTRAINT signal_outcomes_pkey PRIMARY KEY (id);


--
-- Name: signal_outcomes signal_outcomes_signal_id_outcome_type_dedupe_key_rule_vers_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_outcomes
    ADD CONSTRAINT signal_outcomes_signal_id_outcome_type_dedupe_key_rule_vers_key UNIQUE (signal_id, outcome_type, dedupe_key, rule_version);


--
-- Name: signal_score_evaluations signal_score_evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_score_evaluations
    ADD CONSTRAINT signal_score_evaluations_pkey PRIMARY KEY (id);


--
-- Name: signal_score_evaluations signal_score_evaluations_run_id_signal_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_score_evaluations
    ADD CONSTRAINT signal_score_evaluations_run_id_signal_id_key UNIQUE (run_id, signal_id);


--
-- Name: signal_validations signal_validations_batch_id_signal_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_validations
    ADD CONSTRAINT signal_validations_batch_id_signal_id_key UNIQUE (batch_id, signal_id);


--
-- Name: signal_validations signal_validations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_validations
    ADD CONSTRAINT signal_validations_pkey PRIMARY KEY (id);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: signals signals_property_id_signal_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_property_id_signal_type_key UNIQUE (property_id, signal_type);


--
-- Name: source_cities source_cities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_cities
    ADD CONSTRAINT source_cities_pkey PRIMARY KEY (source_id, city_id);


--
-- Name: source_runs source_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_runs
    ADD CONSTRAINT source_runs_pkey PRIMARY KEY (id);


--
-- Name: sources sources_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_key_key UNIQUE (key);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- Name: spatial_features spatial_features_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spatial_features
    ADD CONSTRAINT spatial_features_pkey PRIMARY KEY (id);


--
-- Name: spatial_features spatial_features_source_id_dataset_key_source_item_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spatial_features
    ADD CONSTRAINT spatial_features_source_id_dataset_key_source_item_id_key UNIQUE (source_id, dataset_key, source_item_id);


--
-- Name: rental_projects uq_rental_projects_source_item; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_projects
    ADD CONSTRAINT uq_rental_projects_source_item UNIQUE (source_id, source_item_id);


--
-- Name: score_definitions uq_score_definitions_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_definitions
    ADD CONSTRAINT uq_score_definitions_identity UNIQUE (dimension, definition_revision, parameter_hash, feature_schema_revision, engine_revision);


--
-- Name: score_evaluation_runs uq_score_evaluation_input; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_evaluation_runs
    ADD CONSTRAINT uq_score_evaluation_input UNIQUE (city_id, candidate_rule_version, input_fingerprint);


--
-- Name: score_runs uq_score_runs_replay_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_runs
    ADD CONSTRAINT uq_score_runs_replay_identity UNIQUE (city_id, as_of_date, feature_schema_revision, definition_set_hash, population_fingerprint);


--
-- Name: signal_dimension_evaluations uq_signal_dimension_evaluations_result; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_dimension_evaluations
    ADD CONSTRAINT uq_signal_dimension_evaluations_result UNIQUE (run_id, signal_id, dimension);


--
-- Name: validation_batches validation_batches_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.validation_batches
    ADD CONSTRAINT validation_batches_name_key UNIQUE (name);


--
-- Name: validation_batches validation_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.validation_batches
    ADD CONSTRAINT validation_batches_pkey PRIMARY KEY (id);


--
-- Name: ix_address_enrichments_external; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_address_enrichments_external ON public.address_enrichments USING btree (external_address_id);


--
-- Name: ix_address_register_unit_links_designation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_address_register_unit_links_designation ON public.address_register_unit_links USING btree (designation);


--
-- Name: ix_address_register_unit_links_external; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_address_register_unit_links_external ON public.address_register_unit_links USING btree (external_register_unit_id);


--
-- Name: ix_addresses_geometry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_addresses_geometry ON public.addresses USING gist (geometry);


--
-- Name: ix_benchmark_observations_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_benchmark_observations_lookup ON public.benchmark_observations USING btree (municipality_code, dataset_key, period);


--
-- Name: ix_listing_measurements_metric_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_listing_measurements_metric_status ON public.listing_measurements USING btree (metric, status);


--
-- Name: ix_pilot_signal_activity_signal_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pilot_signal_activity_signal_id ON public.pilot_signal_activity USING btree (signal_id);


--
-- Name: ix_pilot_signal_feedback_signal_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pilot_signal_feedback_signal_id ON public.pilot_signal_feedback USING btree (signal_id);


--
-- Name: ix_rental_listing_classifications_tag; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rental_listing_classifications_tag ON public.rental_listing_classifications USING btree (tag);


--
-- Name: ix_rental_listing_revisions_as_of; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rental_listing_revisions_as_of ON public.rental_listing_revisions USING btree (listing_id, valid_from, revision_number);


--
-- Name: ix_rental_listings_project_source_item; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rental_listings_project_source_item ON public.rental_listings USING btree (project_source_item_id);


--
-- Name: ix_rental_listings_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rental_listings_provider ON public.rental_listings USING btree (upstream_provider_key);


--
-- Name: ix_rental_listings_status_deadline; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rental_listings_status_deadline ON public.rental_listings USING btree (status, application_deadline);


--
-- Name: ix_rental_projects_provider_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rental_projects_provider_status ON public.rental_projects USING btree (upstream_provider_key, status);


--
-- Name: ix_score_activations_scope_city; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_activations_scope_city ON public.score_activations USING btree (scope_key, city_id, activated_at);


--
-- Name: ix_score_definitions_dimension_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_definitions_dimension_status ON public.score_definitions USING btree (dimension, status);


--
-- Name: ix_score_evaluation_runs_rules_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_evaluation_runs_rules_created ON public.score_evaluation_runs USING btree (candidate_rule_version, created_at);


--
-- Name: ix_score_runs_city_date_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_runs_city_date_created ON public.score_runs USING btree (city_id, as_of_date, created_at);


--
-- Name: ix_signal_dimension_evaluations_run_signal; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_dimension_evaluations_run_signal ON public.signal_dimension_evaluations USING btree (run_id, signal_id);


--
-- Name: ix_signal_feature_snapshots_as_of_schema; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_feature_snapshots_as_of_schema ON public.signal_feature_snapshots USING btree (as_of_date, feature_schema_revision);


--
-- Name: ix_signal_feature_snapshots_signal_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_feature_snapshots_signal_id ON public.signal_feature_snapshots USING btree (signal_id);


--
-- Name: ix_signal_outcomes_type_observed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_outcomes_type_observed ON public.signal_outcomes USING btree (outcome_type, observed_at);


--
-- Name: ix_signal_score_evaluations_run_delta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_score_evaluations_run_delta ON public.signal_score_evaluations USING btree (run_id, delta);


--
-- Name: ix_signal_validations_batch_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_validations_batch_review ON public.signal_validations USING btree (batch_id, review_status);


--
-- Name: ix_spatial_features_activity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_spatial_features_activity ON public.spatial_features USING btree (source_id, subtype_code, activity_code);


--
-- Name: ix_spatial_features_geometry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_spatial_features_geometry ON public.spatial_features USING gist (geometry);


--
-- Name: ix_spatial_features_modified; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_spatial_features_modified ON public.spatial_features USING btree (source_id, source_modified_at DESC);


--
-- Name: uq_pilot_activity_dimension_snapshot; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_pilot_activity_dimension_snapshot ON public.pilot_signal_activity USING btree (pilot_key, signal_id, cohort_version, dimension_scope_key, score_run_id, cohort_as_of_date, activity_type);


--
-- Name: uq_pilot_feedback_dimension_snapshot; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_pilot_feedback_dimension_snapshot ON public.pilot_signal_feedback USING btree (pilot_key, signal_id, cohort_version, dimension_scope_key, score_run_id, cohort_as_of_date);


--
-- Name: uq_score_activations_active_scope_dimension; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_score_activations_active_scope_dimension ON public.score_activations USING btree (scope_key, city_id, dimension) WHERE (retired_at IS NULL);


--
-- Name: rental_listing_revisions rental_listing_revisions_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER rental_listing_revisions_append_only BEFORE DELETE OR UPDATE ON public.rental_listing_revisions FOR EACH ROW EXECUTE FUNCTION public.reject_rental_listing_revision_mutation();


--
-- Name: address_enrichments address_enrichments_address_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_enrichments
    ADD CONSTRAINT address_enrichments_address_id_fkey FOREIGN KEY (address_id) REFERENCES public.addresses(id);


--
-- Name: address_enrichments address_enrichments_raw_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_enrichments
    ADD CONSTRAINT address_enrichments_raw_item_id_fkey FOREIGN KEY (raw_item_id) REFERENCES public.raw_items(id);


--
-- Name: address_enrichments address_enrichments_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_enrichments
    ADD CONSTRAINT address_enrichments_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: address_register_unit_links address_register_unit_links_address_enrichment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.address_register_unit_links
    ADD CONSTRAINT address_register_unit_links_address_enrichment_id_fkey FOREIGN KEY (address_enrichment_id) REFERENCES public.address_enrichments(id) ON DELETE CASCADE;


--
-- Name: addresses addresses_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- Name: benchmark_observations benchmark_observations_raw_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benchmark_observations
    ADD CONSTRAINT benchmark_observations_raw_item_id_fkey FOREIGN KEY (raw_item_id) REFERENCES public.raw_items(id);


--
-- Name: benchmark_observations benchmark_observations_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benchmark_observations
    ADD CONSTRAINT benchmark_observations_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: events events_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id);


--
-- Name: events events_raw_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_raw_item_id_fkey FOREIGN KEY (raw_item_id) REFERENCES public.raw_items(id);


--
-- Name: events events_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: pilot_signal_activity fk_pilot_signal_activity_score_run_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_activity
    ADD CONSTRAINT fk_pilot_signal_activity_score_run_id FOREIGN KEY (score_run_id) REFERENCES public.score_runs(id) ON DELETE RESTRICT;


--
-- Name: pilot_signal_feedback fk_pilot_signal_feedback_score_run_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_feedback
    ADD CONSTRAINT fk_pilot_signal_feedback_score_run_id FOREIGN KEY (score_run_id) REFERENCES public.score_runs(id) ON DELETE RESTRICT;


--
-- Name: signal_evidence fk_signal_evidence_superseded_by_event_id_events; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_evidence
    ADD CONSTRAINT fk_signal_evidence_superseded_by_event_id_events FOREIGN KEY (superseded_by_event_id) REFERENCES public.events(id);


--
-- Name: signals fk_signals_superseded_by_signal_id_signals; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT fk_signals_superseded_by_signal_id_signals FOREIGN KEY (superseded_by_signal_id) REFERENCES public.signals(id);


--
-- Name: validation_batches fk_validation_batches_score_run_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.validation_batches
    ADD CONSTRAINT fk_validation_batches_score_run_id FOREIGN KEY (score_run_id) REFERENCES public.score_runs(id) ON DELETE RESTRICT;


--
-- Name: housing_provider_cities housing_provider_cities_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.housing_provider_cities
    ADD CONSTRAINT housing_provider_cities_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- Name: housing_provider_cities housing_provider_cities_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.housing_provider_cities
    ADD CONSTRAINT housing_provider_cities_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.housing_providers(id);


--
-- Name: listing_measurements listing_measurements_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_measurements
    ADD CONSTRAINT listing_measurements_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.rental_listings(id) ON DELETE CASCADE;


--
-- Name: pilot_signal_activity pilot_signal_activity_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_activity
    ADD CONSTRAINT pilot_signal_activity_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: pilot_signal_feedback pilot_signal_feedback_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilot_signal_feedback
    ADD CONSTRAINT pilot_signal_feedback_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: properties properties_address_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_address_id_fkey FOREIGN KEY (address_id) REFERENCES public.addresses(id);


--
-- Name: provider_channels provider_channels_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_channels
    ADD CONSTRAINT provider_channels_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- Name: provider_channels provider_channels_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_channels
    ADD CONSTRAINT provider_channels_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.housing_providers(id);


--
-- Name: provider_channels provider_channels_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.provider_channels
    ADD CONSTRAINT provider_channels_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: raw_items raw_items_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_items
    ADD CONSTRAINT raw_items_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: rental_listing_classifications rental_listing_classifications_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_classifications
    ADD CONSTRAINT rental_listing_classifications_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.rental_listings(id) ON DELETE CASCADE;


--
-- Name: rental_listing_revisions rental_listing_revisions_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_revisions
    ADD CONSTRAINT rental_listing_revisions_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.rental_listings(id);


--
-- Name: rental_listing_revisions rental_listing_revisions_raw_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_revisions
    ADD CONSTRAINT rental_listing_revisions_raw_item_id_fkey FOREIGN KEY (raw_item_id) REFERENCES public.raw_items(id);


--
-- Name: rental_listing_revisions rental_listing_revisions_source_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listing_revisions
    ADD CONSTRAINT rental_listing_revisions_source_run_id_fkey FOREIGN KEY (source_run_id) REFERENCES public.source_runs(id);


--
-- Name: rental_listings rental_listings_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listings
    ADD CONSTRAINT rental_listings_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id);


--
-- Name: rental_listings rental_listings_raw_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listings
    ADD CONSTRAINT rental_listings_raw_item_id_fkey FOREIGN KEY (raw_item_id) REFERENCES public.raw_items(id);


--
-- Name: rental_listings rental_listings_rental_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listings
    ADD CONSTRAINT rental_listings_rental_project_id_fkey FOREIGN KEY (rental_project_id) REFERENCES public.rental_projects(id);


--
-- Name: rental_listings rental_listings_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_listings
    ADD CONSTRAINT rental_listings_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: rental_projects rental_projects_raw_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_projects
    ADD CONSTRAINT rental_projects_raw_item_id_fkey FOREIGN KEY (raw_item_id) REFERENCES public.raw_items(id);


--
-- Name: rental_projects rental_projects_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_projects
    ADD CONSTRAINT rental_projects_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: score_activations score_activations_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_activations
    ADD CONSTRAINT score_activations_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- Name: score_activations score_activations_decision_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_activations
    ADD CONSTRAINT score_activations_decision_run_id_fkey FOREIGN KEY (decision_run_id) REFERENCES public.score_runs(id) ON DELETE RESTRICT;


--
-- Name: score_activations score_activations_definition_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_activations
    ADD CONSTRAINT score_activations_definition_id_fkey FOREIGN KEY (definition_id) REFERENCES public.score_definitions(id) ON DELETE RESTRICT;


--
-- Name: score_components score_components_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_components
    ADD CONSTRAINT score_components_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: score_evaluation_runs score_evaluation_runs_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_evaluation_runs
    ADD CONSTRAINT score_evaluation_runs_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- Name: score_runs score_runs_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_runs
    ADD CONSTRAINT score_runs_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- Name: signal_dimension_evaluations signal_dimension_evaluations_definition_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_dimension_evaluations
    ADD CONSTRAINT signal_dimension_evaluations_definition_id_fkey FOREIGN KEY (definition_id) REFERENCES public.score_definitions(id) ON DELETE RESTRICT;


--
-- Name: signal_dimension_evaluations signal_dimension_evaluations_feature_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_dimension_evaluations
    ADD CONSTRAINT signal_dimension_evaluations_feature_snapshot_id_fkey FOREIGN KEY (feature_snapshot_id) REFERENCES public.signal_feature_snapshots(id) ON DELETE RESTRICT;


--
-- Name: signal_dimension_evaluations signal_dimension_evaluations_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_dimension_evaluations
    ADD CONSTRAINT signal_dimension_evaluations_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.score_runs(id) ON DELETE CASCADE;


--
-- Name: signal_dimension_evaluations signal_dimension_evaluations_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_dimension_evaluations
    ADD CONSTRAINT signal_dimension_evaluations_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signal_evidence signal_evidence_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_evidence
    ADD CONSTRAINT signal_evidence_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id);


--
-- Name: signal_evidence signal_evidence_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_evidence
    ADD CONSTRAINT signal_evidence_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signal_feature_snapshots signal_feature_snapshots_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_feature_snapshots
    ADD CONSTRAINT signal_feature_snapshots_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signal_outcomes signal_outcomes_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_outcomes
    ADD CONSTRAINT signal_outcomes_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE SET NULL;


--
-- Name: signal_outcomes signal_outcomes_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_outcomes
    ADD CONSTRAINT signal_outcomes_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.rental_listings(id) ON DELETE SET NULL;


--
-- Name: signal_outcomes signal_outcomes_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_outcomes
    ADD CONSTRAINT signal_outcomes_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signal_score_evaluations signal_score_evaluations_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_score_evaluations
    ADD CONSTRAINT signal_score_evaluations_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.score_evaluation_runs(id) ON DELETE CASCADE;


--
-- Name: signal_score_evaluations signal_score_evaluations_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_score_evaluations
    ADD CONSTRAINT signal_score_evaluations_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signal_validations signal_validations_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_validations
    ADD CONSTRAINT signal_validations_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.validation_batches(id) ON DELETE CASCADE;


--
-- Name: signal_validations signal_validations_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_validations
    ADD CONSTRAINT signal_validations_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signals signals_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id);


--
-- Name: source_cities source_cities_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_cities
    ADD CONSTRAINT source_cities_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- Name: source_cities source_cities_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_cities
    ADD CONSTRAINT source_cities_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: source_runs source_runs_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_runs
    ADD CONSTRAINT source_runs_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: spatial_features spatial_features_raw_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spatial_features
    ADD CONSTRAINT spatial_features_raw_item_id_fkey FOREIGN KEY (raw_item_id) REFERENCES public.raw_items(id);


--
-- Name: spatial_features spatial_features_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spatial_features
    ADD CONSTRAINT spatial_features_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id);


--
-- Name: validation_batches validation_batches_city_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.validation_batches
    ADD CONSTRAINT validation_batches_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.cities(id);


--
-- PostgreSQL database dump complete
--
