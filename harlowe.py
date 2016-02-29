# coding: utf-8
from __future__ import division, unicode_literals, print_function
from six import text_type

import re
from collections import OrderedDict
import html5lib
import xml.etree.ElementTree as etree


PASSAGE_TAG = 'tw-passagedata'

# These patterns are taken from the Harlowe source (js/markup/Patterns.js)
# The letters and whitespace patterns include unicode characters. Since they're spelled out
# in Harlowe, I'll copy those instead of using Python's re.UNICODE flag
unicode_letters_pattern = '\u00c0-\u00de\u00df-\u00ff\u0150\u0170\u0151\u0171'
whitespace_pattern = '[ \\f\\t\\v\u00a0\u1680\u180e\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]'
property_name_pattern = r'[\w{0}]*[a-zA-Z{0}][\w{0}]*'.format(unicode_letters_pattern)

# Variable is '$'+property_name_pattern
# Macro names can be '[any letter\-/\][any letter\-]*'' OR a variable
# Hook tags are '[any letter\-]*'
# Passage links start with '\[\[(?!\[)'
# Passage link contents are '[^]]*', and are separated by -> or <-
variable_name_pattern = property_name_pattern
variable_pattern = r'\$'+variable_name_pattern
macro_name_pattern = r'((?P<name>[\w\-{0}\\/][\w\-{0}]*)|(?P<variable>{1})):'.format(unicode_letters_pattern,
                                                                                     variable_pattern)
hook_tag_name_pattern = r'[\w\-{0}]*'.format(unicode_letters_pattern)
link_contents_pattern = r'((?P<desc1>[^]]+)\->(?P<dest1>[^]]+)|(?P<dest2>[^]]+?)<\-(?P<desc2>[^]]+)|(?P<contents>[^]]*))'


# Memoize computed regexes. Sadly Python 2 doesn't have functools.lru_cache()
_regex_cache = dict()
def compile_re(pattern):
    try:
        regex = _regex_cache[pattern]
    except KeyError:
        regex = re.compile(pattern)
        _regex_cache[pattern] = regex
    return regex


# Append an item to an array either by a regular append or, if both the new
# item and the last item in the array are strings, by appending the new string to
# the last one
def append_with_string_merge(seq, new_item):
    if seq and isinstance(new_item, text_type) and isinstance(seq[-1], text_type):
        s = seq.pop()
        seq.append(s+new_item)
    else:
        seq.append(new_item)


def escape(s):
    """Replace special HTML characters according to the rules Harlowe/Twine uses."""
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
    return [escape(item) if isinstance(item, text_type) else str(item) for item in l]


# todo debug
def code_str(item):
    if isinstance(item, text_type):
        return item
    return item.code_str()


class TwineRoom:
    parsed_contents = None
    destinations = set()
    parents = set()

    def __init__(self, pid, name, contents, tags, position):
        self.pid = pid
        self.name = name
        self.contents = contents
        self.tags = tags
        self.position = position

    @classmethod
    def from_string(cls, s):
        elem = etree.fromstring(s)
        return cls.from_element(elem)

    @classmethod
    def from_element(cls, elem):
        return cls(elem.attrib['pid'], elem.attrib['name'], elem.text, elem.attrib['tags'], elem.attrib['position'])

    def parse_contents(self):
        self.parsed_contents = tokenize(self.contents)[0]

    def __str__(self):
        str_list = ['<{} pid="{}" name="{}" tags="{}" position="{}">'.format(PASSAGE_TAG, self.pid,
                                                                             escape(self.name), escape(self.tags),
                                                                             self.position)]

        # Prefer the parsed contents to the raw contents string
        if self.parsed_contents:
            str_list.extend(escape_list(self.parsed_contents))
        elif self.contents:
            str_list.append(escape(self.contents))

        str_list.append('</{}>'.format(PASSAGE_TAG))

        return ''.join(str_list)


class TwineVariable:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '$'+self.name

    def code_str(self):
        return '$<'+self.name+'>'


