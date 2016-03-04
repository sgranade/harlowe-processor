# coding: utf-8

from harlowe import *


# TOKENIZING AND PARSING

class TestTokenizingAndParsing:

    def test_tokenize_handles_simple_links(self):
        contents = '[[a simple link]]'

        results, _, _ = tokenize(contents)

        assert(['a simple link'] == results[0].link_text)
        assert(not results[0].passage_name)

    def test_tokenize_handles_right_arrow_links(self):
        contents = '[[the stars my->destination]]'

        results, _, _ = tokenize(contents)

        assert(['the stars my'] == results[0].link_text)
        assert(['destination'] == results[0].passage_name)

    def test_tokenize_handles_left_arrow_links(self):
        contents = '[[destination<-the stars my]]'

        results, _, _ = tokenize(contents)

        assert(['the stars my'] == results[0].link_text)
        assert(['destination'] == results[0].passage_name)

    def test_tokenize_handles_multiple_right_arrow_links(self):
        contents = '[[a->b->c->d]]'

        results, _, _ = tokenize(contents)

        assert(['a->b->c'] == results[0].link_text)
        assert(['d'] == results[0].passage_name)

    def test_tokenize_handles_multiple_left_arrow_links(self):
        contents = '[[d<-c<-b<-a]]'

        results, _, _ = tokenize(contents)

        assert(['c<-b<-a'] == results[0].link_text)
        assert(['d'] == results[0].passage_name)

    def test_tokenize_variable_names_can_have_underscores(self):
        contents = '$var_name'

        results, _, _ = tokenize(contents)

        assert('var_name' == results[0].name)

    def test_tokenize_handles_simple_anonymous_hooks(self):
        contents = '[this is a simple anonymous hook]'

        results, _, _ = tokenize(contents)

        assert(None == results[0].nametag)
        assert(['this is a simple anonymous hook'] == results[0].hook)

    def test_tokenize_binds_hooks_tightly_to_macros(self):
        contents = '(macro:)[[Nested hook]]'

        results, _, _ = tokenize(contents)

        assert(isinstance(results[0], TwineMacro))
        assert(isinstance(results[1], TwineHook))
        assert(isinstance(results[1].hook[0], TwineHook))
        assert(['Nested hook'] == results[1].hook[0].hook)

    def test_tokenize_can_tell_when_a_link_is_actually_a_nested_hook(self):
        contents = '[[Nested hook] ]'

        results, _, _ = tokenize(contents)

        assert(isinstance(results[0], TwineHook))
        assert(isinstance(results[0].hook[0], TwineHook))
        assert(['Nested hook'] == results[0].hook[0].hook)

    def test_macro_names_can_have_hyphens(self):
        contents = '(tExt-style:)'

        results, _, _ = tokenize(contents)

        assert(isinstance(results[0], TwineMacro))
        assert('tExt-style' == results[0].name_in_source)
        # Remember that hyphens get stripped out of the canonical macro names, plus they're made lower case
        assert('textstyle' == results[0].canonical_name)
        assert([] == results[0].code)

    def test_macro_names_can_have_variables(self):
        contents = '($var_name:)'

        results, _, _ = tokenize(contents)
        macro_obj = results[0]

        assert(isinstance(macro_obj.name_in_source, TwineVariable))
        assert(isinstance(macro_obj.canonical_name, TwineVariable))

    def test_hook_can_have_left_tag(self):
        contents = '|tag>[hook]'

        results, _, _ = tokenize(contents)

        assert(isinstance(results[0], TwineHook))
        assert('tag' == results[0].nametag)
        assert(['hook'] == results[0].hook)

    def test_hook_can_have_right_tag(self):
        contents = '[hook]<tag|'

        results, _, _ = tokenize(contents)

        assert(isinstance(results[0], TwineHook))
        assert('tag' == results[0].nametag)

    def test_hook_tag_can_have_hyphens(self):
        contents = '[hook]<ca-age|'

        results, _, _ = tokenize(contents)

        assert(isinstance(results[0], TwineHook))
        assert('ca-age' == results[0].nametag)

    def test_hooks_can_contain_links(self):
        contents = '[ [[link text]] ]'

        results, _, _ = tokenize(contents)

        assert(isinstance(results[0].hook[1], TwineLink))
        assert(['link text'] == results[0].hook[1].link_text)
        assert(not results[0].hook[1].passage_name)


