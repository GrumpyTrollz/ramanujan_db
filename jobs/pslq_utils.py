import mpmath as mp
import numpy as np

def verify_result(first_value, second_value, result):
    right_side = second_value
    left_side = (first_value * result[0] + result[1])
    right_side = right_side * (first_value * result[2] + result[3])
    if mp.almosteq(right_side, left_side):
        return result
    else:
        print("False positive")
        return None

def check_int_null_vector(first_value, second_value):
    result = mp.pslq([first_value, 1, -second_value*first_value, -second_value])

    # Verify: denote the math const as M and the CF value as cf then the result we seek is:
    # (a*M + b) / (c*M + d) = cf
    # where a,b,c,d are result[0], result[1], result[2], result[3] respectively
    if result:
        val = verify_result(first_value, second_value, result)
        return val

    return None

def verify_result2(constants, cf, res):
    if mp.almosteq(constants.dot(res[:len(constants)]), cf * constants.dot(res[len(constants):])):
        return res
    else:
        print("False positive")
        return None

def check_int_null_vector2(constants, cf):
    # instead of just one first_value, now constants is a list of "first_value"s to PSLQ against
    # cf, which was the second value. gonna use numpy vector magic to make things nice and compact
    constants = np.concatenate((constants, [1]))
    res = mp.pslq(np.concatenate((constants, -cf * constants)).tolist())
    return verify_result2(constants, cf, res) if res else None

def find_null_polynomial(poly):
    res = mp.pslq(poly)
    if res:
        if mp.almosteq(np.dot(poly, res), 0):
            return res
        print("False positive")
    return None