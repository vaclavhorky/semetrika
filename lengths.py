#!/usr/bin/env python3

import sys
import os
import pickle

from scan import *

class LengthDictionary(dict):
    """Class for learning monophthong lengths from a corpus
    of hexameters."""

    def __init__(self):
        # super().__init__()   # initialize as an empty dictionary
        self.frequencies = None
        self.dictionary = None
        self.verses = []

    @staticmethod
    def count_length_frequencies_for_verse(line, length_frequencies, tokens, sequence):
        sequence_i = 0
        
        for token in tokens:
            if token.type_ != "word":
                continue
                    
            form = strip_diacritics(token.lowercase_form)
            segments = token.segments            

            # if the form wasn't encoutered yet, initialize it
            if form not in length_frequencies:
                vowels = []
                for segment in segments:
                    # diphthongs and final nasal vowels always scan as long, so they are not interesting
                    if segment.subtype == "monophthong":
                        vowels.append({"long": 0, "short": 0, "unknown": 0})
                length_frequencies[form] = vowels

            vowel_i = 0
            for segment in segments:
                # diphthongs and final nasal vowels always scan as long, so they are not interesting
                if segment.subtype == "monophthong":
                    if not segment.elided:
                        # if the length (only given for oral monophthongs) is already
                        # known (either because it was given in user's input, or
                        # because it was in a previously created length dictionary)
                        if segment.length == "long" or segment.length == "short":
                            length_frequencies[form][vowel_i][segment.length] += 1
                        # if the syllable is short, the vowel has to be short as well
                        elif sequence[sequence_i] == "u":
                            length_frequencies[form][vowel_i]["short"] += 1
                        # if the syllable is long, we can infer the vowel is short
                        # only if it is in a positively open syllable
                        elif sequence[sequence_i] == "-" and segment.coda == "open":
                            length_frequencies[form][vowel_i]["long"] += 1
                        # vowel in a (possibly) closed syllable
                        else:
                            length_frequencies[form][vowel_i]["unknown"] += 1
                    else:
                        if segment.length == "long" or segment.length == "short":
                            length_frequencies[form][vowel_i][segment.length] += 1
                        else:
                            length_frequencies[form][vowel_i]["unknown"] += 1
                    vowel_i += 1
                if segment.type_ == "vowel" and not segment.elided:
                    sequence_i += 1
                    
        return

    # for each word token in unambigously scanned verses,
    # count how many times each of its vowels was found short, long, or unknown
    def count_length_frequencies(self, paths, *args, **kwargs):
        print("I am trying to learn which vowel lengths",
              "in which words are unambiguous.",
              "This should take some time",
              "(if it doesn't, the corpus you have given me",
              "is probably too small).",
             file=sys.stderr)
        length_frequencies = {}
        for path in paths:
            with open(path, "r") as file:
                for line in file:
                    verse = Verse(line, *args)
                    if len(verse.metrical_sequences) == 1:   # consider only unambiguously analysed verses
                        self.count_length_frequencies_for_verse(line, length_frequencies,
                                                           verse.tokens,
                                                           verse.metrical_sequences[0])
                print(f"DONE: {path}", file=sys.stderr)
        self.frequencies = length_frequencies
        return

    # find out which lengths in which words seem to be unambigous
    def make_length_dictionary(self,
                               minimal_frequency=20, maximum_of_contradictions=3):
        """Input: length_frequencies,
        minimal_frequency -- of the short/long monophthong,
        maximum_of_contradictions -- maximal frequency of the opposite length.
        The default values are just wild guesses."""
        length_dictionary = {}
        for word, vowels in self.frequencies.items():
            safe = False    # is there at least one vowel in the word which can be safely assigned length?
            vowel_lengths = []
            for vowel in vowels:
                if (
                    vowel["long"] >= minimal_frequency and
                    vowel["short"] <= maximum_of_contradictions
                ):
                    vowel_lengths.append("long")
                    safe = True
                elif (
                    vowel["short"] >= minimal_frequency and
                    vowel["long"] <= maximum_of_contradictions
                ):
                    vowel_lengths.append("short")
                    safe = True
                else:
                    vowel_lengths.append("unknown")
            if safe:
                length_dictionary[word] = vowel_lengths
        self.dictionary = length_dictionary
        return

    def save(self, path):
        with open(path, "wb") as file:
            pickle.dump(self, file)

    def load(self, path, / , load_frequencies=False):
        with open(path, "rb") as file:
            loaded = pickle.load(file)
            self.dictionary = loaded.dictionary
            if load_frequencies:
                self.frequencies = loaded.frequencies

    def print_with_lengths(self, word):
        token = Token(word, type_="word", length_dictionary=self.dictionary)
        token.normalize_cases()
        form = strip_diacritics(token.lowercase_form)
        if form not in self.dictionary:
            print(f"({form})")
        else:
            form_with_lengths = ""
            token.segmentize()
            token.add_lengths()
            form_with_lengths = [segment.lowercase_form for segment
                                 in token.segments]
            print(*form_with_lengths, sep="")
        return
    
    def print_dictionary(self):
        words = sorted(self.dictionary.keys())
        for word in words:
            self.print_with_lengths(word)
        return
                    


def make_default_length_dictionary():
    paths = os.listdir("perseus_corpus")
    paths = [f"perseus_corpus/{path}" for path in paths]
    ld = LengthDictionary()
    ld.count_length_frequencies(paths, length_dictionary=None)
    ld.make_length_dictionary()
    ld.save(".default_length_dictionary.pickle")

# if __name__ == "__main__":
#    make_default_length_dictionary()
