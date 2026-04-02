#!/usr/bin/env python3
# coding=utf-8
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""UniversalNer (UNER) data preprocessing.

This script preprocesses the UniversalNER corpora
(https://github.com/UniversalNER). Available on GitHub. License: CC BY-SA, as
per the publication: https://aclanthology.org/2024.naacl-long.243/.
"""

import os
import sys

import langcodes

UNER_NCOLS = 5
UNER_COLSEP = "\t"

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--add_docstarts",
        action="store_true",
        default=False,
        help="Adds -DOCSTART- on document start.",
    )
    parser.add_argument(
        "--language", required=True, default=None, type=str, help="Corpus language."
    )
    parser.add_argument(
        "--source_corpus",
        required=True,
        default=None,
        type=str,
        help="Source corpus name.",
    )
    parser.add_argument(
        "--source_path",
        required=True,
        default=None,
        type=str,
        help="Path to the source corpus.",
    )
    parser.add_argument(
        "--target_corpus",
        required=True,
        default=None,
        type=str,
        help="Target corpus name.",
    )
    parser.add_argument(
        "--target_path",
        required=True,
        default=None,
        type=str,
        help="Path to the target corpus.",
    )
    args = parser.parse_args()

    corpus_spec = args.source_corpus.split("-")[-1].lower()
    if args.source_corpus == "UNER_Norwegian-NDT":  # fix irregularity
        corpus_spec = "norne"

    if args.language == "maghrebi_arabic_french":
        langcode = "qaf"
    elif args.language == "norwegian_bokmaal":
        langcode = "nob"
    elif args.language == "norwegian_nynorsk":
        langcode = "nno"
    else:
        langcode = langcodes.find(args.language)

    for split in ["train", "dev", "test"]:
        filename = os.path.join(
            args.source_path, "{}_{}-ud-{}.iob2".format(langcode, corpus_spec, split)
        )
        output_filename = os.path.join(args.target_path, "{}.conll".format(split))

        if os.path.isfile(filename):
            print("{} -> {}".format(filename, output_filename), file=sys.stderr)
            with open(filename, "r", encoding="utf-8") as fr:
                with open(output_filename, "w", encoding="utf-8") as fw:
                    for l, line in enumerate(fr):
                        if line.startswith("#"):  # drop comments
                            if (
                                line.startswith("# newdoc") and args.add_docstarts
                            ):  # except marking new doc
                                print("-DOCSTART-\tO", file=fw)
                                print("", file=fw)
                            continue
                        line = line.rstrip()
                        if line:
                            cols = line.split(UNER_COLSEP)
                            if len(cols) != UNER_NCOLS:
                                raise ValueError(
                                    'Expected {} columns, got {} on line {}: "{}"'.format(
                                        UNER_NCOLS, len(cols), l, line
                                    )
                                )

                            # Drop OTH, as it is annotated inconsistently and
                            # not part of the official annotation
                            # (https://aclanthology.org/2024.naacl-long.243/)
                            if cols[2].endswith("OTH"):
                                cols[2] = "O"

                            # Drop "-" in norwegian
                            if cols[2] == "-":
                                cols[2] = "O"

                            print("{}\t{}".format(cols[1], cols[2]), file=fw)
                        else:
                            print("", file=fw)
        else:
            print(
                'UNER file "{}" does not exist, skipping.'.format(filename),
                file=sys.stderr,
            )
