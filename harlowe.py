# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function

import re
import HTMLParser
import xml.etree.ElementTree as ET

passage_tag = 'tw-passagedata'

story_re = re.compile('<tw-storydata.+?name="([^"]+?)".+?startnode="([^"]+?)".+?>')
link_re = re.compile(r'\[\[([^]]+?)((?:->)([^]]+?))?\]\]')
discard_re = re.compile(r'\((text-style|transition|link)\s*?:\s*?".+?"\)\[(.*?)\]')
append_re = re.compile(r'\(link-reveal\s*?:\s*?"(.+?)"\)\[(.*?)\]')
append_re = re.compile(r'\(link-reveal\s*?:\s*?"(.+?)"\)\[(.*?)\]')


# Memoize computing regexes. Sadly Python 2 doesn't have functools.lru_cache()
_regex_cache = dict()
def compile_re(pattern):
	try:
		regex = _regex_cache[pattern]
	except KeyError:
		regex = re.compile(pattern)
		_regex_cache[pattern] = regex
	return regex


class TwineLink:
	def __init__(self, link_text, destination):
		self.link_text = link_text
		self.destination = destination
		
	def __str__(self):
		str_list = [ '[[', self.link_text ]
		if len(self.destination) != 1 or self.link_text != self.destination[0]:
			str_list.append('->')
			for item in self.destination:
				str_list.append(str(item))
		str_list.append(']]')
		return ''.join(str_list)
	
	
class TwineMacro:
	def __init__(self, name, code):
		self.name = name
		self.code = code
		
	def __str__(self):
		str_list = ['(', str(self.name), ':']
		for item in self.code:
			str_list.append(str(item))
		str_list.append(')')
		return ''.join(str_list)
	
	
class TwineHook:
	def __init__(self, name, hook):
		self.name = name
		self.hook = hook

	def __str__(self):
		str_list = []
		if self.name:
			str_list.append('|'+self.name+'>')
		str_list.append('[')
		for item in self.hook:
			str_list.append(str(item))
		str_list.append(']')
		return ''.join(str_list)
	
	
class TwineVariable:
	def __init__(self, name):
		self.name = name
		
	def __str__(self):
		return '$'+self.name
	
	
def parse_link(match, s):
	# Links are in the form [[str->destination]] or [[destination<-str]] or [[destination]]
	token1_list, stop_token, s1 = tokenize(s, stop_token_pattern=r'->|<-|\]\]')
	if stop_token == ']]':
		link_text_list = token1_list
		destination = token1_list
	else:
		token2_list, _, s1 = tokenize(s1, stop_token_pattern=r'\]\]')
		# Figure out which direction the thing is pointing in
		if stop_token == '->':
			link_text_list = token1_list
			destination = token2_list
		elif stop_token == '<-':
			link_text_list = token2_list
			destination = token1_list
			
	if len(link_text_list) != 1 or not isinstance(link_text_list[0], basestring):
		raise RuntimeError("Link didn't have plain link text: [[{}".format(s))
	return [TwineLink(link_text_list[0], destination)], s1
	
	
def parse_macro(match, s):
	# Macros are in the form "(name: content)"
	name_list, stop_token, s1 = tokenize(s, stop_token_pattern=':')
	if stop_token != ':':
		# Whoops, not a macro
		return [match], s
	
	if len(name_list) != 1:
		raise IndexError('Parsing a macro resulted in a tokenized list of length {}: "({}"'.format(len(name_list), s))
	strip_symbols_re = compile_re('-|_')
	name = strip_symbols_re.sub('', name_list[0].lower())
	s = s1
	content_list, stop_token, s1 = tokenize(s, stop_token_pattern=r'\)')
	
	return_list = [TwineMacro(name, content_list)]
	
	# Check to see if a hook potentially follows this macro
	if s1 and s1[0] == '[':
		hook_list, s1 = parse_hook(s1[0], s1[1:])
		return_list.extend(hook_list)
	
	return return_list, s1
	
	
def parse_hook(match, s):
	# Hooks can be named: |name>[hook] or [hook]<name|
	# or can be anonymous: [hook]
	name = None
	if match == '|':
		# Make sure this is an actual name tag
		left_tag_re = compile_re(r'(?P<name>\s|\w)+>\[')
		tag_match = left_tag_re.match(s)
		if not tag_match:
			return match, s
		name = tag_match.group('name')
		s = s[tag_match.end(0):]
		
	hook_list, stop_token, s1 = tokenize(s, stop_token_pattern=r'\]|\]<')
	if stop_token == ']<':
		# We may have a name tag
		right_tag_re = compile_re(r'(?P<name>\s|\w)+\|')
		tag_match = right_tag_re.match(s1)
		if tag_match:
			name = tag_match.group('name')
			s1 = s1[tag_match.end(0):]
		else:
			# Put the bar character back on
			s1 = '|'+s1
		
	return [TwineHook(name, hook_list)], s1

	