# STRING VERSION OF OBJECTS

class TestStringVersionOfObjects:

    def test_string_version_of_a_simple_link(self):
        link_obj = TwineLink(['passage name'])
        link_str = str(link_obj)

        assert('[[passage name]]' == link_str)

    def test_string_version_of_a_right_arrow_link(self):
        link_obj = TwineLink(['link text'], ['this room\'s got "quote marks"'])
        link_str = str(link_obj)

        assert('[[link text-&gt;this room&#39;s got &quot;quote marks&quot;]]' == link_str)

    def test_string_version_of_a_left_arrow_link(self):
        link_obj = TwineLink(['link text'], ['this room\'s got "quote marks"'], passage_on_right=False)
        link_str = str(link_obj)

        assert('[[this room&#39;s got &quot;quote marks&quot;&lt;-link text]]' == link_str)

    def test_string_version_of_a_simple_macro(self):
        macro_obj = TwineMacro('goto', [' "passage link"'])
        macro_str = str(macro_obj)

        assert('(goto: &quot;passage link&quot;)' == macro_str)

    def test_string_version_of_a_macro_preserves_dashes(self):
        macro_obj = TwineMacro('go-to', [' "passage link"'])
        macro_str = str(macro_obj)

        assert('(go-to: &quot;passage link&quot;)' == macro_str)

    def test_string_version_of_a_hook_without_a_tag(self):
        hook_obj = TwineHook(["simple text 'mkay?"])
        hook_str = str(hook_obj)

        assert('[simple text &#39;mkay?]' == hook_str)

    def test_string_version_of_a_hook_with_a_right_tag(self):
        hook_obj = TwineHook(["simple text 'mkay?"], 'right-tag', nametag_on_right=True)
        hook_str = str(hook_obj)

        assert('[simple text &#39;mkay?]&lt;right-tag|' == hook_str)

    def test_string_version_of_a_hook_with_a_left_tag(self):
        hook_obj = TwineHook(["simple text 'mkay?"], 'left-tag', nametag_on_right=False)
        hook_str = str(hook_obj)

        assert('|left-tag&gt;[simple text &#39;mkay?]' == hook_str)


