import argparse
import io
import os.path

import harlowe
from helper_functions import smartify_entities

parser = argparse.ArgumentParser(description='Turn slab quotes in a Harlowe game into smart quotes.')
parser.add_argument('input', help='Harlowe HTML file to process')
parser.add_argument('-o', '--output',
                    help='Output file (default: the input filename with "-smart" appended to the base name')

args = parser.parse_args()
if not args.output:
    root, ext = os.path.splitext(args.input)
    args.output = root+'-smart'+ext

story_str = None
with open(args.input, 'rt', encoding='utf8') as infile:
    story_str = infile.read()

story_elems, other_elems, passages = harlowe.parse_harlowe_html(story_str)

for _, passage_obj in passages.items():
    passage_obj.modify_text(smartify_entities)

modified_story_str = harlowe.reconstruct_harlowe_html(story_elems, other_elems, passages)

with open(args.output, 'wt', encoding='utf8') as outfile:
    outfile.write(modified_story_str)
