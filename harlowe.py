# coding: utf-8
from __future__ import division, unicode_literals, print_function
from six import text_type

from collections import OrderedDict
import re
import codecs
import html5lib
from lxml import etree

from helper_functions import compile_re


_STORY_TAG = 'tw-storydata'
_PASSAGE_TAG = 'tw-passagedata'

# These patterns are taken from the Harlowe source (js/markup/Patterns.js)
# The letters and whitespace patterns include unicode characters. Since they're spelled out
# in Harlowe, I'll copy those instead of using Python's re.UNICODE flag
_UNICODE_LETTERS_PATTERN = '\u00c0-\u00de\u00df-\u00ff\u0150\u0170\u0151\u0171'
_WHITESPACE_PATTERN = '[ \\f\\t\\v\u00a0\u1680\u180e\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]'
_PROPERTY_NAME_PATTERN = r'[\w{0}]*[a-zA-Z{0}][\w{0}]*'.format(_UNICODE_LETTERS_PATTERN)

# Variable is '$'+property_name_pattern
# Macro names can be '[any letter\-/\][any letter\-]*'' OR a variable
# Hook tags are '[any letter\-]*'
# Passage links start with '\[\[(?!\[)'
# Passage link contents are '[^]]*', and are separated by -> or <-
_VARIABLE_NAME_PATTERN = _PROPERTY_NAME_PATTERN
_VARIABLE_PATTERN = r'\$' + _VARIABLE_NAME_PATTERN
_MACRO_NAME_PATTERN = r'((?P<name>[\w\-{0}\\/][\w\-{0}]*)|(?P<variable>{1})):'.format(_UNICODE_LETTERS_PATTERN,
                                                                                      _VARIABLE_PATTERN)
_HOOK_NAME_PATTERN = r'[\w\-{0}]*'.format(_UNICODE_LETTERS_PATTERN)
_LINK_CONTENTS_PATTERN = r'((?P<desc1>[^]]+)\->(?P<dest1>[^]]+)|(?P<dest2>[^]]+?)<\-(?P<desc2>[^]]+)|(?P<contents>[^]]*))'


# Append an item to an array either by a regular append or, if both the new
# item and the last item in the array are strings, by appending the new string to
# the last one
def _append_with_string_merge(seq, new_item):
    """
    Append an item to a list. If the new item is a string and the last item in the list is a string, then the
     strings are concatenated instead.

    Args:
        seq (list of object): The list to append to.
        new_item (object): The new item to append to the list.
    """
    if seq and isinstance(new_item, text_type) and isinstance(seq[-1], text_type):
        s = seq.pop()
        seq.append(s+new_item)
    else:
        seq.append(new_item)


def _unescape_string(s):
    """Decode any backslash-escaped literals in a string.

    Args:
        s: The string to decode.

    Returns:
        The decoded string.
    """
    # We don't use codecs.decode() straight up for reasons explained in http://stackoverflow.com/a/24519338
    escape_sequence = compile_re(r'''
        ( \\U........      # 8-digit hex escapes
        | \\u....          # 4-digit hex escapes
        | \\x..            # 2-digit hex escapes
        | \\[0-7]{1,3}     # Octal escapes
        | \\N\{[^}]+\}     # Unicode characters by name
        | \\[\\'"abfnrtv]  # Single-character escapes
        )''', re.UNICODE | re.VERBOSE)

    return escape_sequence.sub(lambda match: codecs.decode(match.group(0), 'unicode-escape'),
                               s)


def _escape_string(s, surrounding_quote='"'):
    """Escape special characters in a string by adding backslashes.

    Args:
        s: The string to escape.
        surrounding_quote: The quote mark surrounding the string.

    Returns:
        The escaped string.
    """
    s = s.replace('\\', '\\\\')
    if surrounding_quote == '"':
        s = s.replace('"', r'\"')
    if surrounding_quote == "'":
        s = s.replace("'", r"\'")
    return s