def parse_variable(match, s):
	variable_re = compile_re(r'[^\s]+?')
	variable_match = variable_re.match(s)
	if variable_match:
		return [TwineVariable(variable_match.group(0))], s[variable_match.end(0):]
	else:
		return [match], s
	
	
start_tokens = { '[[': [ parse_link, r'\[\[' ],
		'(': [ parse_macro, r'\(' ],
		'[': [ parse_hook, r'\[(?!\[)' ],
		'|': [ parse_hook, r'\|' ],
		'$': [ parse_variable, r'\$' ]
	}


# Verbatim token starts are any number of consecutive ` marks and so are handled separately
start_token_patterns = '(?P<start>('+'|'.join([s[1] for s in start_tokens.values()])+r")|(`+?))"


def append_with_string_merge(seq, new_item):
	if seq and isinstance(new_item, basestring) and isinstance(seq[-1], basestring):
		s = seq.pop()
		seq.append(s+new_item)
	else:
		seq.append(new_item)


def tokenize(s, stop_token_pattern=None):
	token_list = []
	if not stop_token_pattern:
		token_re = compile_re(start_token_patterns)
	else:
		token_re = compile_re(start_token_patterns+'|(?P<stop>'+stop_token_pattern+')')
	
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
				tokenized_objs, s = token_info[0](token_match.group('start'), s[token_match.end('start'):])
				for item in tokenized_objs:
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
						append_with_string_merge(token)
				else:
					raise RuntimeError('Found a token "{}" that isn\'t recognized'.format(token))
		else:
			# We matched the stop token instead of the start token
			to_return = token_list, token_match.group('stop'), s[token_match.end('stop'):]
			break
			
	return to_return
		

class TwineRoom:
	pid = ''
	name = ''
	contents = ''
	destinations = set()
	parents = set()
	
	
	# todo this may not be needed -- xml parser may scrub escaped chars already
	def unescape(self):
		h = HTMLParser.HTMLParser()
		
		old_name = self.name
		self.pid = h.unescape(self.pid)
		self.name = h.unescape(self.name)
		self.contents = h.unescape(self.contents)
		
		if name != old_name:
			return old_name
		return None
	

def parse_twine_xml(s):
	passages = dict()
	
	# The opening story tag contains a bare attribute, which
	# isn't allowed in XML, so we process that tag using a regex (sigh)
	# and then get rid of its attributes
	
	story_info = story_re.search(s)
	if not story_info:
		raise RuntimeError('No properly-formatted story tag (tw-storydata) found')
	title, startpid = story_info.group(1, 2)
	
	s = story_re.sub('<tw-storydata>', s)
	
	root = ET.fromstring(s)
	
	for passage_elem in root.iter(passage_tag):
		passage = TwineRoom()
		passage.pid = passage_elem.attrib['pid']
		passage.name = passage_elem.attrib['name']
		passage.contents = passage_elem.text
		passages[passage.name] = passage
		
	return title, startpid, passages
	

