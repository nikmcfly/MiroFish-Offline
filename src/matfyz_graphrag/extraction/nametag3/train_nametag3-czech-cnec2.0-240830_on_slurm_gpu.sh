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

# NameTag 3 training script for the nametag3-czech-cnec2.0-240803 model.
#
# The model is released and distributed by LINDAT:
#
# Straková, Jana, 2024, NameTag 3 Czech CNEC 2.0 Model, LINDAT/CLARIAH-CZ
# digital library at the Institute of Formal and Applied Linguistics (ÚFAL),
# Faculty of Mathematics and Physics, Charles University,
# http://hdl.handle.net/11234/1-5677.
#
# To submit to Slurm, call this script as:
#
# sbatch -C "gpuram40G|gpuram48G" --mem=8G ./train_nametag3-czech-cnec2.0-240830_on_slurm_gpu.sh
#
# You may be able to get away with less GPU RAM than 40G|48G for fine-tuning
# a model of Base size (~110M params), as this GPU RAM is safe for a Large
# model.

DATA="data_preprocessed"
PYTHON=venv/bin/python3

$PYTHON nametag3.py \
  --batch_size=4 \
  --context_type="sentence" \
  --corpus="czech-cnec2.0" \
  --decoding="seq2seq" \
  --dev_data="$DATA/czech-cnec2.0/dev.conll" \
  --dropout=0.5 \
  --epochs=20 \
  --epochs_frozen=20 \
  --evaluate_test_data \
  --hf_plm="ufal/robeczech-base" \
  --latent_dim=256 \
  --learning_rate=2e-5 \
  --learning_rate_frozen=1e-3 \
  --logdir="logs/" \
  --name="$corpus" \
  --sampling="concatenate" \
  --save_best_checkpoint \
  --test_data="$DATA/czech-cnec2.0/test.conll" \
  --threads=4 \
  --train_data="$DATA/czech-cnec2.0/train.conll" \
  --warmup_epochs=1 \
  --warmup_epochs_frozen=1
