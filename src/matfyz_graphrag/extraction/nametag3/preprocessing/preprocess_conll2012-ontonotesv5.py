#!/usr/bin/env python3
# coding=utf-8
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""CoNLL2012 OntoNotes v5 data preprocessing for NameTag 3.

This script preprocesses the CoNLL2012 OntoNotes v5 data.

The CoNLL-2012 train/dev/test split is available from HuggingFace
(https://huggingface.co/datasets/ontonotes/conll2012_ontonotesv5). License: CC
BY-NC-ND 4.0, as per the dataset card on HF.

The original OntoNotes v5 dataset is available from LDC.
"""

import os
import sys

from datasets import load_dataset

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
        "--language", required=True, choices=["english_v12", "chinese_v4", "arabic_v4"]
    )
    parser.add_argument(
        "--ldc",
        required=True,
        type=str,
        help="Path to the original LDC OntoNotes v5 annotations.",
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

    for split in ["train", "dev", "test"]:
        output_filename = os.path.join(args.target_path, "{}.conll".format(split))
        print(
            'Processing the "{}" split of the "{}" language into target file "{}"'.format(
                split, args.language, output_filename
            ),
            file=sys.stderr,
            flush=True,
        )

        split = "validation" if split == "dev" else split
        dataset = load_dataset(
            "ontonotes/conll2012_ontonotesv5",
            args.language,
            trust_remote_code=True,
            split=split,
        )
        id2label = dataset.info.features["sentences"][0]["named_entities"].feature.names

        with open(output_filename, "w", encoding="utf-8") as fw:
            for document in dataset:
                # Only take the NE-annotated documents from the original LDC
                # distribution, which are recognized by having a corresponding
                # *.name file, and skip the documents without a manual NE
                # annotation. Such documents have been artifically augmented
                # with "O" everywhere in the CoNLL-2012 shared task data. This
                # saves the training from seeing a lot of false negatives
                # introduced in the CoNLL-2012 shared task, but does not change
                # the evaluation (no NEs were lost, obviously).

                ne_annotations_filename = os.path.join(
                    args.ldc, "{}.name".format(document["document_id"])
                )
                if not os.path.isfile(ne_annotations_filename):
                    print(
                        'No NE annotations found for document "{}" in file "{}"'.format(
                            document["document_id"], ne_annotations_filename
                        ),
                        file=sys.stderr,
                    )
                    continue

                if args.add_docstarts:
                    print("-DOCSTART-\tO", file=fw)
                    print("", file=fw)

                for sentence in document["sentences"]:
                    for word, ne in zip(sentence["words"], sentence["named_entities"]):
                        if args.language == "arabic_v4":
                            word = word.split("#")[
                                0
                            ]  # remove the morphological information
                        print("{}\t{}".format(word, id2label[ne]), file=fw)
                    print("", file=fw)