teststring = '''<tw-storydata name="Will Not Let Me Go" startnode="1" creator="Twine" creator-version="2.0.10" ifid="6106B74D-7DB6-435A-8557-DC44D016231B" format="Harlowe" options="" hidden>
<tw-passagedata pid="1" name="Funeral Opening" tags="funeral" position="388,116">Funerals have become a kind of spectator sport for you. You come to see who&#39;ll show up, what(link: &quot;...&quot;)[ well-meaning but dumb things they&#39;ll say, that sort of thing.

This one&#39;s in the late afternoon instead of the heat of the day, thank goodness. There aren&#39;t any clouds between you and the sun, just red red rays that color everyone crimson.

It&#39;s the usual graveside arrangement, with one of those green tents set up over the open grave and the casket on (link-reveal: &quot;a&quot;)[&amp;mdash;some kind of contraption that&#39;ll drop it into the hole once the platitudes are done and no one&#39;s looking any more. The funeral home workers scattered cheap plastic seats around the grave like birdseed. At least you got one of them. There&#39;s not much fun about being old, but they do give you a seat when you damn well need one.

Being so close to the front, down with the [[mourners]], means you&#39;re also close to the preacher who&#39;s busy pretending he knew the deceased, talking over the sound of the [[tent fringe]] snapping in the wind.]]</tw-passagedata>
<tw-passagedata pid="2" name="after verses" tags="funeral" position="388,808">It&#39;s not a bad Bible passage, and the preacher didn&#39;t launch into a bunch of hellfire and damnation talk. You&#39;ve been to one funeral that went that way. It was like being strapped in a dentist&#39;s chair, and the only thing that made it tolerable was that you weren&#39;t paying for the experience.

Besides, the verses must&#39;ve done their job because the [[man next to you]] is trying very hard not to tear up, though he&#39;s not succeeding. He glances over and sees you staring, so you look down and fiddle with the [[funeral program]] they handed you.</tw-passagedata>
<tw-passagedata pid="3" name="tent fringe" tags="" position="272,308">The tent&#39;s there in case of rain, which is damn foolish. There aren&#39;t even [[clouds]] to hint at rain. Shame it isn&#39;t raining, though. Make it more of a proper funeral. And you&#39;ll take your distractions where you can get them. After you&#39;ve been to a bunch, funerals are like oatmeal, all gray and bland no matter what you dump into them.</tw-passagedata>
<tw-passagedata pid="4" name="preacher" tags="" position="392,644">The preacher means well, which is kind of his job description when you get down to it. Mean well, and visit the orphans and the widows. Most else is noise and distraction. He&#39;s got on a dark and somber (link: &quot;smock&quot;)[//suit//, the kind that&#39;s meant to show he&#39;s there on God&#39;s business.

He gestures with his worn, dog-eared Bible and flips it open one-handed. You wonder if he practices that move in front of a mirror. &quot;I&#39;d like to read from Paul&#39;s first letter to the church in Corinth,&quot; he says all serious-like.

&quot;Behold, I shew you a mystery; We shall not all sleep, but we shall all be changed,
in a moment, in the twinkling of an eye, at the last trump:
for the trumpet shall sound, and the dead shall be raised incorruptible, and we shall be changed.

&quot;For this corruptible must put on incorruption, and this mortal must put on immortality.

&quot;So when this corruptible shall have put on incorruption, and this mortal shall have put on immortality, then shall be brought to pass the saying that is written, (link-reveal: &quot;Death is swallowed up in victory.&quot;)[

&quot;O death, (link-reveal: &quot;where is thy sting?&quot;)[
&quot;O grave, (link-reveal: &quot;where is thy victory?&quot;)[

&quot;The sting of death is sin; and the strength of sin is the law. But thanks be to God, which giveth us the victory through [[our Lord Jesus Christ.&quot;-&gt;after verses]]
]]]]</tw-passagedata>
<tw-passagedata pid="5" name="mourners" tags="" position="512,304">It&#39;s the usual mix of folks. Some are there because they loved the person who&#39;s died. Some are there because they&#39;re expected to be, like you are. Many are dressed in their everyday clothes, which is annoying, just a bit. If you&#39;re going to go to a funeral, dress up. The dead person won&#39;t know, but you will, and showing some respect&#39;s the right thing to do. There are a couple of other people in suits or sports coats besides you and the [[preacher]].</tw-passagedata>
<tw-passagedata pid="6" name="clouds" tags="" position="364,456">There ought to be clouds. Some sign that God&#39;s hiding his face in sadness over the person He&#39;s taken. But there aren&#39;t any. The only evidence of God is the [[preacher]] who&#39;s being all sober and serious.</tw-passagedata>
<tw-passagedata pid="7" name="man next to you" tags="" position="300,968">He&#39;s sandy-haired, like you used to be before you went gray and then white. He&#39;s in a suit(if: (history:) contains &quot;mourners&quot;)[ like you and the pastor,] and his face has that complete stillness that shows that he&#39;s working hard not to cry. He keeps twisting his wedding ring around and around his finger(if: (history:) contains &quot;funeral program&quot;)[. He must have [[known her well]]](else:)[ like how you&#39;re [[twisting that funeral program-&gt;funeral program]]].</tw-passagedata>
<tw-passagedata pid="8" name="funeral program" tags="" position="460,972">It&#39;s got one of those glowing Thomas Kinkade paintings on the front. The inside has the dead person&#39;s name, Virginia, along with a terrible poem and &quot;With Our Deepest Sympathy&quot; above the name of the funeral home. Because nothing conveys real sympathy like a small fold of paper that was printed by the thousands.

It&#39;s also full of those infuriating(link: &quot;...&quot;)[ euphemisms like &quot;Entered Into Rest&quot; instead of &quot;Died&quot; and &quot;Interment&quot; instead of &quot;Burial&quot;. It&#39;s another piece of the junk that gathers around a dead person(if: (history:) contains &quot;man next to you&quot;)[, all of it pretending to have [[known her well]].](else:)[. Maybe the [[man next to you]] finds it comforting.]]
</tw-passagedata>
<tw-passagedata pid="9" name="known her well" tags="" position="375,1135">&quot;I&#39;d like to close by singing one of Virginia&#39;s favorite hymns, &#39;It Is Well With My Soul&#39;,&quot; the preacher says. &quot;If you&#39;ll join me.&quot;

It&#39;s one of your favorite hymns, too. The man who wrote it did so after a ship sunk with his four daughters on board, so it&#39;s a fitting hymn for the occasion. &quot;When peace like a river attendeth my way,&quot; you sing out, your baritone voice rougher than it used to be. It&#39;s been(link: &quot;...&quot;)[&amp;mdash;well, years since you sang in the choir at church, and you still miss it.

Then the graveside service is over. The man next to you stands up and rests his hand on the casket, gently, as if to convince himself that it&#39;s there. &quot;Love you, mom,&quot; he whispers. The woman next to him leans on the casket, letting it keep her upright. The wind lifts her fine gold hair into a halo around her, and the sun&#39;s red light catches her tears. Embarassed by the raw emotion, you put your hand on your four-legged cane and start to stand. The sandy-haired man takes your other arm, surprising you.

&quot;C&#39;mon, dad,&quot; he says. &quot;[[Let&#39;s get you to the car-&gt;Title]].&quot;]
</tw-passagedata>
<tw-passagedata pid="10" name="Title" tags="" position="376,1281">(text-style: &quot;bold&quot;)[Will Not Let Me Go]
(live: 2s)[(transition: &quot;fade-in&quot;)[by Stephen Granade](stop:)]

(live: 4s)[(goto: &quot;Waffle House&quot;)(stop:)]</tw-passagedata>
<tw-passagedata pid="11" name="Waffle House" tags="" position="824,120">&quot;That&#39;s one large order of hashbrowns, scattered, smothered, covered; one waffle with bacon; two eggs, scrambled, side of grits; and an oatmeal with fruit and a glass of OJ.&quot; Gerald grimaces across from you. Ever since that scare last year he&#39;s been watching what he eats and being jealous watching what other people eat. You like the man, but he&#39;s not going to get you to give up hashbrowns with cheese and onions. &quot;I&#39;ll be back, top off those coffees for you.&quot;

As the waitress walks away, Will leans forward. &quot;Okay, Dick, spill it. What&#39;ve you been waiting to tell us?&quot;

Dick grins. &quot;Finished the kitchen yesterday.&quot;

&quot;About time,&quot; you say. 

Gerald looks over at you. &quot;Fred,&quot; he says, with that tone of voice that means he wants everyone to try to get along. He takes things far more seriously than he should.

&quot;No, of course I&#39;m glad you&#39;re done. You&#39;ve been working on that remodel for...well, I can&#39;t even remember how long.&quot; You smile, but you really can&#39;t remember. There&#39;s a [[blank spot-&gt;new appliances]] there.
</tw-passagedata>
<tw-passagedata pid="12" name="new appliances" tags="" position="824,270">&quot;The new appliances&#39;re in, the flooring&#39;s down, and Joan can&#39;t be happier.&quot;

&quot;I bet,&quot; Gerald says, setting down his coffee mug. &quot;She regret asking you to do all that work? She can&#39;t have liked not being able to use the kitchen for months.&quot;

Dick considers. &quot;I don&#39;t think so. That kitchen was in bad need of updating &amp;mdash; had been for years. I&#39;d been putting it off, but once I retired I left my excuses behind at the office.&quot; Dick&#39;s someone who loves working with his hands, and now that he has free time, he&#39;s working through all of the projects he&#39;d been talking about but not doing for years and years.

Dick&#39;s mention of retirement reminds you that you&#39;ve decided to retire as well. You start to tell the guys about your [[upcoming retirement-&gt;retirement]], but then you [[hesitate-&gt;next project]].
</tw-passagedata>
<tw-passagedata pid="267" name="now you&#39;re really really lost" tags="" position="9516,716">There&#39;s nothing for it. You&#39;re going to have to find either a cop to direct you or a pay phone to call Virginia for help.

Guess you won&#39;t be [[driving alone-&gt;driving alone end]] for much longer.</tw-passagedata>
<tw-passagedata pid="268" name="driving alone end" tags="" position="9516,866">(live: 2s)[(goto: &quot;pastor visits&quot;)(stop:)]</tw-passagedata>
</tw-storydata>'''


def main():
	with open('Twinetest.txt', 'rt') as fh:
		contents = fh.read()
	
	#title, startpid, rooms = parse_twine_xml(teststring)
	title, startpid, rooms = parse_twine_xml(contents)

	for name, room in rooms.items():
		contents = tokenize(room.contents)[0]
		print('----\n'+'&&'.join([str(s) for s in contents]))
		#break
		
	return

	for name, room in rooms.items():
		print('{}: {}'.format(name, room.get_plain_contents()))

	for name, room in rooms.items():
		missing_links = room.find_destinations(rooms)
		for dest in room.destinations:
			print('. {} -> {}'.format(room.name, dest.name))
		if missing_links:
			print('\n'.join(missing_links))
		pass #new_name = room.
		
if __name__ == '__main__':
	main()