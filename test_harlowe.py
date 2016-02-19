# coding: utf-8

from twine import *

def test_tokenize_handles_simple_links():
	contents = '[[a simple link]]'
	
	results, _, _ = tokenize(contents)
	
	assert('a simple link' == results[0].link_text)
	assert(['a simple link'] == results[0].destination)


def test_tokenize_handles_right_arrow_links():
	contents = '[[the stars my->destination]]'
	
	results, _, _ = tokenize(contents)
	
	assert('the stars my' == results[0].link_text)
	assert(['destination'] == results[0].destination)	

def test_tokenize_handles_left_arrow_links():
	contents = '[[destination<-the stars my]]'
	
	results, _, _ = tokenize(contents)
	
	assert('the stars my' == results[0].link_text)
	assert(['destination'] == results[0].destination)	


def test_tokenize_handles_multiple_right_arrow_links():
	contents = '[[a->b->c->d]]'
	
	results, _, _ = tokenize(contents)
	
	assert('a->b->c' == results[0].link_text)
	assert(['d'] == results[0].destination)	


def test_tokenize_handles_multiple_left_arrow_links():
	contents = '[[d<-c<-b<-a]]'
	
	results, _, _ = tokenize(contents)
	
	assert('c<-b<-a' == results[0].link_text)
	assert(['d'] == results[0].destination)


def test_tokenize_variable_names_can_have_underscores():
	contents = '$var_name'
	
	results, _, _ = tokenize(contents)
	
	assert('var_name' == results[0].name)


def test_tokenize_handles_simple_anonymous_hooks():
	contents = '[this is a simple anonymous hook]'
	
	results, _, _ = tokenize(contents)
	
	assert(None == results[0].name)
	assert(['this is a simple anonymous hook'] == results[0].hook)


def test_tokenize_binds_hooks_tightly_to_macros():
	contents = '(macro:)[[Nested hook]]'
	
	results, _, _ = tokenize(contents)
	
	assert(isinstance(results[0], TwineMacro))
	assert(isinstance(results[1], TwineHook))
	assert(isinstance(results[1].hook[0], TwineHook))
	assert(['Nested hook'] == results[1].hook[0].hook)


def test_tokenize_can_tell_when_a_link_is_actually_a_nested_hook():
	contents = '[[Nested hook] ]'
	
	results, _, _ = tokenize(contents)
	
	assert(isinstance(results[0], TwineHook))
	assert(isinstance(results[0].hook[0], TwineHook))
	assert(['Nested hook'] == results[0].hook[0].hook)


def test_macro_names_can_have_hyphens():
	contents = '(text-style:)'
	
	results, _, _ = tokenize(contents)
	
	assert(isinstance(results[0], TwineMacro))
	# Remember that hyphens get stripped out of macro names
	assert('textstyle' == results[0].name)
	assert([] == results[0].code)


def test_hook_can_have_left_tag():
	contents = '|tag>[hook]'
	
	results, _, _ = tokenize(contents)
	
	assert(isinstance(results[0], TwineHook))
	assert('tag' == results[0].name)
	assert(['hook'] == results[0].hook)


def test_hook_can_have_right_tag():
	contents = '[hook]<tag|'
	
	results, _, _ = tokenize(contents)
	
	assert(isinstance(results[0], TwineHook))
	assert('tag' == results[0].name)


def test_hook_tag_can_have_hyphens():
	contents = '[hook]<ca-age|'
	
	results, _, _ = tokenize(contents)
	
	assert(isinstance(results[0], TwineHook))
	assert('ca-age' == results[0].name)


def test_hooks_can_contain_links():
	contents = "[ [[link text]] ]"

	results, _, _ = tokenize(contents)
	
	assert(isinstance(results[0].hook[1], TwineLink))
	assert('link text' == results[0].hook[1].link_text)
	assert(['link text'] == results[0].hook[1].destination)

test_hooks_can_contain_links()
