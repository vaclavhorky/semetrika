#!/usr/bin/env python3

import sys
import argparse

from scan import Verse
from lengths import LengthDictionary

argparser = argparse.ArgumentParser()
argparser.add_argument("-i", "--input",
                       help=(
                           "file with verses to analyse" +
                           " (if none is given, read from stdin)"
                           ))
argparser.add_argument("--brevize",
                    help=(
                        "for fully macronized input,"
                        " treat unmarked vowels as short"
                        ),
                    action="store_true")
argparser.add_argument("--nolengths",
                    help=(
                        "don't try to add unambiguous lengths"
                        ),
                    action="store_true")
args = argparser.parse_args()

input_file = args.input
unmarked_short = args.brevize


if not args.nolengths:
    default_ld = LengthDictionary()
    try:
        default_ld.load(".default_length_dictionary.pickle")
        length_dictionary=default_ld.dictionary
    except FileNotFoundError:
        print("WARNING: length dictionary not found, cannot add lengths")
        length_dictionary=None
else:
    length_dictionary=None

if input_file:
    try:
        with open(input_file, "r") as file:
            for line in file:
                verse = Verse(line, length_dictionary=length_dictionary,
                              unmarked_short=unmarked_short)
                verse.print_scansions()
                print()
    except FileNotFoundError:
        print("ERROR: file {input_file!r} not found")

else:
    for line in sys.stdin:
        verse = Verse(line, length_dictionary=length_dictionary,
                      unmarked_short=unmarked_short)
        verse.print_scansions()
        print()
