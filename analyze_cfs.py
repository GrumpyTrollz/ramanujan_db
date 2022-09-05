from db.ramanujan_db import RamanujanDB
import sys
import numpy as np
import sympy
from sympy.polys.polytools import poly_from_expr
from sympy.core.numbers import Rational
from sympy.ntheory.factor_ import factorint
import math
import os

from jobs import job_generate_cfs as gen_cfs
from jobs import job_calculate_precision as prec_job
from jobs import job_const_cf_pslq as pslq_job

def get_polys(filename, symbol_char):
    with open(filename, 'r') as polys_file:
        for line in polys_file.readlines():
            line = line.strip()
            a_n, b_n = line.split(',')
            sympy.Symbol(symbol_char)
            yield (poly_from_expr(a_n)[0].all_coeffs(), poly_from_expr(b_n)[0].all_coeffs())

def get_lcm(numbers):
    cur_lcm = 1
    for i in numbers:
        cur_lcm = cur_lcm * i // math.gcd(cur_lcm, i)

    return cur_lcm

def get_closest_root(num):
    root = 1
    for p, deg in factorint(num).items():
        if deg % 2 == 1:
            deg += 1
        root *= p**(deg/2)

    return int(root)

def expand_cf(a_n, b_n):
    try:
        a_lcm = get_lcm([x.q for x in a_n])
        b_lcm = get_lcm([x.q for x in b_n])
        lcm = Rational(get_lcm([int(a_lcm), get_closest_root(b_lcm)]))

        return [int((lcm ** 2) * x) for x in b_n], [int(lcm * x) for x in a_n]
    except Exception as ex:
        print(ex)
        print(f'{a_n}, {b_n}')
    return None


def parse_polys_from_file(filename, symbol_char='l'):
    success = 0
    polys = 0
    for a_n, b_n in get_polys(filename, symbol_char):
        polys += 1
        res = expand_cf(a_n, b_n)
        if res:
            success += 1
            yield res

    print(f'got {success} out of {polys}')

def analyze_polys(filename, num_of_constants):
    db_handle = RamanujanDB()
    for num, denom in parse_polys_from_file(filename):
        cf_id = gen_cfs.add_one(num, denom, db_handle)
        precision_data = prec_job.run_one(num, denom,db_handle, write_to_db=True, cf_id=cf_id)
        if precision_data.precision < 54:
            print(f'pricision is too low prec: {precision_data.precision} cf id: {cf_id}')
            continue
        if precision_data.general_data['rational'] == 1:
            print(f'cf is rational value: {precision_data.value} cf id: {cf_id}')
            continue

        connections = pslq_job.run_one(cf_id,db_handle, write_to_db=True, num_of_consts=num_of_constants)
        print(f'num: {num}, denom:{denom} has cf_id:{cf_id}')
        print(f'Precision data: {precision_data.value}')
        print(f'Found connections: {connections}')
        db_handle.session.close()


def main():
    os.makedirs(os.path.join(os.getcwd(), 'logs'), exist_ok=True)
    analyze_polys(sys.argv[1], int(sys.argv[2]))

if __name__ == '__main__':
    main()
