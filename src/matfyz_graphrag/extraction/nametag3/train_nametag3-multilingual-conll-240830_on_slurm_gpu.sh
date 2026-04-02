#!/bin/bash
#SBATCH -J ner
#SBATCH -p gpu-queue
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1

# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# NameTag3 training script for the nametag3-multilingual-conll-240830 model
#
# The model is released and distributed by LINDAT:
#
# Straková, Jana, 2024, NameTag 3 Multilingual CoNLL Model, LINDAT/CLARIAH-CZ
# digital library at the Institute of Formal and Applied Linguistics (ÚFAL),
# Faculty of Mathematics and Physics, Charles University,
# http://hdl.handle.net/11234/1-5678.
#
# To submit to Slurm, call this script as:
#
# sbatch -C "gpuram40G|gpuram48G" --mem=64G ./train_nametag3-multilingual-conll-240830_on_slurm_gpu.sh"
#
# You may be able to get away with less GPU RAM than 40G|48G for fine-tuning
# a model of Base size (~110M params), as this GPU RAM is safe for a Large
# model.

DATA="data_preprocessed"
PYTHON=venv/bin/python3

$PYTHON nametag3.py \
  --batch_size=8 \
  --context_type="split_document" \
  --corpus="english-CoNLL2003-conll,german-CoNLL2003-conll,spanish-CoNLL2002-conll,dutch-CoNLL2002-conll,czech-cnec2.0-conll,ukrainian-languk-conll" \
  --decoding="classification" \
  --dev_data="$DATA/english-CoNLL2003-conll/dev.conll,$DATA/german-CoNLL2003-conll/dev.conll,$DATA/spanish-CoNLL2002-conll/dev.conll,$DATA/dutch-CoNLL2002-conll/dev.conll,$DATA/czech-cnec2.0-conll/dev.conll,$DATA/ukrainian-languk-conll/dev.conll" \
  --dropout=0.5 \
  --epochs=20 \
  --evaluate_test_data \
  --hf_plm="xlm-roberta-large" \
  --learning_rate=2e-5 \
  --logdir="logs/" \
  --name="multilingual" \
  --sampling="temperature" \
  --save_best_checkpoint \
  --test_data="$DATA/english-CoNLL2003-conll/test.conll,$DATA/german-CoNLL2003-conll/test.conll,$DATA/spanish-CoNLL2002-conll/test.conll,$DATA/dutch-CoNLL2002-conll/test.conll,$DATA/czech-cnec2.0-conll/test.conll,$DATA/ukrainian-languk-conll/test.conll" \
  --threads=4 \
  --train_data="$DATA/english-CoNLL2003-conll/train.conll,$DATA/german-CoNLL2003-conll/train.conll,$DATA/spanish-CoNLL2002-conll/train.conll,$DATA/dutch-CoNLL2002-conll/train.conll,$DATA/czech-cnec2.0-conll/train.conll,$DATA/ukrainian-languk-conll/train.conll" \
  --warmup_epochs=1
