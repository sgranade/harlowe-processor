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


def smartify_entities(s):
    """
    Given a string, turn its slab quotes into HTML curly quote entities, dashes in to em-dash entitites, and
    ellipses into the ellipsis entity. HTML comments (<!-- comment -->) are left alone.

    This is a modified version of the [smartypants module](https://bitbucket.org/livibetter/smartypants.py).

    Args:
        s (str): The string to be smartified.

    Returns:
        str: The smartified string.
    """
    s = _smartify_quotes(s)
    s = _smartify_dashes(s)
    s = _smartify_ellipses(s)
    return s


def _smartify_quotes(s):
    punct_pattern = r"""[!"#\$\%'()*+,-.\/:;<=>?\@\[\\\]\^_`{|}~]"""
    close_pattern = r"""[^\ \t\r\n\[\{\(\-]"""
    close_pattern_no_leading_single_quotes = r"""[^\ \t\r\n\[\{\(\-']"""
    dec_dashes_pattern = r"""&#8211;|&#8212;|&ndash;|–|&mdash;|—"""

    # One thing to note: Harlowe uses "''" as a delimiter to indicate bold text.
    # We'll have to avoid that

    # Special case if the very first character is a quote
    # followed by punctuation at a non-word-break. Close the quotes by brute force:
    s = sub_re(r"""^'(?=%s\\B)""" % (punct_pattern,), r"""’""", s)
    s = sub_re(r"""^"(?=%s\\B)""" % (punct_pattern,), r"""”""", s)

    # Special case for double sets of quotes, e.g.:
    #   He said, "'Quoted' words in a larger quote."
    s = sub_re(r""""'(?=\w)""", r"""“‘""", s)
    s = sub_re(r"""'"(?=\w)""", r"""‘“""", s)

    # Special case for decade abbreviations (the '80s):
    s = sub_re(r"""(?<=\W)'(?=\d{2}s)""", r"""’""", s)

    # Get most opening single quotes:
    opening_single_quotes_regex = compile_re(r"""
            (
                \s          |   # a whitespace char, or
                &nbsp;      |   # a non-breaking space entity, or
                --          |   # dashes, or
                &[mn]dash;  |   # named dash entities
                –|—         |   # Unicode dashes
                %s          |   # or decimal entities
                &\#x201[34];    # or hex
            )
            '                 # the quote
            (?=\w)            # followed by a word character
            """ % (dec_dashes_pattern,), re.VERBOSE)
    s = opening_single_quotes_regex.sub(r"""\1‘""", s)

    closing_single_quotes_regex = compile_re(r"""
            (%s)
            '
            (?!\s | s\b | \d | ')
            """ % (close_pattern_no_leading_single_quotes,), re.VERBOSE)
    s = closing_single_quotes_regex.sub(r"""\1’""", s)

    closing_single_quotes_regex = compile_re(r"""
            (%s)
            '
            (\s | s\b)
            """ % (close_pattern,), re.VERBOSE)
    s = closing_single_quotes_regex.sub(r"""\1’\2""", s)

    # Any remaining single quotes that are by themselves should be opening ones:
    s = sub_re(r"""(?<!')'(?!')""", r"""‘""", s)
    # (Note that they need to be by themselves so as not to catch Harlowe '' bold marks)

    # Get most opening double quotes:
    opening_double_quotes_regex = compile_re(r"""
            (
                \s          |   # a whitespace char, or
                &nbsp;      |   # a non-breaking space entity, or
                --          |   # dashes, or
                &[mn]dash;  |   # named dash entities
                –|—         |   # Unicode dashes
                %s          |   # or decimal entities
                &\#x201[34];    # or hex
            )
            "                 # the quote
            (?=\w)            # followed by a word character
            """ % (dec_dashes_pattern,), re.VERBOSE)
    s = opening_double_quotes_regex.sub(r"""\1“""", s)

    # Double closing quotes:
    closing_double_quotes_regex = compile_re(r"""
            #(%s)?   # character that indicates the quote should be closing
            "
            (?=\s)
            """ % (close_pattern,), re.VERBOSE)
    s = closing_double_quotes_regex.sub(r"""”""", s)

    closing_double_quotes_regex = compile_re(r"""
            (%s)   # character that indicates the quote should be closing
            "
            """ % (close_pattern,), re.VERBOSE)
    s = closing_double_quotes_regex.sub(r"""\1”""", s)

    # Any remaining quotes should be opening ones.
    s = sub_re(r'"', r"""“""", s)

    return s


def _smartify_dashes(s):
    return sub_re('(?<!\<\!)--(?!\>)', '—', s)


def _smartify_ellipses(s):
    return sub_re(r'(?<!\.)\.{3}(?!\.)|(?<!\. )\. \. \.(?! \.)', '…', s)
