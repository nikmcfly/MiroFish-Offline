#!/bin/bash
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# This script evaluates the NameTag 3 output externally on dev data, for flat
# NE corpora (e.g., CoNLL-2003 and CoNLL-2002), using the official evaluation
# script conlleval.

# Usage: ./run_conlleval.sh [dev|test] gold_conll_file system_conll_file

set -e

name="$1"
gold="$2"
system="$3"

# Debug print
#echo "Running external CoNLL evaluation on \"$name\" dataset with gold file \"$gold\" and system file \"$system\""

# Create conlleval script input
paste $(dirname $0)/${gold} ${system} | cut -f1,2,4 > ${name}_conlleval_input.conll

# Run conlleval
$(dirname $0)/conlleval -d "\t" < ${name}_conlleval_input.conll > $name.eval
