#!/usr/bin/python3

from typing import Any, List
from test_readCommaSeparatedLine import readCommaSeparatedLine


def writeCommaSeparatedLine(values: List[Any]) -> str:
    result = []
    for value in values:
        if type(value) == list:
            result.append(writeCommaSeparatedLine(value))
        elif type(value) == str:
            if '"' in value:
                value = value.replace('"', '""')
                value = f'"{value}"'
            elif ',' in value:
                value = f'"{value}"'
            result.append(value)
        else:
            result.append(str(value))
    return ', '.join(result)


if __name__ == "__main__":
    original = ['argr', 'serg"rg', ['ergr,erg', 'rtrh"grerth",trhth'], 45]
    csv = writeCommaSeparatedLine(original)
    data = readCommaSeparatedLine(csv)
    print(csv)
    print(original)
    print(data)