def _escape_harlowe_html(s):
    """Replace special HTML characters according to the rules Harlowe/Twine uses.

    Args:
        s: The string whose contents should be replaced.

    Returns:
        The escaped string.
    """
    # We can't just replace ampersands willy-nilly because that will stomp on
    # pre-existing character references. So don't match things like &quot; or &#17;.
    ampersand_re = compile_re('''
        &                       # Match an ampersand
        (?!                     # that isn't followed by:
            (\#\d+ |            #   a hash plus digits (#nnnn) or...
            \#x[0-9a-fA-F]+ |   #   a hash and "x" plus hex digits (#xffff) or...
            \w+                 #   word characters
            )
        );                      # and then a semicolon
    ''', re.VERBOSE)

    #s = ampersand_re.sub("&amp;", s)
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    s = s.replace('\'', "&#39;")
    return s


def escape_list(l):
    """Replace special HTML characters for each string item in the list, and convert non-strings to strings.

    Calls the str() method on every object that isn't a string in the list to cast it to a string.

    Args:
        l: The list whose contents will be escaped or cast to strings.
    """
    return [_escape_harlowe_html(item) if isinstance(item, text_type) else str(item) for item in l]


class HarlowePassage:
    """
    A Harlowe passage.

    Attributes:
        pid (str): Passage ID.
        name (str): Passage name.
        contents (str): Unparsed contents of the passage.
        tags (str): Comma-separated tags.
        position (str): Position of the passage in the Twine editor in the form "x,y"
        parsed_contents (list of object): Parsed contents as generated by the parse_contents() method.
        destinations (set of HarlowePassage): Other passages that can be reached in one step.
        parents (set of HarlowePassage): Other passages that can reach this passage in one step.
    """
    parsed_contents = None
    destinations = set()
    parents = set()

    def __init__(self, pid, name, contents, tags, position):
        """
        Create a Harlowe passage.

        Args:
            pid (str): The string containing the passage ID.
            name (str): The passage's name.
            contents (str): The unparsed contents of the passage.
            tags (str): The passage's comma-separated tags.
            position (str): The "x,y" position of the passage in the Twine editor.
        """
        self.pid = pid
        self.name = name
        self.contents = contents
        self.tags = tags
        self.position = position

    @classmethod
    def from_string(cls, s):
        """
        Create a passage object from a string containing an HTML <tw-passage> element.

        Args:
            s (str): The passage.

        Returns:
            The new Harlowe passage object.
        """
        # TODO this doesn't work if you have non-defined entities like &lsquo; in your text!
        elem = etree.fromstring(s)
        return cls.from_element(elem)

    @classmethod
    def from_element(cls, elem):
        """
        Create a passage object from an ElementTree element built from an HTML <tw-passage> element.

        Args:
            elem (etree.Element): The passage.

        Returns:
            The new Harlowe passage object.
        """
        return cls(elem.attrib['pid'], elem.attrib['name'], elem.text, elem.attrib['tags'], elem.attrib['position'])

    def __str__(self):
        str_list = ['<{} pid="{}" name="{}" tags="{}" position="{}">'.format(_PASSAGE_TAG, self.pid,
                                                                             _escape_harlowe_html(self.name), _escape_harlowe_html(self.tags),
                                                                             self.position)]

        # Prefer the parsed contents to the raw contents string
        if self.parsed_contents:
            str_list.extend(escape_list(self.parsed_contents))
        elif self.contents:
            str_list.append(_escape_harlowe_html(self.contents))

        str_list.append('</{}>'.format(_PASSAGE_TAG))

        return ''.join(str_list)

    def parse_contents(self):
        """
        Parse the passage contents from the HarlowePassage.contents attribute.
        """
        self.parsed_contents = tokenize(self.contents)[0]

    def modify_text(self, mod_fn):
        """
        Apply a function to the output text of all of the passage's parsed contents. If the parsed_contents attribute
        is None, then HarlowePassage.parse_contents() is called first.

        Args:
            mod_fn ((str) -> str): The text-modifying function.

        Returns:
            The Harlowe passage object.
        """
        if not self.parsed_contents:
            self.parse_contents()

        self.parsed_contents = [mod_fn(item) if isinstance(item, text_type) else item.modify_text(mod_fn)
                                for item in self.parsed_contents]

        return self


