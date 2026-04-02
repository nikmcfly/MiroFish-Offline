#!/bin/sh
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# A simple script for accessing NameTag 3 REST API using curl.
#
# This is a simple script for accessing NameTag 3 webservice from the command
# line using curl. The script will call a server. Do not send personal or
# private data unless you are authorized and comfortable with it being
# processed by NameTag 3.
#
# Usage:
#
# Get this script either by cloning the entire NameTag 3 repository:
#
# git clone https://github.com/ufal/nametag3
#
# or by simply downloading just this script specifically from the NameTag
# 3 repository by opening
#
# https://github.com/ufal/nametag3/blob/main/nametag3_with_curl.sh
#
# and hitting the download button ("Download raw file").
#
# Save your text in a plaintext file, see an example in examples/cs_input.txt.
# At the command line, type the following command:
#
# ./nametag3_with_curl.sh examples/cs_input.txt
#
# The output will be printed to the standard output. To redirect the output
# into a file, you can type:
#
# ./nametag3_with_curl.sh examples/cs_input.txt > output_file.xml
#
# Additionally, you can specify the language of your data. The options are
# arabic, chinese, croatian, czech, danish, dutch, english, german, maghrebi,
# norwegian_bokmaal, norwegian_nynorsk, portuguese, serbian, slovak, spanish,
# swedish, and ukrainian.
#
# ./nametag3_with_curl.sh examples/en_input.txt english > output_file.xml

# Exit immediately if any command exits with a non-zero status (i.e., stops the script on errors).
set -e

# Check the commandline arguments.
if [ "$#" -ne 1 -a "$#" -ne 2 ]; then
    echo "USAGE: ./nametag3_with_curl.sh input_file arabic|chinese|croatian|czech|danish|dutch|english|german|maghrebi|norwegian_bokmaal|norwegian_nynorsk|portuguese|serbian|slovak|spanish|swedish|ukrainian"
    exit 1
fi

# Extract the commandline arguments.
input_file="$1"

# Default language is czech
model="czech"
if [ "$#" -eq 2 ]; then
  model="$2"
fi

# Call the NameTag 3 server with curl and extract the result from the response with Python.
curl -F data=@$input_file -F model=$model http://lindat.mff.cuni.cz/services/nametag/api/recognize | PYTHONIOENCODING=utf-8 python3 -c "import sys,json; sys.stdout.write(json.load(sys.stdin)['result'])"
