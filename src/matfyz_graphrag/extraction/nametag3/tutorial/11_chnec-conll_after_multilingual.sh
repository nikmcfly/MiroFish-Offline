#!/bin/bash
#SBATCH -J ner
#SBATCH -p gpu-queue
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1

# Copyright 2025 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# NameTag3 training script for the Training tutorial.
#
# The tutorial can be found here:
#
# https://ufal.mff.cuni.cz/nametag/3/tutorial
#
# If you use this software, please give us credit by referencing
# https://aclanthology.org/2025.acl-demo.4/.
#
# This script trains NameTag 3 on the Czech Historical Named Entity Corpus
# (CHNEC) with the CoNLL NE labels (PER, ORG, LOC, MISC) by further fine-tuning
# the nametag3-multilingual-250203 model
# (https://ufal.mff.cuni.cz/nametag/3/models#multilingual).
#
# The corpus can be downloaded here:
#
# http://chnec.kiv.zcu.cz/
#
# For further information about this corpus, see https://aclanthology.org/2020.lrec-1.549.pdf
#
# To submit to Slurm, call this script as:
#
# sbatch -C "gpuram40G|gpuram48G" --mem=8G ./11_chnec-conll_after_multilingual.sh
#
# You may be able to get away with less GPU RAM than 40G|48G for fine-tuning
# a model of Base size (~110M params), as this GPU RAM is safe for a Large
# model.

cd ..

DATA="data_preprocessed/czech-chnec-conll"
PYTHON=venv/bin/python3

$PYTHON nametag3.py \
  --batch_size=4 \
  --context_type="split_document" \
  --corpus="czech-chnec-conll" \
  --decoding="classification" \
  --dev_data="$DATA/dev.conll" \
  --epochs=10 \
  --evaluate_test_data \
  --hf_plm="xlm-roberta-large" \
  --learning_rate=2e-5 \
  --load_checkpoint="models/nametag3-multilingual-250203/" \
  --logdir="logs_tutorial" \
  --name="chnec-conll" \
  --tagsets="conll" \
  --test_data="$DATA/test.conll" \
  --train_data="$DATA/train.conll" \
