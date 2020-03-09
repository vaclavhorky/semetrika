#!/usr/bin/env python3

import unicodedata
import sys

# characters in non-word tokens
# -----------------------------

PUNCTUATION = set(",;.?!: " +
                  "‐––—" +
                  "\"\'„“‚‘»«›‹" +
                  "()[]/")
NUMBERS = set("0123456789")
NONWORD_CHARS = PUNCTUATION | NUMBERS

NO_ELISION = set(";.?!")    # punctuation marks preventing elision

# characters in word tokens
# -------------------------

VOWELS_UNKNOWN = "aeiouyë"
    # y can be followed by breve, but it is here for zipping (see below)
VOWELS_SHORT =   "ăĕĭŏŭ"
    # y̆ is not here because there is no single character for it
VOWELS_LONG =    "āēīōūȳ"
VOWELS = set(VOWELS_UNKNOWN+VOWELS_SHORT+VOWELS_LONG)

CONSONANTS = set("bcdfgjklmnpqrstvwxz")

WORD_CHARS = VOWELS | CONSONANTS | {"h"} | set("y̆")
    # y̆ is here for the combining breve, "y" already in VOWELS

# characters which are not stripped by normalization
ALLOWED_CHARS = NONWORD_CHARS | WORD_CHARS


# strings always forming a diphthong
DIPHTHONGS = set("ae oe au".split())

# words where "eu" and "ui" form a diphthong
EU_WORDS = set("neu seu heu heus ceu".split())   # ceu not in Panhuis
UI_WORDS = set("cui cuique hui huic".split())   # neither cuique

# forms of esse where e can be elided
ESSE_ELISION_FORMS = set("est ĕst es ĕs".split())

# prefixes (for the case of prefix+i+V)
# source: Panhuis, prepositions;
# http://dcc.dickinson.edu/grammar/latin/compound-words
PREFIXES = set(("in sub super ad ante circum contra extra inter intra"
                + " ob per post praeter supra trans ab con de e prae"
                + " pro   dis re").split())

# muta cum liquida clusters
MUTES = set("bpdtgcf")   # f not in Kuťáková, but should be
LIQUIDS = set("lr")
MCL = set(mute+liquid for mute in MUTES for liquid in LIQUIDS)


# dictionaries to add macron/breve to monophthongs
# ------------------------------------------------

ADD_MACRON = {
    unknown: long for unknown, long in zip(VOWELS_UNKNOWN, VOWELS_LONG)
    }
ADD_MACRON["ë"] = "ē"
ADD_BREVE = {
    unknown: short for unknown, short in zip(VOWELS_UNKNOWN, VOWELS_SHORT)
    }
ADD_BREVE["ë"] = "ĕ"
ADD_BREVE["y"] = "y̆"

VOWELS_ACUTE = "áéíóúý"
CONVERT_ACUTE = {
    acute: macron for acute, macron in zip(VOWELS_ACUTE, VOWELS_LONG)
    }

STRIP_DIACRITICS = {
    short: unknown for unknown, short in zip(VOWELS_UNKNOWN, VOWELS_SHORT)
    }
STRIP_DIACRITICS.update({
    long: unknown for unknown, long in zip(VOWELS_UNKNOWN, VOWELS_LONG)
    })
STRIP_DIACRITICS["y̆"] = "y"

def strip_diacritics(text):
    stripped = ""
    for char in text:
        if char in VOWELS_LONG or char in VOWELS_SHORT:
            stripped += STRIP_DIACRITICS[char]
        else:
            stripped += char
    stripped = stripped.replace("y̆", "y")
    return stripped


# dictionary to convert ligatures of diphthongs
# ---------------------------------------------

LIGATURES = ("Æ", "æ", ", Œ", "œ")
LIGATURES_REPLACEMENTS = ("Ae", "ae", "Oe", "oe")
CONVERT_LIGATURE = {
    ligature: replacement for ligature, replacement
    in zip(LIGATURES, LIGATURES_REPLACEMENTS)
    }

