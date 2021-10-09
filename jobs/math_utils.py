import numpy as np


#given a polynomial with integer coeffs return its integer roots
def integer_roots(integer_poly):
    abs_sum_coeff = sum([np.abs(i) for i in integer_poly])

    roots = []

    i= -abs_sum_coeff
    while i <= abs_sum_coeff:
        if np.polyval(integer_poly,i) == 0:
            roots.append(i)
        i+=1

    return roots
