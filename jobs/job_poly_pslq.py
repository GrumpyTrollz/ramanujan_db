'''
Finds polynomial relations between constants and/or continued fractions in the DB, using PSLQ.

Configured as such:
'bulk': How many CFs to scan. (since there can be many in the DB)
'num_denom_factor': Tuple of the form (factor: int, strict: bool). Every PCF in the DB can be characterized
                    by the ratio between the degrees of its polynomials, so factor is either the exact ratio
                    of PCFs to look for if strict, else the greatest ratio to look for (meaning lower ratios
                    will also be scanned).
'num_of_consts': Tuple of the form (num: int, strict: bool), num is how many constants to relate, and
                 if strict then only relate exactly num constants, else relate 1..num constants.
                 Since the code eliminates redundant constants, it may still find relations using
                 less constants, so in practice there will probably be little benefit to nonstrict.
'num_of_cfs': Similar to num_of_constants, but with CFs instead.
'degree': Tuple of the form (polydegree: int, innerdegree: int). All relations are structured like
          multivariate polynomials over the constants and CFs, of degree polydegree with a maximum
          exponent of innerdegree. For example, a 2-variable polynomial of degree (2,1) will be of
          the form a+bx+cy+dxy (note the lack of x^2 and y^2), and a 4-variable polynomial of degree
          (3,1) will be of the form:
              a + bx+cy+dz+ew + fxy+gxz+hxw+iyz+jyw+kzw + lxyz+mxyw+nxzw+oyzw
          Note here the lack of any single variable with an exponent greater than 1, and also the lack of xyzw.
'use_artificial': Some constants are considered "artificial" for one reason or another, say they're easily related
                  to other constants. Whatever the reason, if this is True then the code is allowed to use artificial
                  constants when checking relations, otherwise it's not allowed to.

Examples:
    'num_of_consts': (1, True), 'num_of_cfs': (1, True), 'degree': (2, 1)
        Replicates the old single-constant 'job_const_cf_pslq'.
    'num_of_consts': (0, True), 'num_of_cfs': (2, True), 'degree': (2, 1)
        Replicates 'job_cf_to_cf_pslq'.
    'num_of_consts': (n, *), 'num_of_cfs': (m, *), 'degree': (n+m, 1)
        Find general multilinear relations. (for any nonnegative integers n,m)
'''
from db import models, ramanujan_db
import mpmath as mp
import time
from sqlalchemy import Integer, or_, Float
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.expression import func
from jobs import pslq_utils
import logging
import logging.config
import sys
import os
from itertools import chain, combinations, combinations_with_replacement, takewhile
from collections import Counter
from functools import reduce
from operator import mul
import traceback

mp.mp.dps = 2000

EXECUTE_NEEDS_ARGS = True

ALGORITHM_NAME = 'POLYNOMIAL_PSLQ'
LOGGER_NAME = 'job_logger'
BULK_SIZE = 500
DEFAULT_NUM_OF_CONSTANTS = (1, True)
DEFAULT_NUM_OF_CFS = (1, True)
DEFAULT_DEGREE = (2, 1)
DEFAULT_USE_ARTIFICIAL = False

FILTERS = [
        models.Cf.precision_data != None,
        models.Cf.precision_data.has(models.CfPrecision.precision > 100),
        models.Cf.precision_data.has(models.CfPrecision.general_data != None),
        models.Cf.precision_data.has(models.CfPrecision.general_data['rational'].cast(Float) == 0.0),
        or_(models.Cf.scanned_algo == None, ~models.Cf.scanned_algo.has_key(ALGORITHM_NAME))
        ]

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

        filters = [new_filter] + filters

    return filters 

def poly_check(values, exponents):
    if 1 in values:
        return None # solely for backwards-compatibility. We don't need 1 in the DB!
    poly = [mp.mpf(str(reduce(mul, (values[i] ** exp[i] for i in range(len(values))), 1))) for exp in exponents]
    result = pslq_utils.find_null_polynomial(poly)
    
    if result:
        logging.getLogger(LOGGER_NAME).info('Found relation')

    return result