# Æ and Œ can be in an all-caps context, where it should be replaced
# rather by AE and OE, but meh


# ---------------------------------------------

AMBIGUOUS_ELEMENTS = set("ow")
UNAMBIGUOUS_ELEMENTS = set("-u|")
ELEMENTS = AMBIGUOUS_ELEMENTS | UNAMBIGUOUS_ELEMENTS


# ==================================================

class ParsingError(Exception):
    pass

class Meter():
    """Class generating all realizations of a metre from its scheme."""

    def __init__(self, scheme):
        self.scheme = scheme
        self.sequences = None
        self.generate_metrical_sequences()

    # -  short syllable
    # u  long syllable
    # o  -/u
    # w  -/uu
    # |  feet boundary
    def generate_metrical_sequences(self):
        sequences = {}
        scheme = "".join([
            char for char in self.scheme if char in ELEMENTS
            ])
            
        def add_sequence(sequence, remainder):
            if remainder == "":
                sequence_lengths = "".join([
                    char for char in sequence if char in set("-u")
                    ])    # only syllable lengths without feet boundaries
                sequences[sequence_lengths] = sequence
            else:
                element = remainder[0]
                remainder = remainder[1:]
                if element == "o":
                    add_sequence(sequence+"-", remainder)
                    add_sequence(sequence+"u", remainder)
                elif element == "w":
                    add_sequence(sequence+"-", remainder)
                    add_sequence(sequence+"uu", remainder)
                else:    # unambiguous element
                    add_sequence(sequence+element, remainder)

        add_sequence("", scheme)
        self.sequences = sequences
        return

HEXAMETER = Meter("-w | -w | -w | -w | -uu | -o")

def restore_cases(lowercase_form, original_cases):
    restored = ""
    for char, case in zip(lowercase_form, original_cases):
        if case == "U":
            restored += char.upper()
        else:
            restored += char
    return restored


class Segment():
    """Class for phonological units (defined with respect to scansion)."""

    def __init__(self, lowercase_form="", original_case="", type_=None,
                 / , subtype=None, length=None):
        self.lowercase_form = lowercase_form
        self.original_case = original_case
        self.type_ = type_
        self.subtype = subtype
        self.length = length
            # only for oral monophthongs (as nasal monophthongs and
            # diphthongs are always long)
        self.coda = None    # only for vowels
        self.elided = None