class HarloweVariable:
    """
    A Harlowe variable.

    Attributes:
        name (str): The name of the variable (without the leading '$')
    """
    def __init__(self, name):
        """
        Create a HarloweVariable.

        Args:
            name (str): The variable's name (without the leading '$')
        """
        self.name = name

    def __str__(self):
        return '$'+self.name

    def modify_text(self, mod_fn):
        """
        Apply a function to the output text of all of the variable's parsed contents (which, for variables,
        is none).

        Args:
            mod_fn ((str) -> str): The text-modifying function.

        Returns:
            The Harlowe variable object.
        """
        return self


hook_count = 0  # TODO DEBUG
class HarloweHook:
    """
    A Harlowe hook.

    Attributes:
        hook (list of object): The parsed contents of the hook.
        nametag (str): The nametag, if any, attached to the hook.
    """
    def __init__(self, hook, nametag=None, nametag_on_right=False):
        """
        Create a Harlowe hook object.

        Args:
            hook (list of object): The parsed contents of the hook.
            nametag (str, optional): The nametag, if any, attached to the hook.
            nametag_on_right (bool, optional): True if the hook had a nametag that was attached to the right of the
             hook, False otherwise.
        """
        self.hook = hook
        self.nametag = nametag
        self.nametag_on_right = nametag_on_right

    def __str__(self):
        str_list = ['[']
        str_list.extend(escape_list(self.hook))
        str_list.append(']')
        if self.nametag:
            if self.nametag_on_right:
                str_list.append('&lt;' + _escape_harlowe_html(self.nametag) + '|')
            else:
                str_list = ['|', _escape_harlowe_html(self.nametag), '&gt;'] + str_list
        return ''.join(str_list)

    def modify_text(self, mod_fn):
        """
        Apply a function to the output text of all of the hook's parsed contents.

        Args:
            mod_fn ((str) -> str): The text-modifying function.
        """
        self.hook = [mod_fn(item) if isinstance(item, text_type) else item.modify_text(mod_fn)
                     for item in self.hook]
        return self


class HarloweLink:
    """
    A Harlowe link.

    Attributes:
        link_text (list of object): The link's parsed text.
        passage_name (list of object, optional): The parsed name of the passage, or None (for "[[passage name]]" links).
    """
    def __init__(self, link_text, passage_name=None, passage_on_right=True):
        """
        Create a Harlowe link object.

        Args:
            link_text (list of object): The link's parsed text.
            passage_name (list of object, optional): The parsed name of the passage, or None (for "[[passage name]]"
                links).
            passage_on_right (bool, optional): True for "[[text->passage]]" links, False for "[[passage<-text]]" ones.
        """
        self.link_text = link_text
        self.passage_name = passage_name
        self.passage_on_right = passage_on_right

    def __str__(self):
        str_list = ['[[']
        escaped_link_text = escape_list(self.link_text)
        if self.passage_name:
            escaped_passage_name = escape_list(self.passage_name)
            if self.passage_on_right:
                str_list.extend(escaped_link_text)
                str_list.append('-&gt;')
                str_list.extend(escaped_passage_name)
            else:
                str_list.extend(escaped_passage_name)
                str_list.append('&lt;-')
                str_list.extend(escaped_link_text)
        else:
            str_list.extend(escaped_link_text)
        str_list.append(']]')

        return ''.join(str_list)

    def modify_text(self, mod_fn):
        """
        Apply a function to the output text of all of the link's parsed text. Passage names are not modified, which
        means that no change happens for "[[text]]"-style links.

        Args:
            mod_fn ((str) -> str): The text-modifying function.

        Returns:
            The Harlowe link object.
        """
        if self.passage_name:
            self.link_text = [mod_fn(item) if isinstance(item, text_type) else item.modify_text(mod_fn)
                              for item in self.link_text]
        return self