def compress_relation(result, cfs, consts, exponents, degree):
    # will need to use later, so evaluating into lists
    logging.getLogger(LOGGER_NAME).info(f'Original relation is {result}')
    
    indices_per_var = list(list(i[0] for i in enumerate(exponents) if i[1][j]) for j in range(len(cfs)+len(consts)))
    redundant_vars = list(i[0] for i in enumerate(indices_per_var) if not any(result[j] for j in i[1]))
    redundant_coeffs = set()
    for redundant_var in redundant_vars: # remove redundant variables
        logging.getLogger(LOGGER_NAME).info(f'Removing redundant variable #{redundant_var}')
        redundant_coeffs |= set(indices_per_var[redundant_var])
        if redundant_var >= len(consts):
            cfs = cfs[:redundant_var - len(consts)] + cfs[redundant_var - len(consts) + 1:]
        else:
            consts = consts[:redundant_var] + consts[redundant_var + 1:]
    
    polydegree, innerdegree = degree # remove redundant degrees
    indices_per_polydegree = list(list(i[0] for i in enumerate(exponents) if sum(i[1].values())==j) for j in range(polydegree+1))
    redundant_polydegrees = list(i[0] for i in enumerate(indices_per_polydegree) if not any(result[j] for j in i[1]))
    redundant_polydegrees = list(takewhile(lambda x: sum(x) == polydegree, enumerate(sorted(redundant_polydegrees, reverse=True))))
    if redundant_polydegrees:
        polydegree = redundant_polydegrees[-1][1] - 1
    redundant_coeffs.update(*indices_per_polydegree[polydegree+1:])
    
    indices_per_innerdegree = list(list(i[0] for i in enumerate(exponents) if max(i[1].values(), default=0)==j) for j in range(innerdegree+1))
    redundant_innerdegrees = list(i[0] for i in enumerate(indices_per_innerdegree) if not any(result[j] for j in i[1]))
    redundant_innerdegrees = list(takewhile(lambda x: sum(x) == innerdegree, enumerate(sorted(redundant_innerdegrees, reverse=True))))
    if redundant_innerdegrees:
        innerdegree = redundant_innerdegrees[-1][1] - 1
    redundant_coeffs.update(*indices_per_innerdegree[innerdegree+1:])
    
    degree = [polydegree, innerdegree]
    logging.getLogger(LOGGER_NAME).info(f'True degree is {degree}')
    for i in sorted(redundant_coeffs, reverse=True):
        del result[i]
    
    logging.getLogger(LOGGER_NAME).info(f'Compressed relation is {result}')

    # TODO now also manually test for smaller sub-relations! PSLQ is only guaranteed to return
    # a small norm, but not guaranteed to return a 1-dimensional relation! see for example pslq([1,3,5])

    return models.Relation(relation_type=ALGORITHM_NAME, details=degree+result, cfs=list(cfs), constants=list(consts))

def check_cfs(cfs, constants, num_of_consts, exponents, degree, use_artificial, existing):
    logging.getLogger(LOGGER_NAME).info(f'checking cfs: {[(cf.partial_numerator, cf.partial_denominator) for cf in cfs]}')
    relations = []
    if not use_artificial: # just this line caused me so much trouble... doesn't seem like SQL handles booleans too well
        constants = constants.filter(models.Constant.artificial == 0)
    num, strict = num_of_consts # if strict then only check subsets of exactly num size, else check subsets of size 1..num
    subsets = combinations(constants, num) if strict else chain.from_iterable(combinations(constants, n) for n in range(1,num+1))
    subsets = list(subsets) # weird python idiosyncrasies mean this must be evaluated before being iterated on again
    subsets = (consts for consts in subsets if not any(r for r in existing if set(c.constant_id for c in r.constants) <= set(c.constant_id for c in consts)))
    for consts in subsets:
        logging.getLogger(LOGGER_NAME).debug(f'checking consts {[const.name for const in consts]}')
        mp.mp.dps = min([const.precision for const in consts] + [cf.precision_data.precision for cf in cfs]) * 9 // 10
        result = poly_check([const.value for const in consts]
                            + [mp.mpf(str(cf.precision_data.previous_calc[2])) / mp.mpf(str(cf.precision_data.previous_calc[3])) for cf in cfs],
                            exponents)
        if result:
            if relations: # TODO: Report because we found 2 different constants
                logging.getLogger(LOGGER_NAME).critical(f'found connection to multiple constants!!!')
            relations.append(compress_relation(result, cfs, consts, exponents, degree))
    
    return relations

