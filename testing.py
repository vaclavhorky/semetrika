#!/usr/bin/env python3

from collections import Counter

from lengths import *
from scan import *

default_ld = LengthDictionary()
default_ld.load(".default_length_dictionary.pickle")

class Test():
    """Class for testing Semetrika with and without using
    length dictionary."""

    def __init__(self, lines):
        # skip short lines
        self.lines = [line for line in lines
                       if len(line) > 10]
        self.verse_count = len(self.lines)
        # without length dictionary
        self.verses_without_lengths = [Verse(line, length_dictionary=None)
                                 for line in self.lines]
        # with
        self.verses_with_lengths = [Verse(line, length_dictionary=
                                          default_ld.dictionary)
                                   for line in self.lines]
        # verses which cannot be scanned
        self.verses_with_no_scansion = [verse for verse
                                       in self.verses_without_lengths
                                       if verse.scansion_count == 0]
        # verses which are scanned differently with and without
        # the dictionary
        self.verses_with_different_scansions = [(wo, w) for wo, w
                                               in zip(self.verses_without_lengths,
                                                      self.verses_with_lengths)
                                               if wo.scansion_count != w.scansion_count ]
        self.statistics = None
        self.count_statistics()

    # number of verses scanned in zero to six ways with and
    # without the length dictionary
    def count_statistics(self):
        statistics = {"without": Counter(), "with": Counter()}
        for verse in self.verses_without_lengths:
            statistics["without"][verse.scansion_count] += 1
        for verse in self.verses_with_lengths:
            statistics["with"][verse.scansion_count] += 1
        self.statistics = statistics
        return
    
    def print_statistics(self):
        """Prints number of verses scanned in zero to six ways
        without and with the length dictionary."""
        print(f"NUMBER OF VERSES: {self.verse_count}\n")
        print("\t| W/O\tWITH\t| W/O\tWITH")
        # there cannot be more than six scansions
        for scansion_count in range(7):
            wo_count = self.statistics["without"][scansion_count]
            wo_pct = wo_count*100 // self.verse_count
            w_count = self.statistics["with"][scansion_count]
            w_pct = w_count*100 // self.verse_count
            if not wo_count == w_count == 0:
                print(f"{scansion_count}\t| {wo_count}\t{w_count}"
                      + f"\t| {wo_pct} %\t{w_pct} %")
        return
    
    def print_differences(self):
        """Prints verses which cannot be scanned and those which
        are scanned differently without and with length dictionary."""
        for verse_wo, verse_with in zip(self.verses_without_lengths,
                                        self.verses_with_lengths):
            if verse_wo.scansion_count == 0:
                print("NO SCANSION FOUND:")
                verse_wo.print_scansions()
                print(f"\n{'='*30}\n")
            elif verse_wo.scansion_count != verse_with.scansion_count:
                print("DIFFERENT NUMEBR OF SCANSIONS:")
                print("WITHOUT LENGTH DICTIONARY:")
                verse_wo.print_scansions()
                print("WITH LENGTH DICTIONARY:", end=" ")
                verse_with.print_verse()
                verse_with.print_scansions()
                print(f"\n{'='*30}\n")
        return
