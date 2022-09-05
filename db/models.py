# coding: utf-8
from sqlalchemy import ARRAY, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint, text, Table
from sqlalchemy.sql.sqltypes import BigInteger
from sqlalchemy.types import Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


class Constant(Base):
    __tablename__ = 'constant'

    constant_id = Column(Integer, primary_key=True, server_default=text("nextval('constant_constant_id_seq'::regclass)"))
    name = Column(String, nullable=False, unique=True)
    description = Column(String)
    value = Column(Numeric, nullable=False)
    precision = Column(Integer, nullable=False)
    trust = Column(Float, nullable=False, server_default=text("1"))
    artificial = Column(Integer, nullable=False, server_default=text("0"))
    _lambda = Column('lambda', Float, server_default=text("0"))
    delta = Column(Float, server_default=text("0"))
    insertion_date = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class CfFamily(Base):
    __tablename__ = 'cf_family'

    family_id = Column(UUID, primary_key=True, server_default=text("uuid_generate_v1()"))
    description = Column(String)
    constant = Column(ForeignKey('constant.constant_id'))

    constant1 = relationship('Constant')


class Cf(Base):
    __tablename__ = 'cf'
    __table_args__ = (
        UniqueConstraint('partial_numerator', 'partial_denominator'),
    )

    cf_id = Column(UUID, primary_key=True, server_default=text("uuid_generate_v1()"))
    partial_numerator = Column(ARRAY(Numeric()), nullable=False)
    partial_denominator = Column(ARRAY(Numeric()), nullable=False)
    family_id = Column(ForeignKey('cf_family.family_id'))
    scanned_algo = Column(JSONB(astext_type=Text()))

    family = relationship('CfFamily')
    precision_data = relationship('CfPrecision', uselist=False, lazy='joined')


class CfPrecision(Base):
    __tablename__ = 'cf_precision'

    cf_id = Column(ForeignKey('cf.cf_id'), primary_key=True)
    insertion_date = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    depth = Column(Integer, nullable=False)
    precision = Column(Integer, nullable=False)
    value = Column(Numeric, nullable=False)
    previous_calc = Column(ARRAY(String()), nullable=False)
    general_data = Column(JSONB(astext_type=Text()))
    interesting = Column(Numeric, server_default=text("0"))
    update_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class CfConstantConnection(Base):
    __tablename__ = 'cf_constant_connection'

    constant_id = Column(ForeignKey('constant.constant_id'), primary_key=True, nullable=False)
    cf_id = Column(ForeignKey('cf.cf_id'), primary_key=True, nullable=False)
    connection_type = Column(String, nullable=False)
    connection_details = Column(ARRAY(Integer()), nullable=False)
    insertion_date = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    cf = relationship('Cf')
    constant = relationship('Constant')


constant_in_relation_table = Table(
    "constant_in_relation",
    Base.metadata,
    Column('constant_id', ForeignKey('constant.constant_id'), primary_key=True),
    Column('relation_id', ForeignKey('relation.relation_id'), primary_key=True),
)


cf_in_relation_table = Table(
    "cf_in_relation",
    Base.metadata,
    Column('cf_id', ForeignKey('cf.cf_id'), primary_key=True),
    Column('relation_id', ForeignKey('relation.relation_id'), primary_key=True),
)


class Relation(Base):
    __tablename__ = 'relation'

    relation_id = Column(UUID, primary_key=True, server_default=text("uuid_generate_v1()"))
    relation_type = Column(String, nullable=False)
    # if this needs an order on the constants and cfs (and it probably will), it is
    # determined by ascending order on the constant_ids, and then ascending order on the cf_ids
    # generally going to be of the form: (polydegree, innerdegree, argcount, (nullvector))
    details = Column(ARRAY(Integer()), nullable=False)
    insertion_date = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    cfs = relationship('Cf', secondary=cf_in_relation_table)
    constants = relationship('Constant', secondary=constant_in_relation_table)


class ContinuedFractionRelation(Base):
    __tablename__ = 'continued_fraction_relation'

    source_cf = Column(ForeignKey('cf.cf_id'), primary_key=True, nullable=False)
    target_cf = Column(ForeignKey('cf.cf_id'), primary_key=True, nullable=False)
    connection_type = Column(String, nullable=False)
    connection_details = Column(ARRAY(Integer()), nullable=False)
    rating = Column(Float, server_default=text("0"))
    insertion_date = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    cf = relationship('Cf', primaryjoin='ContinuedFractionRelation.source_cf == Cf.cf_id')
    cf1 = relationship('Cf', primaryjoin='ContinuedFractionRelation.target_cf == Cf.cf_id')