class Token():
    """Class for words or punctuation (including space) or digits
    (for verse numbers)"""

    def __init__(self, original_form="", type_=None,
                 length_dictionary=None):
        self.original_form = original_form
        self.original_cases = None
        self.lowercase_form = None
        self.type_ = type_
        self.length_dictionary = length_dictionary
        self.segments = None
        self.normalize_cases()

    # to make various comparisons easier, remember the original case for
    # each character, and turn them lower-case
    def normalize_cases(self):
        original_cases = ""
        for char in self.original_form:
            if char.isupper():
                original_cases += "U"
            else:
                original_cases += "L"
        self.original_cases = original_cases
        self.lowercase_form = self.original_form.lower()
        return

    # split the token into segments, roughly phonemes
    def segmentize(self):
        segments = []
        # parse non-word segments (punctuation, numbers) as one segment
        if self.type_ != "word":   
            segments.append(Segment(self.lowercase_form,
                                    self.original_cases, "other"))
        # for word segments:
        else:
            # to avoid checking whether we are at the beginning or
            # the end of the word, add sentinel spaces
            form = f" {self.lowercase_form} "
            cases = f" {self.original_cases} "
            i = 1   # id of the current character in the token
            while form[i] != " ":
                prev, char, next_ = form[i-1:i+2]
                char_case, next_case = cases[i:i+2]
                new_i = i+1

                # diphthongs
                if (
                    (char+next_ in DIPHTHONGS) or
                    (char+next_ == "eu" and form[1:-1] in EU_WORDS) or
                    (char+next_ == "ui" and form[1:-1] in UI_WORDS)
                ):
                    new = [Segment(char+next_, char_case+next_case,
                                   "vowel", subtype = "diphthong")]
                    new_i += 1

                # final nasal vowels
                elif char in VOWELS and form[i+1:] == "m ":
                    new = [Segment(char+next_, char_case+next_case,
                                   "vowel", subtype = "nasal")]
                    new_i += 1

                # i as a consonant
                # before a vowel initially or after a prefix 
                elif (
                    char == "i" and next_ in VOWELS and
                    (i == 1 or form[1:i] in PREFIXES)
                ):   
                    new = [Segment("i", char_case, "consonant")]
                # i as two consonants between two vowels
                elif (
                    (char == "i" or char == "j") and
                    prev in VOWELS and next_ in VOWELS and
                    form[i-2:i] != "qu" and form[i-3:i] != "ngu"
                    # qu, (n)gu is a consonant, not a vowel
                ):   
                    new = [Segment("", "", "consonant"),
                           Segment(char, char_case, "consonant")]
                # otherwise i is a monophthong and is treated later

                # qu is a single consonant
                elif char+next_ == "qu":
                    new = [Segment("qu", char_case+next_case,
                                   "consonant")]
                    new_i += 1
                # gu after n and before a vowel is a single consonant
                elif prev+char+next_ == "ngu" and form[i+2] in VOWELS:
                    new = [Segment("gu", char_case+next_case,
                                   "consonant")]
                    new_i += 1

                # x (= cs), z (= zz) are two consonants
                elif char == "x" or char == "z":
                    new = [Segment("", "", "consonant"),
                           Segment(char, char_case, "consonant")]

                # h never causes length by position and does not
                # prevent elision, so it gets a special type
                elif char == "h":
                    new = [Segment("h", char_case, "h")]
                
                # y with breve: there is no single character for it in
                # Unicode, so it was not normalized, and has to be
                # treated specially
                elif char+next_ == "y̆":
                    new = [Segment("y̆", char_case+next_case,
                                   "vowel", subtype="monophthong",
                                   length="short")]
                    new_i += 1

                # other vowels
                elif char in VOWELS:
                    if char in VOWELS_LONG:
                        length = "long"
                    elif char in VOWELS_SHORT:
                        length = "short"
                    else:
                        length = "unknown"
                    new = [Segment(char, char_case, "vowel",
                                   subtype="monophthong",
                                   length=length)]

                # other consonants
                elif char in CONSONANTS:
                    new = [Segment(char, char_case, "consonant")]

                else:
                    raise ValueError("Cannot analyse this character:"
                                     + f" {char!r}")

                segments.extend(new)
                i = new_i

        self.segments = segments
        return

    # for fully macronized input, treat unmarked vowels as short
    def brevize(self):
        for segment in self.segments:
            if (
                segment.subtype == "monophthong" and
                segment.length == "unknown"
                ):
                segment.length = "short"
                segment.lowercase_form = ADD_BREVE[
                    segment.lowercase_form]
        return

    # adds unambiguous lengths which were learned from unambiguously
    # scanned verses in a large corpus
    def add_lengths(self):
        if self.length_dictionary is None:
            raise ParsingError("no length dictionary specified")
        word = strip_diacritics(self.lowercase_form)
        if word in self.length_dictionary:
            monophthong_i = 0
            for segment in self.segments:
                if segment.subtype == "monophthong":
                    if (
                        segment.length == "unknown" and
                        self.length_dictionary[word][monophthong_i] != "unknown"
                        ):
                        segment.length = self.length_dictionary[word][monophthong_i]
                        if segment.length == "long":
                            segment.lowercase_form = ADD_MACRON[segment.lowercase_form]
                        elif segment.length == "short":
                            if segment.lowercase_form == "y":
                                segment.original_case += "L"
                            segment.lowercase_form = ADD_BREVE[segment.lowercase_form]
                    monophthong_i += 1
        return

    def print_segments(self):
        """Prints segments of a token divided by |. Vowels are in upper case."""
        if self.segments == None:
            raise ParsingError(f"The token {self.original_form!r} is not"
                               + " segmented yet.")
        
        if self.segments[0].lowercase_form == " ":
            print("_")
        else:
            segment_forms = []
            for segment in self.segments:
                if segment.type_ == "vowel":
                    segment_forms.append(segment.lowercase_form.upper())
                else:
                    segment_forms.append(segment.lowercase_form)
            print(*segment_forms, sep="|")
        return


