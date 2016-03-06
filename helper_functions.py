# coding: utf-8

import re

# Memoize computed regexes. Sadly Python 2 doesn't have functools.lru_cache()
_regex_cache = dict()
def compile_re(pattern, flags=0):
    """
    Compile a regular expression (with memoization).

    Args:
        pattern (str): The regex to be compiled.
        flags (int, optional): Flags to modify how the regex is interpreted.

    Returns:
        The compiled regular expression object.
    """
    try:
        regex = _regex_cache[pattern+str(flags)]
    except KeyError:
        regex = re.compile(pattern, flags)
        _regex_cache[pattern+str(flags)] = regex
    return regex


def sub_re(pattern, replacement, s, count=0, flags=0):
    """
    Replace all occurrences of a regex pattern (with memoization of the regex object).

    Args:
        pattern (str): The regular expression pattern.
        replacement (str): The string to replace.
        s (str): The string in which the replacements will be done.
        count (int, optional): The maximum number of replacements to make.
        flags (int, optional): Flags to modify how the regex is interpreted.
    """
    regex = compile_re(pattern, flags)

    return regex.sub(replacement, s, count)

