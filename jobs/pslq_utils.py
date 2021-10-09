import mpmath as mp


def verify_result(first_value, second_value, result):
    if result[0] == result[2] == 0:
        print("False positive")
        return None

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

