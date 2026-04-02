#!/bin/bash
#
# Copyright 2018 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# This script evaluates the NameTag 3 nested NER during the training phase,
# using the evaluation script compare_nested_entities.py.

# Usage: ./run_conlleval.sh [dev|test] gold_conll_file system_conll_file

set -e

name="$1"
gold="$2"
system="$3"

# Debug print
#echo "Running external nested evaluation on \"$name\" dataset with gold file \"$gold\" and system file \"$system\""

# Print system entities
touch ${name}_system_entities.txt
cat ${system} | $(dirname $0)/conll2eval_nested.py > ${name}_system_entities.txt

# Print gold entities
touch ${name}_gold_entities.txt
cat $(dirname $0)/${gold} | $(dirname $0)/conll2eval_nested.py > ${name}_gold_entities.txt

$(dirname $0)/compare_nested_entities.py ${name}_gold_entities.txt ${name}_system_entities.txt > ${name}.eval
