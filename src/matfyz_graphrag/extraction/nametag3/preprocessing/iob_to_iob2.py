#!/usr/bin/env python3
# coding=utf-8
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""IOB to IOB2 converter.

This script converts named entity tags in the IOB (Inside-Outside-Beginning)
format to the stricter IOB2 format.

In IOB tagging, entities are labeled with:

B-X for the beginning of an entity of type X,
I-X for subsequent tokens of the same entity,
O for tokens outside any named entity.

However, IOB allows the first token of an entity to be tagged as I-X if it
directly follows another entity of the same type. IOB2 strictly requires all
entity starts to be labeled with B-X, making the format more consistent and
suitable for many sequence labeling models.

This script outputs valid IOB2-compliant tags.

Usage:

./iob_to_iob2.py < input.txt > output.txt

The input data file format is a vertical file, one token and its label(s) per
line: columns separated by a tabulator; sentences delimited by newlines (such
as the first and the fourth column in the well-known CoNLL-2003 shared task).
A line containing '-DOCSTART-' with the label 'O', as seen in the CoNLL-2003
shared task data, can be used to mark document boundaries. Input examples can
be found in 'nametag3.py' and in 'examples'.

John	I-PER
loves	O
Mary	I-PER
.	O

Mary	I-PER
loves	O
John	I-PER
.	O

Output:

John	B-PER
loves	O
Mary	B-PER
.	O

Mary	B-PER
loves	O
John	B-PER
.	O

"""

import sys

if __name__ == "__main__":

    prev_tag = "O"
    for line in sys.stdin:
        line = line.strip()

        if line:
            form, tag = line.split("\t")

            # If previous tag was 'O' or a different entity type, change to 'B-'
            if tag.startswith("I-"):
                if prev_tag == "O" or prev_tag[2:] != tag[2:]:
                    tag = "B-" + tag[2:]

            prev_tag = tag

            line = "\t".join([form, tag])

        print(line)