def run_query(bulk=0, num_denom_factor=None, num_of_consts=None, num_of_cfs=None, degree=None, use_artificial=False):
    logging.config.fileConfig('logging.config', defaults={'log_filename': f'pslq_const_manager'})
    bulk = bulk if bulk else BULK_SIZE
    logging.getLogger(LOGGER_NAME).debug(f'Starting to check relations, using PCF bulk size {bulk}')
    db_handle = ramanujan_db.RamanujanDB()
    results = db_handle.session.query(models.Cf).filter(*get_filters(num_denom_factor)).order_by(func.random()).limit(bulk).all()
    # apparently postgresql is really slow with the order_by(random) part,
    # but on 1000 CFs it only takes 1 second, which imo is worth it since
    # that allows us more variety in testing the CFs
    db_handle.session.close()
    logging.getLogger(LOGGER_NAME).info(f'size of batch is {len(results)}')
    return results

def execute_job(query_data, bulk=0, num_denom_factor=None, num_of_consts=None, num_of_cfs=None, degree=None, use_artificial=False):
    try:
        logging.config.fileConfig('logging.config', defaults={'log_filename': f'pslq_const_worker_{os.getpid()}'})
        num_of_consts = num_of_consts if num_of_consts else DEFAULT_NUM_OF_CONSTANTS
        num_of_cfs = num_of_cfs if num_of_cfs else DEFAULT_NUM_OF_CFS
        degree = degree if degree else DEFAULT_DEGREE
        use_artificial = use_artificial if use_artificial else DEFAULT_USE_ARTIFICIAL # kinda redundant, but whatever
        logging.getLogger(LOGGER_NAME).info(f'checking against {num_of_consts} constants and {num_of_cfs} PCFs at a time, using degree-{degree} relations')
        if degree[0] > (num_of_consts[0] + num_of_cfs[0]) * degree[1]:
            degree = ((num_of_consts[0] + num_of_cfs[0]) * degree[1], degree[1])
            logging.getLogger(LOGGER_NAME).info(f'redundant degree detected! reducing to {degree}')
        
        polydegree, innerdegree = degree
        exponents = list(c for c in map(Counter, chain.from_iterable(combinations_with_replacement(range(num_of_consts[0] + num_of_cfs[0]), i) for i in range(polydegree+1)))
                         if not any(i for i in c.values() if i > innerdegree))
        db_handle = ramanujan_db.RamanujanDB()
        relations = []
        num, strict = num_of_cfs
        cf_subsets = combinations(query_data, num) if strict else chain.from_iterable(combinations(query_data, n) for n in range(1,num+1))
        for cfs in cf_subsets:
            # evaluate once to reuse over all subsets of constants
            existing = list(r for r in db_handle.session.query(models.Relation).all() + relations
                            if set(c.cf_id for c in r.cfs) <= set(c.cf_id for c in cfs) and r.details[0] <= polydegree and r.details[1] <= innerdegree)
            new_relations = check_cfs(cfs, db_handle.constants, num_of_consts, exponents, degree, use_artificial, existing)
            if new_relations:
                relations += new_relations
            for cf in cfs:
                if not cf.scanned_algo:
                    cf.scanned_algo = dict()
                cf.scanned_algo[ALGORITHM_NAME] = int(time.time())
                # for postgres < 9.4
                flag_modified(cf, 'scanned_algo')
            db_handle.session.add_all(cfs)
        logging.getLogger(LOGGER_NAME).info(f'finished - found {len(relations)} results')
        db_handle.session.add_all(relations)
        db_handle.session.commit()
        db_handle.session.close()
        
        logging.getLogger(LOGGER_NAME).info(f'Commit done')
        
        return len(relations)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).error(f'Exception in execute job: {traceback.format_exc()}')

def summarize_results(results):
    logging.getLogger(LOGGER_NAME).info(f'In total found {sum(results)} relations')

def run_one(cf_id, db_handle,write_to_db=False, num_of_consts=None):
    #db_handle = ramanujan_db.RamanujanDB()
    cf = db_handle.session.query(models.Cf).filter(models.Cf.cf_id == cf_id).first()
    connection_data = check_cf2(cf, db_handle.constants, num_of_consts)
    if write_to_db:
        if not cf.scanned_algo:
            cf.scanned_algo = dict()
        cf.scanned_algo[ALGORITHM_NAME] = int(time.time())
        # for postgres < 9.4
        flag_modified(cf, 'scanned_algo')

        db_handle.session.add_all([cf])
        if connection_data:
            db_handle.session.add_all([connection_data])
        db_handle.session.commit()
      #  db_handle.session.close()

    return connection_data