class HarloweMacro:
    """
    A Harlowe macro object.

    Attributes:
        name_in_source (str): The name as given in the source file. For example, "(go-to:)" has a name_in_source
            of "go-to".
        canonical_name (str): The name with all ignored characters stripped out. For example, "(go-to:)" has a
            canonical_name of "goto".
        code (list of object): The macro's parsed code.
    """
    def __init__(self, name, code):
        """
        Create a Harlowe macro object.

        Args:
            name (str): The name of the macro as given in the source file.
            code (list of object): The macro's parsed code.
        """
        self.name_in_source = name
        if isinstance(name, text_type):
            strip_symbols_re = compile_re('-|_')
            self.canonical_name = strip_symbols_re.sub('', name.lower())
        else:
            self.canonical_name = name
        self.code = code

    def __str__(self):
        str_list = ['(', _escape_harlowe_html(self.name_in_source), ':']
        str_list.extend(escape_list(self.code))
        str_list.append(')')
        return ''.join(str_list)

    def modify_text(self, mod_fn):
        """
        Apply a function to the output text of all of the macro's parsed code. Macro names are not changed.

        Args:
            mod_fn ((str) -> str): The text-modifying function.

        Returns:
            The Harlowe macro object.
        """
        # This off-the-wall regex is adapted from http://stackoverflow.com/a/171499
        # because it handles backslashes inside of strings properly.
        # The more compact, completely unreadable version is: ((["'])((?:(?=(\\?))\4.)*?)\2)
        string_re = compile_re(r'''
        (?P<string>               # The full string
            (?P<quotemark>["\'])  # The opening quote mark
            (?P<contents>         # The actual string contents
                (?:               # Don't make this next part a group
                    (?=           # Match any backslash...
                        (?P<possible_backslash>\\?)
                    )(?P=possible_backslash) # ...followed by another
                    .             # And any character
                )*?               # Match that non-group repeatedly but non-greedily
            )
        (?P=quotemark))           # Capture the same quote mark we opened the string with
        ''', re.VERBOSE)

        new_code = []

        for item in self.code:
            if isinstance(item, text_type):
                new_code.append(string_re.sub(lambda match: match.group('quotemark') +
                                              _escape_string(mod_fn(_unescape_string(match.group('contents'))),
                                                             match.group('quotemark')) +
                                              match.group('quotemark'), item))
            else:
                new_code.append(item.modify_text(mod_fn))

        self.code = new_code

        return self


def _parse_variable(match, s):
    variable_re = compile_re(_VARIABLE_NAME_PATTERN)
    variable_match = variable_re.match(s)
    if variable_match:
        return [HarloweVariable(variable_match.group(0))], s[variable_match.end(0):]
    else:
        return [match], s


def _parse_hook(match, s):
    # Hooks can be named: |nametag>[hook] or [hook]<nametag|
    # or can be anonymous: [hook]
    original_text = s
    nametag = None
    nametag_on_right = False
    if match == '|':
        # Make sure this is an actual name tag
        left_tag_re = compile_re(r'(?P<nametag>' + _HOOK_NAME_PATTERN + ')>\[')
        tag_match = left_tag_re.match(s)
        if not tag_match:
            return [match], original_text
        nametag = tag_match.group('nametag')
        s = s[tag_match.end(0):]

    hook_list, stop_token, s1 = tokenize(s, stop_token_pattern=r'\]<?')
    if not stop_token:
        # Whoops, not a hook after all I guess
        return [match], original_text

    if stop_token == ']<':
        # We may have a name tag
        right_tag_re = compile_re(r'(?P<nametag>' + _HOOK_NAME_PATTERN + ')\|')
        tag_match = right_tag_re.match(s1)
        if tag_match:
            nametag = tag_match.group('nametag')
            s1 = s1[tag_match.end(0):]
            nametag_on_right = True
        else:
            # Put the < character back on
            s1 = '<'+s1

    return [HarloweHook(hook_list, nametag, nametag_on_right)], s1


