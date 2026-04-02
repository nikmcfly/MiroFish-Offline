#!/usr/bin/env python3
# coding=utf-8
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Script to harmonize CNEC 2.0 with CoNLL-2003 PER, ORG, LOC, MISC labels.

In particular, the following happens with the CNEC 2.0 corpus:

1. The 46 CNEC 2.0 fine-grained labels and the 4 CNEC 2.0 containers are mapped
to the 4 CoNLL-2003 PER, ORG, LOC, MISC labels. The mapping was decided by
manually inspecting and comparing the CoNLL-2003 English train data examples
with the CoNLL 2.0 train data examples.

2. Since the CNEC 2.0 allows embedded (nested) entities, the outermost one is
kept to flatten the NE hierarchy, while the inner NEs are dropped.

Input format:

The input data file format is a vertical file, one token and optionally, its label per line,
separated by a tabulator; sentences delimited by newlines (such as a first and
fourth column in a well-known CoNLL-2003 IOB shared task corpus):

John	B-PER
loves	O
Mary	B-PER
.	O

Mary	B-PER
loves	O
John	B-PER
.	O

For nested entities, multiple labels are concatenated in the second column,
outermost to innermost, separated by ``|''.

More examples can be found in the examples directory.

The expected labels are labels from the CNEC 2.0, see the MAP and UNMAPPED hash
tables or the CNEC 2.0 NE labels in https://ufal.mff.cuni.cz/cnec/cnec2.0.
"""

import io
import json
import os
import pickle
import sys

MAP = {
    "P": "PER",  # e.g., Jimi Hendrix (en), Stanislav Procházka (cs)
    "pc": "MISC",  # e.g., American (en), Němec (cs)
    "pf": "PER",  # e.g., Jim (en), Stanislav (cs)
    "pp": "PER",  # e.g., God (en), svatý Václav (cs)
    "pm": "PER",  # e.g., Franklin D. Roosevelt (en), J. Alfred Prufrock (cs)
    "ps": "PER",  # e.g., Hendrix (en), Kafka (cs)
    "p_": "PER",  # PER by majority vote of the other "p" labels
    "gh": "LOC",  # e.g., Taiwan Strait (en), Atlantik (cs)
    "gq": "LOC",  # e.g., Manhattan (en), Letňany (cs)
    "gs": "LOC",  # e.g., Wall Streen (en), Mostecká ulice (cs)
    "gu": "LOC",  # e.g., Brussels (en), Praha (cs)
    "gl": "LOC",  # e.g., Northfield Mountains (en), Ural (cs)
    "gr": "LOC",  # e.g., Golan Heights (en), Ostravsko (cs)
    "gt": "LOC",  # e.g., Asia (en), Evropa (cs)
    "gc": "LOC",  # e.g., Finland (en), Čína (cs)
    "g_": "LOC",  # LOC by majority vote of the other "g" labels
    "ia": "MISC",  # e.g., Grand Slam (en), Stanley Cup (cs)
    "if": "ORG",  # e.g., Gazprom (en), Plzeňská banka (cs)
    "ic": "ORG",  # e.g., Oklahoma State University (en), Královská akademie (cs)
    "io": "ORG",  # e.g., NATO (en), KDU-ČSL (cs)
    "i_": "ORG",  # ORG by majority vote of the other "i" labels
    "oa": "MISC",  # e.g., Mission: Impossible (en), Nebezpečná rychlost (cs)
    "or": "MISC",  # e.g., Regulation No. 2913/92 (en), Zákon o státní službě (cs)
    "op": "MISC",  # e.g., Boeing (en), Opel (cs)
    "o_": "MISC",  # e.g., BSD (en), HIV (cs)
    "ms": "ORG",  # e.g., Israel Radio (en), Radio New Zealand (en), Radio Morava (cs)
    "mn": "ORG",
}  # e.g., The New York Times (en), The Times (en), Star Magazine (en), Wall Street Journal (en), Journal of Forensic Studies (cs)
UNMAPPED = [
    "T",  # e.g., 1996-08-22 (en), 18. května (cs)
    "A",  # not present in English data, Ministerstvo kultury, Maltézské náměstí, Praha 118 11 (cs)
    "C",  # not present in English data, vs. some extremely long names of artistic products (cs)
    "pd",  # e.g., Mr (en), Mgr. (cs)
    "om",  # e.g., dollar (en), Kč (cs)
    "oe",  # e.g., mm (en), kg (cs)
    "tf",  # e.g., Christmas (en), Silvestr (cs)
    "ty",  # e.g., 1983 (en), 1945 (cs)
    "tm",  # e.g., April (en), květen (cs)
    "th",  # e.g., 11.16 a.m. (en), 9.00 (cs)
    "td",  # not present in English data, 26. (cs)
    "mi",  # not present in English data, https:... (cs)
    "me",  # derivatives@reuters.com (en), wise.desk@csob.cz (cs)
    "ah",  # not present in English data, Na Perštýně 6 (cs)
    "az",  # not present in English data, 118 11 (cs)
    "at",  # not present in English data, 287 085 111 (cs)
    "nb",  # not present in English data, 13 (cs)
    "ni",  # e.g., 5. (en), 70. (cs)
    "ns",  # e.g., 6-3 (en), 1:1 (cs)
    "nc",  # e.g., 12 (en), 127 (cs)
    "no",  # e.g., 11th (en), 17. (cs)
    "na",  # e.g., 43-year-old (en), Řehák, 65. (cs)
    "n_",
]  # not present in English data, 7 (cs)

if __name__ == "__main__":

    for line in sys.stdin:
        line = line.strip()

        if not line:
            print("")
            continue

        cols = line.split("\t")

        if cols[1] != "O":
            # Take the outermost entity
            label = cols[1].split("|")[0]

            form, ne_type = label.split("-")

            if ne_type in UNMAPPED:
                cols[1] = "O"
            elif ne_type not in MAP:
                print('Unknown NE type "{}"'.format(ne_type), file=sys.stderr)
                sys.exit(1)
            else:
                cols[1] = "-".join([form, MAP[ne_type]])

        print("\t".join(cols))
