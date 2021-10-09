import math
import logging
import logging.config
from mpmath.functions.functions import root
import numpy as np
import mpmath
from decimal import Decimal, getcontext
from collections import namedtuple
from dataclasses import dataclass, asdict
from jobs import math_utils
from enum import Enum
import time
import os

from db import ramanujan_db
from db import models

from sqlalchemy.sql.expression import func

getcontext().prec = 2000
mpmath.mp.dps = 2000

BULK_SIZE = 5000
DEPTH = 1200
FR_THRESHOLD = 0.1
CALC_JUMP = 200
REDUCE_JUMP = 100
PRECISION_FILTER = 50
LOGGER_NAME = 'job_logger'

FILTERS = [models.Cf.precision_data == None]

def get_filters(num_denom_factor):
    filters = FILTERS
    if num_denom_factor is not None:
        factor, strict = num_denom_factor
        num_deg = func.cardinality(models.Cf.partial_numerator) - 1
        denom_deg = func.cardinality(models.Cf.partial_denominator) - 1
        if factor > 0:
            low_deg = denom_deg * factor
            high_deg = num_deg
        else:
            low_deg = num_deg * abs(factor)
            high_deg = denom_deg

        if strict:
            new_filter = low_deg == high_deg
        else:
            new_filter = low_deg <= high_deg

        filters = filters + [new_filter]

    return filters

class PrecisionType(Enum):
    HIGH_PREC = 1
    LOW_PREC = 2
    NO_PREC = 3

@dataclass
class CfData:
    an_deg: int = 0
    bn_deg: int = 0
    fr: float = 0
    rational: float = 0
    gamma: float = 0
    delta: float = 0
    lambda_: float = 0
    rounded: bool = False
    original_value: str = ''
    converges: bool = True
    reduction: int = 0

CalcData = namedtuple('CalcData', ['a0', 'b0', 'a1', 'b1'])

