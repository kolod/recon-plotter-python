
import math


def pretty_round(num: float, places: int) -> float:
    p = math.log10(abs(num))
    f = math.pow(10, int(round(p)) - places + 1)
    rnum = round(num / f) * f
    return rnum


def pretty_floor(num: float, places: int) -> float:
    p = math.log10(abs(num))
    f = math.pow(10, int(round(p)) - places + 1)
    rnum = math.floor(num / f) * f
    return rnum


def pretty_ceil(num: float, places: int) -> float:
    p = math.log10(abs(num))
    f = math.pow(10, int(round(p)) - places + 1)
    rnum = math.ceil(num / f) * f
    return rnum


if __name__ == '__main__':
    print(str(pretty_round(0.265, 2)))
    print(str(pretty_round(1.26, 2)))
    print(str(pretty_round(12.6, 2)))
    print('----')
    print(str(pretty_floor(0.265, 2)))
    print(str(pretty_floor(1.26, 2)))
    print(str(pretty_floor(12.6, 2)))
    print('----')
    print(str(pretty_ceil(0.265, 2)))
    print(str(pretty_ceil(1.26, 2)))
    print(str(pretty_ceil(12.6, 2)))