def _parse_link(match, s):
    # Links are in the form [[str->destination]] or [[destination<-str]] or [[destination]]
    link_re = compile_re(_LINK_CONTENTS_PATTERN + r'\]\]')
    link_match = link_re.match(s)
    if not link_match:
        # Whoops, not a link, so see if we're two nested macros
        return _parse_hook(match[0], match[1:] + s)

    contents = link_match.group('contents')
    dest_on_right = True
    if contents:
        # A link of the form [[contents]]
        tokenized_contents, _, s1 = tokenize(contents)
        if s1:
            # We had text left after parsing, which shouldn't happen
            raise RuntimeError('Parsing a link failed with "{}" text left over (link: "{}")'.format(s1, contents))
        link = HarloweLink(tokenized_contents)
    else:
        description = link_match.group('desc1')
        if description:
            destination = link_match.group('dest1')
        else:
            description = link_match.group('desc2')
            destination = link_match.group('dest2')
            dest_on_right = False
        tokenized_desc, _, s1 = tokenize(description)
        if s1:
            raise RuntimeError('Parsing a link\'s description failed with "{}" text left over (full description: "{}")'.
                               format(s1, description))
        tokenized_dest, _, s1 = tokenize(destination)
        if s1:
            raise RuntimeError('Parsing a link\'s destination failed with "{}" text left over (full destination: "{}")'.
                               format(s1, destination))
        link = HarloweLink(tokenized_desc, tokenized_dest, dest_on_right)

    return [link], s[link_match.end(0):]


def _parse_macro(match, s):
    # Macros are in the form "(name: content)"
    name_re = compile_re(_MACRO_NAME_PATTERN)
    name_match = name_re.match(s)
    if not name_match:
        # Not a macro
        return [match], s

    name = name_match.group('name')
    if not name:
        # We got a variable
        variable = name_match.group('variable')
        name, s1 = _parse_variable(variable[0], variable[1:])
        if s1:
            # Wait, no, we didn't
            return [match], s
        name = name[0]

    s = s[name_match.end(0):]
    content_list, stop_token, s1 = tokenize(s, stop_token_pattern=r'\)')
    return_list = [HarloweMacro(name, content_list)]

    # Since hooks bind tightly to macros, check to see if the next item's a macro
    if s1 and s1[0] == '[':
        hook_list, s2 = _parse_hook(s1[0], s1[1:])
        if isinstance(hook_list[0], HarloweHook):
            return_list.extend(hook_list)
            s1 = s2

    return return_list, s1


def _parse_nested_brackets(match, s):
    # Deal with hooks that are immediately nested, like "[[[ ]<one| ]<two| ]"

    nested_contents = []
    while match:
        hook, s = _parse_hook(match[-1], s)
        hook = hook[0]
        # Stick the previously-parsed hook on the front of the new hook's contents
        # (i.e. nest the hooks)
        hook.hook = nested_contents + hook.hook
        nested_contents = [hook]
        match = match[:-1]
    if len(nested_contents) != 1:
        err_str = '['+', '.join([str(item) for item in nested_contents])
        raise RuntimeError('Error parsing nested hooks: multiple tokens created\n'+err_str)

    return nested_contents, s


_START_TOKENS = {'[[': [_parse_link, r'\[\[(?!\[)'],
                 '[': [_parse_hook, r'\[(?!\[)'],
                 '|': [_parse_hook, r'\|'],
                 '(': [_parse_macro, r'\('],
                 '$': [_parse_variable, r'\$'],
                 }


# Verbatim token starts are any number of consecutive ` marks and so are handled separately
# Similarly, we handle runs of three or more brackets separately
_START_TOKEN_PATTERNS = '(?P<start>(' + '|'.join([s[1] for s in _START_TOKENS.values()]) + r")|`+?|\[{3,})"