hook_count = 0  # TODO DEBUG
class TwineHook:
    def __init__(self, hook, nametag=None, nametag_on_right=False):
        self.hook = hook
        self.nametag = nametag
        self.nametag_on_right = nametag_on_right

    def __str__(self):
        str_list = ['[']
        str_list.extend(escape_list(self.hook))
        str_list.append(']')
        if self.nametag:
            if self.nametag_on_right:
                str_list.append('&lt;'+escape(self.nametag)+'|')
            else:
                str_list = ['|', escape(self.nametag), '&gt;'] + str_list
        return ''.join(str_list)

    # TODO DEBUG
    def code_str(self):
        global hook_count
        str_list = ['H', str(hook_count)]
        hook_count += 1
        if self.nametag:
            str_list.append('|!'+self.nametag+'!>')
        str_list.append('[')
        for item in self.hook:
            str_list.append(code_str(item))
        hook_count -= 1
        str_list.append(']H'+str(hook_count))
        return ''.join(str_list)


class TwineLink:
    def __init__(self, link_text, passage_name=None, passage_on_right=True):
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

    # TODO DEBUG
    def code_str(self):
        str_list = ['{{', self.link_text]
        if len(self.passage_name) != 1 or self.link_text != self.passage_name[0]:
            str_list.append('}->{')
            for item in self.passage_name:
                str_list.append(code_str(item))
        else:
            str_list = ['S']+str_list
        str_list.append('}}')
        return ''.join(str_list)


class TwineMacro:
    def __init__(self, name, code):
        self.name_in_source = name
        if isinstance(name, text_type):
            strip_symbols_re = compile_re('-|_')
            self.canonical_name = strip_symbols_re.sub('', name.lower())
        else:
            self.canonical_name = name
        self.code = code

    def __str__(self):
        str_list = ['(', escape(self.name_in_source), ':']
        str_list.extend(escape_list(self.code))
        str_list.append(')')
        return ''.join(str_list)

    # TODO DEBUG
    def code_str(self):
        str_list = ['M(<', code_str(self.canonical_name), '>: ']
        for item in self.code:
            str_list.append('<'+code_str(item)+'>')
        str_list.append(')')
        return ''.join(str_list)


def parse_variable(match, s):
    variable_re = compile_re(variable_name_pattern)
    variable_match = variable_re.match(s)
    if variable_match:
        return [TwineVariable(variable_match.group(0))], s[variable_match.end(0):]
    else:
        return [match], s


def parse_hook(match, s):
    # Hooks can be named: |nametag>[hook] or [hook]<nametag|
    # or can be anonymous: [hook]
    original_text = s
    nametag = None
    nametag_on_right = False
    if match == '|':
        # Make sure this is an actual name tag
        left_tag_re = compile_re(r'(?P<nametag>'+hook_tag_name_pattern+')>\[')
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
        right_tag_re = compile_re(r'(?P<nametag>'+hook_tag_name_pattern+')\|')
        tag_match = right_tag_re.match(s1)
        if tag_match:
            nametag = tag_match.group('nametag')
            s1 = s1[tag_match.end(0):]
            nametag_on_right = True
        else:
            # Put the < character back on
            s1 = '<'+s1

    return [TwineHook(hook_list, nametag, nametag_on_right)], s1


def parse_link(match, s):
    # Links are in the form [[str->destination]] or [[destination<-str]] or [[destination]]
    link_re = compile_re(link_contents_pattern+r'\]\]')
    link_match = link_re.match(s)
    if not link_match:
        # Whoops, not a link, so see if we're two nested macros
        return parse_hook(match[0], match[1:]+s)

    contents = link_match.group('contents')
    dest_on_right = True
    if contents:
        # A link of the form [[contents]]
        tokenized_contents, _, s1 = tokenize(contents)
        if s1:
            # We had text left after parsing, which shouldn't happen
            raise RuntimeError('Parsing a link failed with "{}" text left over (link: "{}")'.format(s1, contents))
        link = TwineLink(tokenized_contents)
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
        link = TwineLink(tokenized_desc, tokenized_dest, dest_on_right)

    return [link], s[link_match.end(0):]


