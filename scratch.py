import os.path

import harlowe
from helper_functions import smartify_entities


def test_smartifying():
    args = lambda: None

    args.input = 'Will Not Let Me Go.html'

    root, ext = os.path.splitext(args.input)
    args.output = root+'-smart'+ext

    story_str = None
    with open(args.input, 'rt') as infile:
        story_str = infile.read()

    story_elems, other_elems, passages = harlowe.parse_harlowe_html(story_str)

    for _, passage_obj in passages.items():
        passage_obj.modify_text(smartify_entities)

    modified_story_str = harlowe.reconstruct_harlowe_html(story_elems, other_elems, passages)

    with open(args.output, 'wt') as outfile:
        outfile.write(modified_story_str)


def test_link_testing():
    args = lambda: None

    args.input = 'Will Not Let Me Go-smart.html'


    story_str = None
    with open(args.input, 'rt') as infile:
        story_str = infile.read()

    story_elems, other_elems, passages = harlowe.parse_harlowe_html(story_str)

    bad_passages = harlowe.build_link_graph(passages)

    print(bad_passages)

test_smartifying()
#test_link_testing()
