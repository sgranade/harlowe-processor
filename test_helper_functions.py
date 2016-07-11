# coding: utf-8
from helper_functions import smartify_entities


def test_smartified_double_quotes_at_start_and_end_of_string():
    s = '"Some text"'
    s_smart = '“Some text”'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_single_quotes_at_start_and_end_of_string():
    s = "'Some text'"
    s_smart = '‘Some text’'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_possessive_single_quote():
    s = "don't"
    s_smart = 'don’t'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_decade_abbreviation():
    s = "I love the '80s."
    s_smart = 'I love the ’80s.'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_nested_quotes():
    s = 'He said, "\'Murder, She Wrote\' is my fave show."'
    s_smart = 'He said, “‘Murder, She Wrote’ is my fave show.”'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_quote_before_a_unicode_dash():
    s = '"Here—" he broke off.'
    s_smart = '“Here—” he broke off.'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartifying_quotes_leaves_harlowe_bold_marks_alone():
    s = r"""Don't muck about with ''stuff that's in bold!''"""
    s_smart = r"""Don’t muck about with ''stuff that’s in bold!''"""

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_dashes():
    s = 'This--this includes a dash.'
    s_smart = 'This&mdash;this includes a dash.'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_ellipses():
    s = 'Ellipses...indicate a pause.'
    s_smart = 'Ellipses…indicate a pause.'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_ellipses_with_spaces():
    s = 'Ellipses. . .indicate a pause.'
    s_smart = 'Ellipses…indicate a pause.'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_dashes():
    s = 'Wait--let me make sure this works'
    s_smart = 'Wait—let me make sure this works'

    result = smartify_entities(s)

    assert(s_smart == result)


def test_smartified_dashes_leaves_html_comments_alone():
    s = '<!-- html comment --> This--this is a dash'
    s_smart = '<!-- html comment --> This—this is a dash'

    result = smartify_entities(s)

    assert(s_smart == result)