def parse_macro(match, s):
    # Macros are in the form "(name: content)"
    name_re = compile_re(macro_name_pattern)
    name_match = name_re.match(s)
    if not name_match:
        # Not a macro
        return [match], s

    name = name_match.group('name')
    if not name:
        # We got a variable
        variable = name_match.group('variable')
        name, s1 = parse_variable(variable[0], variable[1:])
        if s1:
            # Wait, no, we didn't
            return [match], s
        name = name[0]

    s = s[name_match.end(0):]
    content_list, stop_token, s1 = tokenize(s, stop_token_pattern=r'\)')
    return_list = [TwineMacro(name, content_list)]

    # Since hooks bind tightly to macros, check to see if the next item's a macro
    if s1 and s1[0] == '[':
        hook_list, s2 = parse_hook(s1[0], s1[1:])
        if isinstance(hook_list[0], TwineHook):
            return_list.extend(hook_list)
            s1 = s2

    return return_list, s1


def parse_nested_brackets(match, s):
    # Deal with hooks that are immediately nested, like "[[[ ]<one| ]<two| ]"

    nested_contents = []
    while match:
        hook, s = parse_hook(match[-1], s)
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


start_tokens = {'[[': [parse_link, r'\[\[(?!\[)'],
                '[': [parse_hook, r'\[(?!\[)'],
                '|': [parse_hook, r'\|'],
                '(': [parse_macro, r'\('],
                '$': [parse_variable, r'\$'],
                }


# Verbatim token starts are any number of consecutive ` marks and so are handled separately
# Similarly, we handle runs of three or more brackets separately
start_token_patterns = '(?P<start>('+'|'.join([s[1] for s in start_tokens.values()])+r")|`+?|\[{3,})"


def tokenize(s, stop_token_pattern=None):
    token_list = []
    if not stop_token_pattern:
        token_re = compile_re(start_token_patterns)
    else:
        token_re = compile_re(start_token_patterns+'|(?P<stop>'+stop_token_pattern+')')
    to_return = None, None, None

    while True:
        if not s:
            to_return = token_list, None, None
            break

        token_match = token_re.search(s)
        # If there are no tokens, yield the entire string and quit
        if not token_match:
            append_with_string_merge(token_list, s)
            to_return = token_list, None, None
            break

        # Yield any bare string before the token
        if token_match.start(0):
            append_with_string_merge(token_list, s[:token_match.start(0)])

        token = token_match.group('start')
        if token:
            try:
                token_info = start_tokens[token]
                # Parser functions return a list of parsed token objects and the remaining string
                parsed_objs, s = token_info[0](token, s[token_match.end('start'):])
                for item in parsed_objs:
                    append_with_string_merge(token_list, item)
            except KeyError:
                # See if we have verbatim text, which is marked by 1+ ` marks
                if token[0] == "`":
                    s = s[token_match.end('start'):]
                    verbatim_re = compile_re(r'(?P<text>.+?)`{'+str(len(token))+'}')
                    verbatim_match = verbatim_re.match(s)
                    if verbatim_match:
                        append_with_string_merge(token_list, verbatim_match.group('text'))
                        s = s[verbatim_match.end(0)]
                    else:
                        # Doesn't appear to be verbatim text, so keep going
                        append_with_string_merge(token_list, token)
                # See if we have a run of brackets
                elif token[0] == '[':
                    parsed_objs, s = parse_nested_brackets(token, s[token_match.end('start'):])
                    for item in parsed_objs:
                        append_with_string_merge(token_list, item)
                else:
                    raise RuntimeError('Found a token "{}" that isn\'t recognized'.format(token))
        else:
            # We matched the stop token instead of the start token
            to_return = token_list, token_match.group('stop'), s[token_match.end('stop'):]
            break

    return to_return


def parse_harlowe_html(s):
    passages = OrderedDict()  # So that we keep the original room order in source code

    # The story uses HTML5 custom elements, and so requires an HTML5-aware parser
    full_doc = html5lib.parseFragment(s, namespaceHTMLElements=False)
    story_elem = full_doc.find('tw-storydata')
    if not story_elem:
        raise RuntimeError('No properly-formatted story tag (tw-storydata) found')
    title = story_elem.attrib['name']
    startpid = story_elem.attrib['startnode']

    for passage_elem in story_elem.iter(PASSAGE_TAG):
        passage = TwineRoom.from_element(passage_elem)
        passages[passage.name] = passage

    return title, startpid, passages