class TestTextModifications:

    def test_variable_names_arent_modified(self):
        variable_obj = TwineVariable('name')

        variable_obj.modify_text(lambda s: s.upper())

        assert('name' == variable_obj.name)

    def test_modifying_hook_changes_hook_contents(self):
        hook_obj = TwineHook(['text'], nametag='tag')

        hook_obj.modify_text(lambda s: s.upper())

        assert(['TEXT'] == hook_obj.hook)

    def test_modifying_hook_leaves_nametags_alone(self):
        hook_obj = TwineHook(['text'], nametag='tag')

        hook_obj.modify_text(lambda s: s.upper())

        assert('tag' == hook_obj.nametag)

    def test_hook_contents_are_modified_recursively(self):
        inner_hook_obj = TwineHook(['inner'], nametag='tag')
        hook_obj = TwineHook(['outer', inner_hook_obj])

        hook_obj.modify_text(lambda s: s.upper())

        assert('OUTER' == hook_obj.hook[0])
        assert(['INNER'] == hook_obj.hook[1].hook)

    def test_links_with_no_separate_passage_arent_modified(self):
        link_obj = TwineLink(['text'])

        link_obj.modify_text(lambda s: s.upper())

        assert(['text'] == link_obj.link_text)

    def test_links_with_a_passage_are_modified(self):
        link_obj = TwineLink(['text'], 'passage_name')

        link_obj.modify_text(lambda s: s.upper())

        assert(['TEXT'] == link_obj.link_text)

    def test_link_contents_are_modified_recursively(self):
        inner_link_obj = TwineLink(['inner'], 'passage_name')
        link_obj = TwineLink(['outer', inner_link_obj], 'passage_name')

        link_obj.modify_text(lambda s: s.upper())

        assert('OUTER' == link_obj.link_text[0])
        assert(['INNER'] == link_obj.link_text[1].link_text)

    def test_macro_names_arent_modified(self):
        macro_obj = TwineMacro('macro name', ['code'])

        macro_obj.modify_text(lambda s: s.upper())

        assert('macro name' == macro_obj.name_in_source)
        assert('macro name' == macro_obj.canonical_name)

    def test_macro_contents_are_modified(self):
        macro_obj = TwineMacro('macro name', ['code'])

        macro_obj.modify_text(lambda s: s.upper())

        assert(['CODE'] == macro_obj.code)

    def test_macro_contents_are_modified_recursively(self):
        inner_macro_obj = TwineMacro('inner macro name', ['inner macro code'])
        macro_obj = TwineMacro('outer macro name', ['outer macro code', inner_macro_obj])

        macro_obj.modify_text(lambda s: s.upper())

        assert('OUTER MACRO CODE' == macro_obj.code[0])
        assert(['INNER MACRO CODE'] == macro_obj.code[1].code)

    def test_rooms_recursively_modify_everything(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
              + '|tag&gt;[hook text plus (macro: "code")] $variable [[link text-&gt;passage]]' \
              + '</tw-passagedata>'
        passage_obj = TwineRoom.from_string(passage_str)

        passage_obj.modify_text(lambda s: s.upper())

        assert('HOOK TEXT PLUS ' == passage_obj.parsed_contents[0].hook[0])
        assert([' "CODE"'] == passage_obj.parsed_contents[0].hook[1].code)
        assert('variable' == passage_obj.parsed_contents[2].name)
        assert(['LINK TEXT'] == passage_obj.parsed_contents[4].link_text)


class TestRoundTripping:

    def test_round_tripping_an_empty_passage(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_round_tripping_a_passage_with_quote_marks(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + '&quot;I&#39;ve got both single and double quotes.&quot;' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_passage_obj_to_string_prefers_parsed_contents(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + '&quot;I&#39;ve got both single and double quotes.&quot;' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        passage_obj.parse_contents()
        passage_obj.contents += 'extra text'
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_parsing_and_round_tripping_right_arrow_links(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + 'This has a link: [[link text-&gt;this&#39;s the passage name]]' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        passage_obj.parse_contents()
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_parsing_and_round_tripping_left_arrow_links(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + 'This has a link: [[passage name&lt;-link text]]' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        passage_obj.parse_contents()
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_parsing_and_round_tripping_macro_with_dashes(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + 'This has a macro with a dash: (go-to: &quot;new passage&quot;)' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        passage_obj.parse_contents()
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_parsing_and_round_tripping_anonymous_hook(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + 'Anonymous hook [ that only contains text ]' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        passage_obj.parse_contents()
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_parsing_and_round_tripping_hook_with_right_tag(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + 'Named hook [ that only contains text ]&lt;right tag|' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        passage_obj.parse_contents()
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

    def test_parsing_and_round_tripping_hook_with_left_tag(self):
        passage_str = '<tw-passagedata pid="1" name="Opening Scene" tags="40% fadein nosave" position="388,116">' \
                      + 'Named hook |left tag&gt;[ that only contains text ]' \
                      + '</tw-passagedata>'

        passage_obj = TwineRoom.from_string(passage_str)
        passage_obj.parse_contents()
        new_passage_str = str(passage_obj)

        assert(passage_str == new_passage_str)

