#!/usr/bin/python3

from typing import List


def readCommaSeparatedLine(line: str) -> List[str]:
    result = []
    isStringStarted = False
    value = ''
    for i in range(len(line)):
        if line[i] == '"':
            if isStringStarted:
                if i > 1 and line[i-1] == '"':
                    value += '"'
            else:
                isStringStarted = True
        elif line[i] == ',':
            if (i > 2 and line[i-1] == '"' and line[i-2] == '"') or (isStringStarted and line[i-1] != '"'):
                value += line[i]
            else:
                result.append(value.strip())
                isStringStarted = False
                value = ''
        else:
            value += line[i]

    if len(value):
        result.append(value.strip())
    return result


if __name__ == "__main__":
    print(readCommaSeparatedLine('1997,Ford,E350'))
    print(readCommaSeparatedLine('"1997","Ford","E350"'))
    print(readCommaSeparatedLine('1997,Ford,E350,"Super, luxurious truck"'))
    print(readCommaSeparatedLine('1997,Ford,E350,"Super, ""luxurious"" truck"'))
    print(readCommaSeparatedLine('C:/Users/alexa/Documents/QtProjects/recon/sample/sample-edited.txt,,,Ud,"Time, s","Voltage, V",0,130.0,-600.0,500.0'))
    print(readCommaSeparatedLine('"""Super"", luxurious truck"'))
