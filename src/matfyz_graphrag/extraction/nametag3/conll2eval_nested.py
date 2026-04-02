#!/usr/bin/env python3
# coding=utf-8
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Prints the (nested) named entities for evaluation.

Input:
------

A CoNLL file with linearized (encoded) nested named entity labels delimited
with '|' (the output of NameTag 3 or the gold CoNLL file).

Output:
-------

One entity per line, three columns per line separated by tab:
    - first column are entity token ids separated by comma,
    - second column is the BIO or BILOU label,
    - the third column are the tokens separated by comma.

The output can be then evaluated with 'compare_nested_entities.py' against the
entities printed from the gold data.
"""

import sys

SEP = "\t"


def flush(ids, forms, tags):
    for i in range(len(ids)):
        print(ids[i] + SEP + tags[i] + SEP + forms[i])
    return [], [], []


if __name__ == "__main__":

    i = 0
    ids, forms, tags = [], [], []
    for line in sys.stdin:
        line = line.rstrip("\r\n")

        if not line:  # sentence ended, flush entities
            ids, forms, tags = flush(ids, forms, tags)

        else:
            cols = line.split(SEP)

            if len(cols) != 2:
                raise ValueError(
                    "conll2eval_nested.py: Incorrect number of fields in line {}".format(
                        i
                    )
                )

            form, ne = line.split(SEP)

            if ne == "O":  # all entities ended, also flush entities
                ids, forms, tags = flush(ids, forms, tags)

            else:

                for j, label in enumerate(ne.split("|")):

                    if j < len(ids):  # running entity

                        # previous running entity ends here, print and insert new entity instead
                        if (
                            label.startswith("B-")
                            or label.startswith("U-")
                            or tags[j] != label[2:]
                        ):
                            print(ids[j] + SEP + tags[j] + SEP + forms[j])
                            ids[j] = str(i)
                            forms[j] = form

                        # entity continues, append ids and forms
                        else:
                            ids[j] += "," + str(i)
                            forms[j] += " " + form
                        tags[j] = label[2:]

                    else:  # no running entities, new entity starts here, just append
                        ids.append(str(i))
                        forms.append(form)
                        tags.append(label[2:])
        i += 1