class Verse():
    """Class for scanning verse.
    .full_metrical_sequences: sequences of syllable lengths with feet
         boundaries fitting the hexameter scheme
    .metrical_sequences: the same without feet boundaries
    .scansions: for each metrical sequence, text of the verse and
         sequence with elements aligned with vowels
    .print_scansions: prints all scansions, if the verse cannot be scanned,
         prints the aligned scheme
    """

    def __init__(self, original_form, / ,
                 length_dictionary=None, unmarked_short=False,
                 idle=False):
        self.original_form = original_form
        self.length_dictionary = length_dictionary
        self.normalized_form = None
        self.tokens = None
        self.scheme = None
        self.candidate_sequences = None
        self.metrical_sequences = None   # only syllable lengths
        self.full_metrical_sequences = None   # + feet boundaries
        self.scansions = None
        self.scansion_count = None
        if not idle:   # for debugging and showing how it works
            self.normalize()
            self.tokenize()
            for token in self.tokens:
                token.segmentize()
                if unmarked_short:
                    token.brevize()
                # only add lengths if the input is not fully macronized
                elif self.length_dictionary:
                    token.add_lengths()
            self.elide()
            self.analyse_codas()
            self.make_scheme()
            self.generate_candidate_sequences()
            self.find_metrical_sequences()
            self.scan()

    # merge combining diacritics with the preceding character (except
    # for y+breve), convert diphtong ligatures, and strip everything but
    # Latin language letters, punctuation and numbers
    def normalize(self):
        normalized = self.original_form.strip()
        
        # merge combining diacritics (but y+breve remains as there is no
        # single Unicode character for it! y+macron is okay)
        normalized = unicodedata.normalize("NFC", normalized)

        # convert vowels with acute (Czech way of marking length)
        # to vowels with macron (Latin way)
        for acute, macron in CONVERT_ACUTE.items():
            normalized = normalized.replace(acute, macron)
            normalized = normalized.replace(acute.upper(),
                                            macron.upper())
        
        # convert ligatures for ae, oe
        for ligature, replacement in CONVERT_LIGATURE.items():
            normalized = normalized.replace(ligature, replacement)
        
        # remove all but allowed characters
        normalized = [
            char for char in normalized if char.lower() in ALLOWED_CHARS
            ]
        normalized = "".join(normalized)
        
        self.normalized_form = normalized
        return

    # split the verse into tokens, i. e. words and non-word characters,
    # that is: words are separated by non-word characters, typically
    # space or other punctuation marks
    # this can lead to bugs if a part of a word is parenthesized as it
    # is then parsed as multiple words (which can then lead to an
    # unwanted elision etc.)
    def tokenize(self):
        # add sentinel space so the last word is added (word tokens are
        # added when a non-word character is encountered)
        verse = f"{self.normalized_form} "
        tokens = []
        word = ""
        for char in verse:
            if char.lower() not in WORD_CHARS:
                # unless the previous character was not a part of
                # a word, add the previous word as a word token
                if word != "":
                    tokens.append(Token(word, "word", self.length_dictionary))
                    word = ""   # and initialize a new word
                # and add this character as a non-word token
                tokens.append(Token(char, "other", self.length_dictionary))    
            else:   # the current word token continues
                word += char
        self.tokens = tokens[:-1]   # without the sentinel
        return

    # elide -- for elided segments, set elided as True, and enclose
    # the elided chunk in parentheses
    def elide(self):
        # indices of word tokens
        word_ids = [token_id for token_id,token
                    in enumerate(self.tokens) if token.type_ == "word"]

        # go through each pair of adjacent words
        for i, word_id in enumerate(word_ids[:-1]):
            word = self.tokens[word_id]
            segments = word.segments
            next_word_id = word_ids[i+1]
            next_word = self.tokens[next_word_id]
            next_segments = next_word.segments
            
            # interjection "o" cannot be elided
            if (word.lowercase_form == "o" or
                word.lowercase_form == "ō"):
                continue

            # does the first word end with a vowel?
            vowel_ending = segments[-1].type_ == "vowel"
            # does the next word start with a vowel?
            vowel_start = next_segments[0].type_ == "vowel"
            # or with "h" (after which a vowel necessarily follows)?
            h_start = next_segments[0].type_ == "h"
            # is there an elision?
            elision = vowel_ending and (vowel_start or h_start)
            
            if elision:           
                # is the next word "es(t)"? then the "e" is elided
                if next_word.lowercase_form in ESSE_ELISION_FORMS:
                    next_segments[0].lowercase_form = (
                        f"({next_segments[0].lowercase_form})")
                    next_segments[0].elided = True
                    next_segments[0].original_case = (
                        f"L{next_segments[0].original_case}L")
                
                # otherwise the final vowel (+ initial h) is
                else:
                    # final segment of the first word is always elided,
                    # and elision always starts there
                    segments[-1].lowercase_form = (
                        f"({segments[-1].lowercase_form}")
                    segments[-1].original_case = (
                        f"L{segments[-1].original_case}")
                    segments[-1].elided = True
                    
                    # where the elision ends?
                    if h_start:
                        next_segments[0].lowercase_form += ")"
                        next_segments[0].original_case += "L"
                        next_segments[0].elided = True
                    else:
                        segments[-1].lowercase_form += ")"
                        segments[-1].original_case += "L"
        
        return

    # syllable = onset (consonants) + nucleus (vowel) + coda
    # (consonants)
    # possibilities:
    #  * one or no consonant after a vowel -> open syllable
    #  * final vowel in a word, even if the next word begins with two
    #    or more consonants -> almost always open syllable
    #  * vowel + muta cum liquida in the same word -> open or closed
    #  * otherwise -> closed
    def analyse_codas(self):
        # vowel in a syllable whose coda is now analysed
        # initialized as a sentinel to catch the irrelevant consonant
        # chunk before the first vowel
        this_vowel = Segment()
        consonant_count = 0   # number of consonants after this vowel
        chunk = ""   # the consonants themselves
        
        for token in self.tokens:
            for segment in token.segments:
                if segment.type_ == "consonant":
                    consonant_count += 1
                    chunk += segment.lowercase_form
                # to prevent initial consonant clusters from causing
                # length by position, add space
                elif segment.lowercase_form == " ":
                    chunk += " "
                elif segment.type_ == "vowel" and not segment.elided:
                    # one or no consonant, or all the consonants belong to
                    # the next word
                    if consonant_count <= 1 or chunk.startswith(" "):
                        this_vowel.coda = "open"
                    # muta cum liquida in the middle of the word is
                    # ambivalent
                    elif chunk in MCL:
                        this_vowel.coda = "unknown"
                    else:
                        this_vowel.coda = "closed"

                    # now analyse the next syllable
                    this_vowel = segment
                    consonant_count = 0
                    chunk = ""
        
        # analyse the last syllable specially
        if consonant_count == 0:
            this_vowel.coda = "open"
        else:
            this_vowel.coda = "closed"
        
        return

    def print_tokens(self):
        """Prints tokens with original cases, separated by |."""
        if self.tokens == None:
            raise ParsingError(f"The verse {self.original_form!r} is"
                               + " not tokenized yet.")
        token_forms = [token.original_form for token in self.tokens]
        print(*token_forms, sep="|")
        return

    # print segments of each token separated by vertical bars on a new
    # line; replace spaces with underscores
    def print_segments(self):
        """Prints segments of each token separated by |, each token
        has its line. Replaces spaces with _."""
        if self.tokens == None:
            raise ParsingError(f"The verse {self.original_form!r} is"
                               + " not tokenized yet.")
        for token in self.tokens:
            token.print_segments()
        return

    def print_verse(self):
        """Prints verse with added lengths and elisions."""
        verse = ""
        for token in self.tokens:
            for segment in token.segments:
                verse += restore_cases(segment.lowercase_form,
                                       segment.original_case)
        print(verse)

    # -: long syllable
    # u: short
    # o: syllable of unknown length
    def make_scheme(self):
        scheme = ""
        for token in self.tokens:
            for segment in token.segments:
                if segment.type_ == "vowel" and not segment.elided:
                    # diphthong or final nasal vowel or long monophthong
                    # or closed syllable -> long syllable
                    if (
                        segment.subtype == "diphthong" or
                        segment.subtype == "nasal" or
                        segment.length == "long" or
                        segment.coda == "closed"
                        ):
                        scheme += "-"
                    # short vowel in an open syllable -> short syllable
                    elif (
                        segment.length == "short" and
                        segment.coda == "open"
                        ):
                        scheme += "u"
                    # otherwise long or short, i. e. unknown length in
                    # an open syllable or vowel + muta cum liquida
                    else:
                        scheme += "o"
        self.scheme = scheme
        return

    # generate all ways to replace "o" with "-" and "u"
    def generate_candidate_sequences(self):
        candidate_sequences = set()
        def add_sequence(sequence, remainder):
            if remainder == "":
                candidate_sequences.add(sequence)
            else:
                if remainder[0] == "o":
                    add_sequence(sequence+"-", remainder[1:])
                    add_sequence(sequence+"u", remainder[1:])
                else:
                    add_sequence(sequence+remainder[0], remainder[1:])
        add_sequence("", self.scheme)
        self.candidate_sequences = candidate_sequences
        return

    # find which of these can be hexameter line
    def find_metrical_sequences(self):
        metrical_sequences = sorted(
            self.candidate_sequences.intersection(HEXAMETER.sequences))
        full_metrical_sequences = [
            full_sequence for sequence, full_sequence
            in HEXAMETER.sequences.items()
            if sequence in metrical_sequences
            ]

        # if two sequences differ only in the last element, which is
        # free in hexameter, merge them together
        def merge_sequences(sequences):
            merged_sequences = []
            i = 0
            # compare the current sequence with the next
            while i < len(sequences)-1:
                this, next_ = sequences[i], sequences[i+1]
                if len(this) == len(next_) and this[:-1] == next_[:-1]:
                    merged_sequences.append(this[:-1]+"o")
                    i += 2
                else:
                    merged_sequences.append(this)
                    i += 1
            # if the antepenultimate sequence wasn't the same as
            # the last one, add it (this covers also the case when there
            # is only one sequence)
            if i == len(sequences)-1:
                merged_sequences.append(sequences[-1])
            return merged_sequences
        
        self.metrical_sequences = merge_sequences(metrical_sequences)
        self.full_metrical_sequences = merge_sequences(
            full_metrical_sequences)
        return

    def scan(self):
        scansions = []

        def scan_in_one_way(sequence):
            text = ""
            aligned_sequence = ""
            i = 0   # where I am in the sequence

            # chunk of characters between the current and next vowel
            chunk = ""
            # is there elision? (necessary for correct placement of
            # the feet boundary)
            chunk_elision = False
            prev_vowel = Segment()   # sentinel
            
            for token in self.tokens:
                for segment in token.segments:
                    if segment.type_ == "vowel" and not segment.elided:
                        
                        # add the previous chunk
                        chunk_sequence = " "*len(chunk)

                        # am I at the feet boundary?
                        if sequence[i] == "|":
                            space_id = chunk.find(" ")
                                 # is there a space in the chunk and where?
                            if space_id != -1 and not chunk_elision:
                                chunk = f"{chunk[:space_id]} | {chunk[space_id+1:]}"
                                chunk_sequence = f"{chunk_sequence[:space_id]} | {chunk_sequence[space_id+1:]}"
                            else:
                                if (
                                    prev_vowel.coda == "open" or
                                    (prev_vowel.coda == "unknown" and
                                     (sequence[i-1] == "u" or prev_vowel.length == "long"
                                      or prev_vowel.subtype == "diphthong")) or
                                    (chunk.lower() == "x" or chunk.lower() == "z" or chunk.lower() == "i") or
                                    chunk.lower().startswith(("x(", "z(", "i("))
                                    # "anceps pugna diu, stant obnixa omnia contra:" -> "obni|x(a) omnia"
                                ):
                                    chunk = f"|{chunk}"
                                    chunk_sequence = f"|{chunk_sequence}"
                                elif prev_vowel.coda == "unknown":
                                    chunk = f"{chunk[0]}\\{chunk[1:]}"
                                    chunk_sequence = f"{chunk_sequence[0]}\\{chunk_sequence[1:]}"
                                else:
                                    chunk = f"{chunk[0]}|{chunk[1:]}"
                                    chunk_sequence = f"{chunk_sequence[0]}|{chunk_sequence[1:]}"
                                    
                            i += 1
                        
                        text += chunk
                        aligned_sequence += chunk_sequence
                        chunk = ""
                        chunk_elision = False
                        
                        # add this vowel
                        new = segment.lowercase_form
                        if (
                            segment.subtype == "monophthong" and
                            segment.length == "unknown" and
                            (segment.coda == "open" or
                             (segment.coda == "unknown" and sequence[i] == "u")
                            )
                        ):
                            if sequence[i] == "-":
                                new = ADD_MACRON[new]
                            elif sequence[i] == "u":
                                new = ADD_BREVE[new]
                        
                        text += restore_cases(new, segment.original_case)
                        
                        aligned_sequence += sequence[i]
                        # add space in the aligned_sequence if diphthong or nasal
                        if len(new) == 2 and new != "y̆":
                            aligned_sequence += " "
                        
                        i += 1
                        prev_vowel = segment
                        
                    else:
                        chunk += restore_cases(segment.lowercase_form, segment.original_case)
                        if segment.elided:
                            chunk_elision = True
            
            # add the chunk after the last vowel
            text += chunk
            aligned_sequence += " "*len(chunk)
                        
            scansions.append((text, aligned_sequence))
            return

        scan_in_one_way(self.scheme)
        for sequence in self.full_metrical_sequences:
            scan_in_one_way(sequence)

        self.scansions = scansions
        self.scansion_count = len(scansions)-1   # minus the scansion with the scheme
        return

    def print_scansions(self):
        """Prints all scansions: text and sequence of syllable lengths
        aligned with vowels. If the verse cannot be scanned, it prints
        the scheme instead."""
        # skip empty lines or too short lines (probably with verse numebrs)
        if len(self.original_form) < 10:
            print(self.original_form)
            return
        
        # if the verse cannot be scanned, print at least the scheme
        if self.scansion_count == 0:
            print("WARNING: cannot scan this", file=sys.stderr)
            print(self.scansions[0][0])
            print(self.scansions[0][1])
        elif self.scansion_count == 1:   # one scansion
            print(self.scansions[1][0])
            print(self.scansions[1][1])
        else:    # more than one scansion
            print("WARNING: cannot scan this unambiguosly", file=sys.stderr)
            for i, (text, sequence) in enumerate(self.scansions[1:],
                                                 start=1):
                print(f"{i}. {text}")
                print(f"   {sequence}")
                if i != self.scansion_count:
                    print()
        return


