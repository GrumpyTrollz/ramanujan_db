-- Creating DB
CREATE DATABASE ramanujanv2
    WITH
    OWNER = postgres
;

-- Use DB
\c ramanujanv2

-- Add module for uuid
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Creating tables
CREATE TABLE constant (
	constant_id SERIAL PRIMARY KEY,
	name VARCHAR NOT NULL UNIQUE,
	description VARCHAR,
	value NUMERIC NOT NULL,
	precision INT NOT NULL,
	trust REAL NOT NULL DEFAULT 1,
	artificial INT NOT NULL DEFAULT 0,
	lambda REAL DEFAULT 0,
	delta REAL DEFAULT 0,
	insertion_date timestamp DEFAULT current_timestamp
);

CREATE TABLE cf_family (
	family_id UUID NOT NULL DEFAULT uuid_generate_v1() PRIMARY KEY,
	description VARCHAR,
	constant INT REFERENCES constant (constant_id)
);

CREATE TABLE cf (
	cf_id UUID NOT NULL DEFAULT uuid_generate_v1() PRIMARY KEY,
	partial_numerator NUMERIC[] NOT NULL,
	partial_denominator NUMERIC[] NOT NULL,
	scanned_algo JSONB,

	UNIQUE(partial_numerator, partial_denominator),
	family_id UUID REFERENCES cf_family (family_id)
);

CREATE TABLE continued_fraction_relation (
	source_cf UUID NOT NULL REFERENCES cf (cf_id),
	target_cf UUID NOT NULL REFERENCES cf (cf_id),
	connection_type VARCHAR NOT NULL,
	connection_details INT[] NOT NULL,
	rating REAL DEFAULT 0,
	insertion_date timestamp DEFAULT current_timestamp,
	PRIMARY KEY (source_cf, target_cf)
);

CREATE TABLE cf_constant_connection (
	constant_id INT NOT NULL REFERENCES constant (constant_id),
	cf_id UUID NOT NULL REFERENCES cf (cf_id),
	connection_type VARCHAR NOT NULL,
	connection_details INT[] NOT NULL,
	insertion_date timestamp DEFAULT current_timestamp,
	PRIMARY KEY (constant_id, cf_id)
);

CREATE TABLE relation (
	relation_id UUID NOT NULL DEFAULT uuid_generate_v1() PRIMARY KEY,
	relation_type VARCHAR NOT NULL,
	details INT[] NOT NULL,
	insertion_date timestamp DEFAULT current_timestamp
);

CREATE TABLE constant_in_relation (
	constant_id INT NOT NULL REFERENCES constant (constant_id) ON UPDATE CASCADE ON DELETE CASCADE,
	relation_id UUID NOT NULL REFERENCES relation (relation_id) ON UPDATE CASCADE,
	CONSTRAINT const_relation_pkey PRIMARY KEY (constant_id, relation_id)
);

CREATE TABLE cf_in_relation (
	cf_id UUID NOT NULL REFERENCES cf (cf_id) ON UPDATE CASCADE ON DELETE CASCADE,
	relation_id UUID NOT NULL REFERENCES relation (relation_id) ON UPDATE CASCADE,
	CONSTRAINT cf_relation_pkey PRIMARY KEY (cf_id, relation_id)
);

CREATE TABLE cf_precision (
	cf_id UUID NOT NULL PRIMARY KEY REFERENCES cf (cf_id),
	insertion_date timestamp DEFAULT current_timestamp,
	depth INT NOT NULL,
	precision INT NOT NULL,
	value NUMERIC NOT NULL,
	previous_calc VARCHAR[] NOT NULL,
	general_data JSONB,
	interesting NUMERIC DEFAULT 0,
	update_time timestamp DEFAULT current_timestamp
);
