import argparse

import harlowe

parser = argparse.ArgumentParser(description='Find any bad links in a Harlowe game.')
parser.add_argument('input', help='Harlowe HTML file to process')

args = parser.parse_args()

with open(args.input, 'rt', encoding='utf8') as infile:
    story_str = infile.read()

story_elems, other_elems, passages = harlowe.parse_harlowe_html(story_str)

bad_passages = harlowe.build_link_graph(passages)

print(bad_passages)