def tokenize(s, stop_token_pattern=None):
    """
    Tokenize a string containing Harlowe code.

    Args:
        s (str): The string to tokenize.
        stop_token_pattern (str, optional): A regular expression pattern that, when found, stops tokenizing.

    Returns:
        (list of object, str, str): A tuple containing the list of tokens, the matched stop token pattern (if the
            stop_token_pattern was found), and the remaining un-tokenized string (if the stop_token_pattern was found).
    """
    token_list = []
    if not stop_token_pattern:
        token_re = compile_re(_START_TOKEN_PATTERNS)
    else:
        token_re = compile_re(_START_TOKEN_PATTERNS + '|(?P<stop>' + stop_token_pattern + ')')
    to_return = None, None, None

    while True:
        if not s:
            to_return = token_list, None, None
            break

        token_match = token_re.search(s)
        # If there are no tokens, yield the entire string and quit
        if not token_match:
            _append_with_string_merge(token_list, s)
            to_return = token_list, None, None
            break

        # Yield any bare string before the token
        if token_match.start(0):
            _append_with_string_merge(token_list, s[:token_match.start(0)])

        token = token_match.group('start')
        if token:
            try:
                token_info = _START_TOKENS[token]
                # Parser functions return a list of parsed token objects and the remaining string
                parsed_objs, s = token_info[0](token, s[token_match.end('start'):])
                for item in parsed_objs:
                    _append_with_string_merge(token_list, item)
            except KeyError:
                # See if we have verbatim text, which is marked by 1+ ` marks
                if token[0] == "`":
                    s = s[token_match.end('start'):]
                    verbatim_re = compile_re(r'(?P<text>.+?)`{' + str(len(token)) + '}')
                    verbatim_match = verbatim_re.match(s)
                    if verbatim_match:
                        _append_with_string_merge(token_list, verbatim_match.group('text'))
                        s = s[verbatim_match.end(0)]
                    else:
                        # Doesn't appear to be verbatim text, so keep going
                        _append_with_string_merge(token_list, token)
                # See if we have a run of brackets
                elif token[0] == '[':
                    parsed_objs, s = _parse_nested_brackets(token, s[token_match.end('start'):])
                    for item in parsed_objs:
                        _append_with_string_merge(token_list, item)
                else:
                    raise RuntimeError('Found a token "{}" that isn\'t recognized'.format(token))
        else:
            # We matched the stop token instead of the start token
            to_return = token_list, token_match.group('stop'), s[token_match.end('stop'):]
            break

    return to_return


def parse_harlowe_html(s):
    """
    Parse a string containing the HTML of a Twine game written using Harlowe.

    Args:
        s (str): The Harlowe source.

    Returns:
        (dict, list, OrderedDict): A dictionary of the attributes on the top-level tw-storydata
         element, a list of non-passage elements in the game (as etree.ElementTree.Element),
         and a dict whose keys are the passage's names and whose values are the
         corresponding HarlowePassage objects.
    """
    passages = OrderedDict()  # So that we keep the original room order in source code
    other_elems = list()

    # The story uses HTML5 custom elements, and so requires an HTML5-aware parser
    story_elem = html5lib.parseFragment(s, treebuilder='lxml', namespaceHTMLElements=False)[0]
    if story_elem is None or story_elem.tag != _STORY_TAG:
        raise RuntimeError('No properly-formatted story tag ('+_STORY_TAG+') found')

    for elem in story_elem:
        if elem.tag == _PASSAGE_TAG:
            passage = HarlowePassage.from_element(elem)
            passages[passage.name] = passage
        else:
            other_elems.append(elem)

    return story_elem.attrib, other_elems, passages


def reconstruct_harlowe_html(story_attribs, other_elems, passages):
    """
    Turn parsed Harlowe passage objects back into HTML.

    Args:
        story_attribs (dict): Attributes to be attached to the top-level tw-storydata
        other_elems (list): Non-passage elements in the game (as etree.ElementTree.Element)
        passages (dict): Passages, where the keys are the passage's names and the
        values are the corresponding HarlowePassage objects.

    Returns:
        str: The Twine game in its HTML form.
    """

    passages_html = '\n'.join([str(passage_obj) for _, passage_obj in passages.items()])+'\n'

    story_elem = etree.Element(_STORY_TAG, story_attribs)
    if other_elems:
        story_elem.extend(other_elems)

    story_html = etree.tostring(story_elem, encoding='unicode')

    # Add the passages_html in by hand, since adding it to an xml element would escape
    # all of the angle brackets, turning them into &lt; and &gt;
    before, sep, after = story_html.partition('</'+_STORY_TAG+'>')
    story_html = before+passages_html+sep+after

    return story_html