class CfCalc(object):
    def __init__(self, num, denom, previous_calc):
        self.num = num
        self.denom = denom
        self.reduction = 1
        if not previous_calc:
            self.data = CalcData(1, 0, CfCalc.calculate_poly_depth(denom, 0), 1)
        else:
            self.data = CalcData(*previous_calc)

    def calc_iter(self, i, try_reduce=True):
        a = CfCalc.calculate_poly_depth(self.num, i+1)
        b = CfCalc.calculate_poly_depth(self.denom, i+1)

        p = b*self.data.a1 + a*self.data.a0
        q = b*self.data.b1 + a*self.data.b0

        data = CalcData(self.data.a1, self.data.b1, p, q)

        if try_reduce:
            gcd_reduce = math.gcd(math.gcd(self.data.a1, self.data.b1), math.gcd(p, q))
            self.reduction *= gcd_reduce
            data = CalcData(self.data.a1 // gcd_reduce, self.data.b1 // gcd_reduce, p // gcd_reduce, q // gcd_reduce)
        
        self.data = data 
        return p, q

    @property
    def value(self):
        return Decimal(self.data.a1) / self.data.b1

    @property
    def precision(self):
        if self.data.b0 == 0 or self.data.b1 == 0:
            return False, 0

        precision = -1 * abs(self.value - Decimal(self.data.a0)/self.data.b0).log10()
        
        if precision != math.inf:
            precision = math.floor(precision)

        return True, precision
    
    def get_calc_data(self):
        return [self.data.a0, self.data.b0, self.data.a1, self.data.b1]

    @staticmethod
    def calculate_poly_depth(coeff_list, n):
        return sum([coeff*n**(len(coeff_list)-1-idx) for idx, coeff in enumerate(coeff_list)])

def get_poly_deg(coeff_list):
    first_nonzero = [i for i,e in enumerate(coeff_list) if e != 0]
    if first_nonzero:
        return len(coeff_list) - 1 - first_nonzero[0]
    else:
        return 0

def check_fr(fr_list):
    for i in range(1, len(fr_list)):
        if abs(fr_list[i] - fr_list[i-1]) < FR_THRESHOLD:
            return 1

    for i in range(2, len(fr_list)):
        if abs(fr_list[i-1] - fr_list[i]) > abs(fr_list[i-2] - fr_list[i-1]):
            return 0

    return 0.5

def check_rational(p, q, num):
    val = mpmath.mpf(p) / mpmath.mpf(q)
    if mpmath.almosteq(p, 0) or mpmath.almosteq(val, 0):
        logging.getLogger(LOGGER_NAME).debug(f'Checking rational that is too close to 0 p={p},q={q}')
        return 1
    
    if mpmath.pslq([val, 1], tol=mpmath.power(10, -100)):
        return 1
    
    integer_roots = math_utils.integer_roots(num)
    for i in integer_roots:
        if i > 0:
            logging.getLogger(LOGGER_NAME).debug(f'numenator has positive integer root, num={num}, root={i}')
            return 1
            
    return 0

def calculate_cf(num, denom, depth_diff, previous_calc=None, verbose=False, skip=1, reduce_jump=False):
    num = [int(i) for i in num]
    denom = [int(i) for i in denom]
    if not reduce_jump:
        reduce_jump = REDUCE_JUMP
    
    precision = 0
    depth = depth_diff
    cf_calc = CfCalc(num, denom, previous_calc)
    
    data = CfData(bn_deg=get_poly_deg(num), an_deg=get_poly_deg(denom))

    fr_calculations = []

    for i in range(0, depth_diff):
        if i % reduce_jump == 0:
            p, q = cf_calc.calc_iter(i)
        else:
            p, q = cf_calc.calc_iter(i, False)

        if i % CALC_JUMP == 0 and i != 0:
            fr_calculations.append(
                    mpmath.log(mpmath.mpf(math.gcd(p, q))) / mpmath.mpf(i) + data.an_deg * (1 - mpmath.log(i))
                    )
    
    can_calc, prec = cf_calc.precision
    if not can_calc:
        logging.getLogger(LOGGER_NAME).debug(f'Cf does not converge since denom is zero: {num}, {denom}')
        data.converges = False
        return math.inf, 0, cf_calc.get_calc_data(), asdict(data), i
    
    value = cf_calc.value
    precision = 2000 if prec == math.inf else prec
    data.fr = check_fr(fr_calculations)
    if mpmath.almosteq(0, mpmath.mpf(p) / mpmath.mpf(q)):
        logging.getLogger(LOGGER_NAME).debug('Rounding to 0')
        data.original_value = str(value)
        data.rounded = True
        value = 0

    data.rational = check_rational(p, q, num)
    data.reduction = cf_calc.reduction

    return value, precision, cf_calc.get_calc_data(), asdict(data), i


def parse_result_type(cf_id, val, precision):
    if val == math.inf:
        logging.getLogger(LOGGER_NAME).debug(f'cf {cf_id} could not be calculated since q goes to 0')
        return PrecisionType.NO_PREC
    else:
        if precision >= PRECISION_FILTER:
            logging.getLogger(LOGGER_NAME).debug(f'cf_id {cf_id} has high precision: {precision}')
            return PrecisionType.HIGH_PREC
        else:
            logging.getLogger(LOGGER_NAME).debug(f'cf_id {cf_id} has low precision: {precision}')
            return PrecisionType.LOW_PREC


def execute_job(cfs):
    logging.config.fileConfig('logging.config', defaults={'log_filename': f'precision_worker_{os.getpid()}'})
    results = []
    prec_types = { PrecisionType.HIGH_PREC: 0, PrecisionType.LOW_PREC: 0, PrecisionType.NO_PREC: 0 }

    for cf in cfs:
        logging.getLogger(LOGGER_NAME).debug(f'calculating for {cf.cf_id}: {cf.partial_numerator}, {cf.partial_denominator}')
        previous_calc = None
        if cf.precision_data:
            logging.getLogger(LOGGER_NAME).debug(f'cf {cf.cf_id} has old precision data')
            previous_calc = cf.precision_data.previous_calc
        start_time = time.time()
        val, precision, calc_data, general_data, real_depth = calculate_cf(cf.partial_numerator, cf.partial_denominator, DEPTH, previous_calc)
        logging.getLogger(LOGGER_NAME).debug(f'calculation of {cf.partial_numerator}, {cf.partial_denominator}, took {time.time() - start_time} seconds')
        prec_types[parse_result_type(cf.cf_id, val, precision)] += 1
        if val == math.inf:
            val = 0
        results.append(models.CfPrecision(cf_id=cf.cf_id, depth=real_depth, precision=precision, value=val, previous_calc=calc_data, general_data=general_data))
    
    logging.getLogger(LOGGER_NAME).info('Done calculation')
    return results, prec_types

def run_query(bulk=0, num_denom_factor=None):
    logging.config.fileConfig('logging.config', defaults={'log_filename': f'precision_manager'})
    db_handle = ramanujan_db.RamanujanDB()

    if not bulk:
        bulk = BULK_SIZE
    logging.getLogger(LOGGER_NAME).info(f'starting to calculate precision for {bulk} cfs')

    queried_data = db_handle.session.query(models.Cf).filter(*get_filters(num_denom_factor)).limit(bulk).all()
    db_handle.session.close()
    logging.getLogger(LOGGER_NAME).info(f'size of batch is {len(queried_data)}')
    return queried_data

def summarize_results(results):
    db_handle = ramanujan_db.RamanujanDB()
    agg_passed = 0
    agg_prec_types = {}
    
    logging.getLogger(LOGGER_NAME).info(f'Committing work')
    for passed_cfs, prec_types in results:
        db_handle.session.add_all(passed_cfs)
        try:
            db_handle.session.commit()
            agg_passed += len(passed_cfs)
            logging.getLogger(LOGGER_NAME).debug('sub commit happenned')
            for k in prec_types.keys():
                if k not in agg_prec_types:
                    agg_prec_types[k] = 0
                agg_prec_types[k] += prec_types[k]
        except Exception as ex:
            logging.getLogger(LOGGER_NAME).info(f'There was an error while committing {ex}')
            db_handle.session.rollback()

    db_handle.session.close()
    logging.getLogger(LOGGER_NAME).info(f'Commit done')
     
    logging.getLogger(LOGGER_NAME).info(f'Calculated precision for: {agg_passed} cfs, which are segmented by: {agg_prec_types}')

def run_one(numerator, denominator, db_handle=None, depth=DEPTH, write_to_db=False, cf_id=None):
    if not db_handle:
        db_handle = ramanujan_db.RamanujanDB()
    precision_data = db_handle.session.query(models.CfPrecision).filter(models.CfPrecision.cf_id == cf_id).one_or_none()

    if not precision_data:

        if not write_to_db:
            cf_id = 0
        val, precision, calc_data, general_data, real_depth = calculate_cf(numerator, denominator, depth)
        if val == math.inf:
            val = 0
            print('Val is 0')
        precision_data = models.CfPrecision(cf_id=cf_id, depth=real_depth, precision=precision, value=val, previous_calc=calc_data,
                       general_data=general_data)
        if write_to_db:
            db_handle.session.add_all([precision_data])
            db_handle.session.commit()
#        db_handle.session.close()
    return precision_data
