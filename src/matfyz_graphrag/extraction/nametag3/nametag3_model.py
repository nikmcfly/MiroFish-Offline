#!/usr/bin/env python3
# coding=utf-8
#
# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""NameTag3Model class.

The main prediction method is predict():

Predicts labels for NameTag3Dataset (see nametag3_dataset.py).
No sanity check of the neural network output is done, which means:

1. Neither correct nesting of the entities, nor correct entity openings and
closing (correct bracketing) are guaranteed.

2. Labels and their encoding (BIO aka IOB-2 vs. IOB) is the exact same as in
the model trained from and underlying corpus (i.e., IOB as found in English
CoNLL-2003 dataset).

See the postprocess() method for correct bracketing and BIO (IOB-2) formatting
of the output.
"""

import json
import os
import sys
import time

import keras
import numpy as np
import seqeval.metrics
import torch
import transformers

import nametag3_dataset

##############################
### NameTag3 Model Factory ###
##############################


def nametag3_model_factory(decoding="classification"):
    """Returns either the flat or nested NameTag3 Model."""

    if decoding == "classification":
        return NameTag3ModelClassification
    elif decoding == "seq2seq":
        return NameTag3ModelSeq2seq
    else:
        raise ValueError('Unknown decoding "{}"'.format(args.decoding))


########################################
### Helper classes for NameTag3Model ###
########################################


# DecoderTraining and DecoderPrediction implement the seq2seq decoder with hard
# attention for nested NER proposed in https://aclanthology.org/P19-1527.pdf.


class DecoderTraining(keras.layers.Layer):
    """Seq2seq decoder with hard attention for training."""

    def __init__(self, output_layer_dim, latent_dim=256):
        super().__init__()
        self._latent_dim = latent_dim
        self._output_layer_dim = output_layer_dim

        self._embeddings = keras.layers.Embedding(
            self._output_layer_dim, self._latent_dim
        )
        self._decoder_lstm = keras.layers.LSTM(self._latent_dim, return_sequences=True)
        self._decoder_output_layer = keras.layers.Dense(self._output_layer_dim)

    def call(self, inputs, targets, training=True):
        """Implements teacher-forced seq2seq decoder with LSTM cell and hard
        attention on the current word.

        inputs: encoder output, the initial state of the decoder.
        targets: gold output tags for teacher forcing.
        """

        # We need to create decoder_inputs such that they are a concatenation
        # (concat will be the last step) of embedded targets (teacher-forced
        # decoder_input) and the current word representation (hard attention),
        # where the current word attention is represented by the corresponding
        # HF PLM contextualized embedding from inputs.

        # Generate targets for the decoder: the previous generated label, which
        # are obtained from targets by
        # - prepending BOS as the first element of every batch example,
        # - dropping the last element of targets.
        shifted_targets = torch.nn.functional.pad(
            targets[:, :-1], (1, 0), value=nametag3_dataset.BOS
        )

        # Embed the shifted and padded targets.
        embedded_targets = self._embeddings(shifted_targets)

        # To get the corresponding contextualized embedding from inputs for
        # each of the targets, first get the increasing indices of the targets
        # in inputs, e.g., [0, 0, 1, 1, 2, 3, 3, 3, 4, 4].
        indices = torch.cumsum(shifted_targets == nametag3_dataset.EOW, dim=-1).cpu()

        # Replace attention indices that already moved one position behind the
        # sentence length with a fake attention index in order to not raise an
        # IndexError. We will ignore these predictions anyway but we need to
        # feed the LSTM.
        indices[targets == nametag3_dataset.BATCH_PAD] = 0

        # Index boundaries check.
        condition = indices < inputs.shape[1]
        assert (
            condition.all().item()
        ), "DecoderTraining.call(): Not all elements of indices are smaller than the inputs.shape[1]."

        # Index the inputs so that we get repeated word representations for the
        # target values (hard attention on current word for targets).
        hard_attention = keras.ops.take_along_axis(
            inputs, keras.ops.expand_dims(indices, -1), axis=1
        )

        # Finally, concatenate the embeded targets and the hard attention as
        # inputs to the LSTM decoder.
        decoder_inputs = torch.concat([embedded_targets, hard_attention], dim=-1)

        hidden = self._decoder_lstm(decoder_inputs)
        return self._decoder_output_layer(hidden)


class DecoderPrediction(keras.layers.Layer):
    """Seq2seq decoder with hard attention for prediction."""

    def __init__(
        self, decoder_training, output_layer_dim, latent_dim=256, max_labels_per_token=5
    ):
        super().__init__()
        self._latent_dim = latent_dim
        self._output_layer_dim = output_layer_dim
        self._max_labels_per_token = max_labels_per_token

        self._embeddings = decoder_training._embeddings
        self._decoder_lstm_cell = decoder_training._decoder_lstm.cell
        self._decoder_output_layer = decoder_training._decoder_output_layer

    def call(self, inputs, word_ids, training=False):
        """Implements auto-regressive seq2seq decoder.

        The decoder uses LSTM cells and hard attention on the current word.

        inputs: encoder output, the initial state of the decoder.
        """

        # We need to create decoder_inputs such that they are a concatenation
        # (concat will be the last step) of the target generated in the
        # previous step (no gold data available in prediction, so this is
        # auto-regressive) and the current word representation (hard
        # attention), where the current word attention is represented by the
        # corresponding HF PLM contextualized embedding from inputs.

        # As we have to collect the previously generated targets ourselves, we
        # have to cycle through the LSTM cell manually.

        index = 0
        targets = torch.full(
            [inputs.shape[0]],
            nametag3_dataset.BOS,
            dtype=torch.int64,
            device=inputs.device,
        )
        states = self._decoder_lstm_cell.get_initial_state(inputs.shape[0])
        results = []  # outputs generated in previous steps
        hard_attention_indices = torch.zeros(
            [inputs.shape[0]], dtype=torch.int64, device=inputs.device
        )
        hard_attention_indices_reps = torch.zeros_like(hard_attention_indices)
        batch_indices = torch.arange(inputs.shape[0], device=inputs.device)
        timesteps = torch.sum(word_ids != nametag3_dataset.BATCH_PAD, dim=-1)

        while index < self._max_labels_per_token * inputs.shape[1] and not torch.all(
            hard_attention_indices == timesteps
        ):
            embedded_targets = self._embeddings(targets)

            # Replace attention indices that already moved one position behind
            # the sentence length with a fake attention index at the last valid
            # position in order to not raise an IndexError. We will ignore
            # these predictions anyway but we need to feed the LSTM.
            adjusted_hard_attention_indices = hard_attention_indices.where(
                hard_attention_indices < timesteps, hard_attention_indices - 1
            )

            # Index boundaries check.
            condition = adjusted_hard_attention_indices < inputs.shape[1]
            assert (
                condition.all().item()
            ), "DecoderPrediction.call(): Not all elements of indices are smaller than the inputs.shape[1]."

            hard_attentions = inputs[batch_indices, adjusted_hard_attention_indices]
            decoder_inputs = torch.concat([embedded_targets, hard_attentions], axis=-1)

            hidden, states = self._decoder_lstm_cell(decoder_inputs, states)
            outputs = self._decoder_output_layer(hidden)
            predictions = outputs.argmax(dim=-1)

            # If number of predicted outputs per token exceeds
            # _max_labels_per_token, force EOW on this token.
            predictions[hard_attention_indices_reps >= self._max_labels_per_token] = (
                nametag3_dataset.EOW
            )

            # Store the meaningful predictions on positions still attended
            # inside the sentence, the rest gets BATCH_PAD.
            results.append(
                torch.full(
                    [inputs.shape[0]], nametag3_dataset.BATCH_PAD, device=inputs.device
                )
            )
            results[-1] = results[-1].where(
                hard_attention_indices == timesteps, predictions
            )

            # Update the hard_attention_indices by setting it to current index
            # if an EOW was generated for the first time, but only for those
            # which have not yet attentioned beyond the sentence length.
            hard_attention_indices_increment = (predictions == nametag3_dataset.EOW) & (
                hard_attention_indices < timesteps
            )
            hard_attention_indices += hard_attention_indices_increment
            hard_attention_indices_reps.masked_fill_(
                hard_attention_indices_increment, 0
            )

            # Finally, move forward in time.
            targets = predictions
            index += 1

        results = torch.stack(results, dim=1)
        return results


class TorchTensorBoardCallback(keras.callbacks.Callback):
    """Torch tensorboard to avoid dependency on tensorflow."""

    def __init__(self, path):
        self._path = path
        self._writers = {}

    def writer(self, writer):
        if writer not in self._writers:
            import torch.utils.tensorboard

            self._writers[writer] = torch.utils.tensorboard.SummaryWriter(
                os.path.join(self._path, writer)
            )
        return self._writers[writer]

    def add_logs(self, writer, logs, step):
        if logs:
            for key, value in logs.items():
                self.writer(writer).add_scalar(key, value, step)
            self.writer(writer).flush()

    def on_epoch_end(self, epoch, logs=None):
        if logs:
            if isinstance(
                getattr(self.model, "optimizer", None), keras.optimizers.Optimizer
            ):
                logs = logs | {
                    "learning_rate": keras.ops.convert_to_numpy(
                        self.model.optimizer.learning_rate
                    )
                }
            self.add_logs(
                "train",
                {k: v for k, v in logs.items() if not k.startswith("val_")},
                epoch + 1,
            )
            self.add_logs(
                "val",
                {k[4:]: v for k, v in logs.items() if k.startswith("val_")},
                epoch + 1,
            )


class RestoreBestWeightsCallback(keras.callbacks.Callback):

    def __init__(self, objective="val_macro_avg_f1"):
        self._best = None
        self._objective = objective

    def on_epoch_end(self, epoch, logs):
        metric = logs[self._objective]
        if self._best is None or metric > self._best:
            self._best = metric
            self._best_epoch = epoch
            self._best_weights = self.model.get_weights()

    def on_train_end(self, logs):
        print(
            "Restoring weights from the end of best epoch {} with maximum {}: {:.4f}".format(
                self._best_epoch + 1, self._objective, self._best
            ),
            file=sys.stderr,
            flush=True,
        )
        self.model.set_weights(self._best_weights)


class NestedF1Score(keras.metrics.Metric):
    """Custom Keras metric for nested span-based micro F1 score."""

    def __init__(self, id2label, name="f1", **kwargs):
        super().__init__(name=name, **kwargs)
        self._id2label = id2label
        self._tp = 0
        self._npred = 0
        self._ntrue = 0

    def _get_entities(self, encoded_labels, max_tokens=None, padding_mask=None):

        entities = set()
        token_count = 0
        for s, sentence in enumerate(encoded_labels):

            labels_on_current_token, sentence_tokens = 0, 0
            open_ids, open_labels = [], []
            for l, label in enumerate(sentence):
                if label == nametag3_dataset.BATCH_PAD:
                    break

                if padding_mask and padding_mask[s][l]:
                    break

                if max_tokens and sentence_tokens >= max_tokens[s]:
                    break

                if label == nametag3_dataset.EOW:  # move to next token
                    labels_on_current_token = 0
                    token_count += 1
                    sentence_tokens += 1
                    continue

                # Process next label
                label = self._id2label[label]

                if label == "O" or label in nametag3_dataset.CONTROL_LABELS:
                    for open_id, open_label in zip(open_ids, open_labels):
                        entities.add((open_label, open_id[0], open_id[-1]))
                    open_ids, open_labels = [], []
                else:
                    if labels_on_current_token < len(
                        open_ids
                    ):  # previously open entities exist

                        # Previous open entity ends here, close it and open a new entity instead
                        if (
                            label.startswith("B-")
                            or label.startswith("U-")
                            or open_labels[labels_on_current_token]
                            != label.split("-")[1]
                        ):
                            entities.add(
                                (
                                    open_labels[labels_on_current_token],
                                    open_ids[labels_on_current_token][0],
                                    open_ids[labels_on_current_token][-1],
                                )
                            )
                            open_ids[labels_on_current_token] = [token_count]

                        else:  # entity continues
                            open_ids[labels_on_current_token].append(token_count)

                        open_labels[labels_on_current_token] = label.split("-")[1]

                    else:  # new entity, no open entities, just append
                        open_ids.append([token_count])
                        open_labels.append(label.split("-")[1])

                labels_on_current_token += 1

            # end of sentence, close any open entities
            for open_id, open_label in zip(open_ids, open_labels):
                entities.add((open_label, open_id[0], open_id[-1]))

        return entities

    def update_state(self, y_true, y_pred, sample_weight=None):
        # Get true entities
        true_entities = self._get_entities(y_true.tolist())

        # Get pred entities
        max_tokens = torch.sum(y_true == nametag3_dataset.EOW, dim=-1)
        if y_pred.dim() == 3:  # y_pred training shape
            y_pred = torch.argmax(y_pred, dim=-1)
            padding_mask = y_true == nametag3_dataset.BATCH_PAD
            pred_entities = self._get_entities(
                y_pred.tolist(),
                max_tokens=max_tokens.tolist(),
                padding_mask=padding_mask.tolist(),
            )
        else:  # y_pred inference shape
            pred_entities = self._get_entities(
                y_pred.tolist(), max_tokens=max_tokens.tolist()
            )

        # Update number of true and predicted entities
        self._ntrue += len(true_entities)
        self._npred += len(pred_entities)

        # Update number of true positives
        true_positives = pred_entities.intersection(true_entities)
        self._tp += len(true_positives)

    def reset_state(self):
        self._tp = 0
        self._npred = 0
        self._ntrue = 0

    def result(self):
        precision = self._tp / self._npred if self._npred else 0
        recall = self._tp / self._ntrue if self._ntrue else 0

        return (
            2 * precision * recall / (precision + recall) if (precision + recall) else 0
        )


class SeqevalF1Score(keras.metrics.Metric):
    """Custom Keras metric for flat span-based micro F1 score."""

    def __init__(self, id2label, name="f1", **kwargs):
        super().__init__(name=name, **kwargs)
        self._id2label = id2label
        self._tp = 0
        self._npred = 0
        self._ntrue = 0

    def _decode_entities(self, label_ids, true_ids):
        decoded = []
        for s, sentence in enumerate(label_ids.tolist()):
            decoded.append([])
            for i, label_id in enumerate(sentence):
                if (
                    true_ids[s][i] == nametag3_dataset.BATCH_PAD
                ):  # end of sentence in gold data
                    break
                decoded[-1].append(self._id2label[label_id])
        return decoded

    def update_state(self, y_true, y_pred, sample_weight=None):
        with torch.no_grad():
            # Get gold entities
            y_true_decoded = self._decode_entities(y_true, y_true)
            true_entities = seqeval.metrics.sequence_labeling.get_entities(
                y_true_decoded
            )

            # Get predicted entities
            y_pred_idxs = np.argmax(keras.ops.convert_to_numpy(y_pred), axis=-1)
            y_pred_decoded = self._decode_entities(y_pred_idxs, y_true)
            pred_entities = seqeval.metrics.sequence_labeling.get_entities(
                y_pred_decoded
            )

        self._ntrue += len(true_entities)
        self._npred += len(pred_entities)

        true_positives = [x for x in pred_entities if x in true_entities]
        self._tp += len(true_positives)

    def reset_state(self):
        self._tp = 0
        self._npred = 0
        self._ntrue = 0

    def result(self):
        precision = self._tp / self._npred if self._npred else 0
        recall = self._tp / self._ntrue if self._ntrue else 0

        return (
            2 * precision * recall / (precision + recall) if (precision + recall) else 0
        )


class GatherLayer(keras.layers.Layer):
    """Custom Keras layer for gathering embeddings by indices.

    This is necessary because we have to predict label(s) on each word, which
    can however be subtokenized into subwords (input_ids) by the HF tokenizer.
    The indices mark the first subword (input_id) of each word.
    """

    def call(self, inputs, word_ids):
        return keras.ops.take_along_axis(
            inputs,
            keras.ops.expand_dims(
                keras.ops.maximum(word_ids, 0), nametag3_dataset.BATCH_PAD
            ),
            axis=1,
        )


class TagsetMaskLayer(keras.layers.Layer):

    def call(self, inputs, tagset_masks):
        return (
            inputs
            + tagset_masks[
                :,
                None,
            ]
        )


class PLMLayer(keras.layers.Layer):
    """Custom Keras layer as a wrapper around PyTorch AutoModel."""

    def __init__(self, hf_plm, tokenizer, load_checkpoint):
        super().__init__()

        if load_checkpoint:
            config = transformers.AutoConfig.from_pretrained(hf_plm)
            self._plm = transformers.AutoModel.from_config(config)
        else:
            self._plm = transformers.AutoModel.from_pretrained(hf_plm)

    def call(self, inputs, training=False):
        return self._plm(
            keras.ops.maximum(inputs, 0),
            attention_mask=inputs > nametag3_dataset.BATCH_PAD,
        ).last_hidden_state


class MacroAverageDevF1(keras.callbacks.Callback):
    """Computes macro average span-based micro F1 over all dev datasets."""

    def __init__(self, args, dev_collection):
        self._args = args
        self._dev_datasets = dev_collection.datasets

    def on_epoch_end(self, epoch, logs=None):
        print(
            "Dev evaluation after epoch {}".format(epoch + 1),
            file=sys.stderr,
            flush=True,
        )

        dev_scores = []
        for i in range(len(self._dev_datasets)):

            # Predict the output and write to file
            predictions_filename = "{}_{}_predictions.conll".format(
                "dev", self._dev_datasets[i].corpus
            )
            predicted_output = "".join(
                self.model.predict("dev", self._dev_datasets[i], self._args)
            )
            with open(
                os.path.join(self._args.logdir, predictions_filename),
                "w",
                encoding="utf-8",
            ) as predictions_file:
                print(predicted_output, file=predictions_file, end="")

            # Evaluate
            dev_score = self._dev_datasets[i].evaluate(
                "dev", predictions_filename, self._args.logdir
            )
            dev_scores.append(dev_score)
            print(
                "F1 on dev {} ({}): {:.4f}".format(
                    i, self._dev_datasets[i].corpus, dev_score
                ),
                file=sys.stderr,
                flush=True,
            )

        logs["val_macro_avg_f1"] = np.sum(dev_scores) / len(dev_scores)


class SafeSparseCategoricalCrossentropy(keras.losses.SparseCategoricalCrossentropy):
    """Wraps SparseCategoricalCrossentropy and returns 0 for symbolic pre-run."""

    def __init__(self, from_logits=False, ignore_class=None):
        super().__init__(from_logits=from_logits, ignore_class=ignore_class)

    def call(self, y_true, y_pred):
        # Return 0 only if we're in symbolic pre-run (meta tensors)
        if getattr(y_pred, "device", None) and y_pred.device.type == "meta":
            return y_pred.new_zeros(())
        return super().call(y_true, y_pred)


#####################
### NameTag3Model ###
#####################


class NameTag3Model(keras.Model):
    """NameTag3 neural network class."""

    def __init__(self, output_layer_dim, args, id2label, tokenizer):
        """Constructs the model."""

        super().__init__()

        # Layers
        self._embeddings = PLMLayer(
            args.hf_plm, tokenizer, load_checkpoint=args.load_checkpoint
        )
        self._gathered = GatherLayer()
        self._dropout = keras.layers.Dropout(args.dropout)

        # Other
        self._output_layer_dim = output_layer_dim
        self._args = args
        self._id2label = id2label

        # Callback for saving the best checkpoint. Saved here for transfering
        # between frozen pretraining and fine-tuning.
        self._model_checkpoint = None

    def compile(self, training_batches=0, frozen=False):
        """Compiles the model for either frozen training or fine-tuning."""

        self._embeddings.trainable = not frozen

        if frozen:
            super().compile(
                optimizer=keras.optimizers.Adam(
                    learning_rate=keras.optimizers.schedules.CosineDecay(
                        (
                            0.0
                            if self._args.warmup_epochs_frozen
                            else self._args.learning_rate_frozen
                        ),  # initial learning rate
                        training_batches
                        * (
                            self._args.epochs_frozen - self._args.warmup_epochs_frozen
                        ),  # decay steps
                        warmup_target=self._args.learning_rate_frozen,  # target learning rate
                        warmup_steps=training_batches * self._args.warmup_epochs_frozen,
                    )
                ),  # warmup_steps
                loss=SafeSparseCategoricalCrossentropy(
                    from_logits=True, ignore_class=nametag3_dataset.BATCH_PAD
                ),
                metrics=self._create_metrics(),
            )
        else:
            if (
                training_batches * max(self._args.epochs - self._args.warmup_epochs, 0)
                <= 0
            ):
                schedule = self._args.learning_rate
            else:
                schedule = keras.optimizers.schedules.CosineDecay(
                    (
                        0.0 if self._args.warmup_epochs else self._args.learning_rate
                    ),  # initial learning rate
                    training_batches
                    * max(
                        self._args.epochs - self._args.warmup_epochs, 0
                    ),  # decay steps
                    warmup_target=self._args.learning_rate,  # target learning rate
                    warmup_steps=training_batches * self._args.warmup_epochs,
                )

            super().compile(
                optimizer=keras.optimizers.Adam(learning_rate=schedule),
                loss=SafeSparseCategoricalCrossentropy(
                    from_logits=True, ignore_class=nametag3_dataset.BATCH_PAD
                ),
                metrics=self._create_metrics(),
            )

    def postprocess(self, text):
        """Postprocesses predicted output.

        Guarantees correctly bracketed and unique NEs in the BIO (IOB-2)
        format.
        """

        forms, previous_labels, starts = [], [], []
        entities = dict()  # (start, end, label)

        for i, line in enumerate(text.split("\n")):
            if not line:  # end of sentence
                forms.append("")
                for j in range(len(previous_labels)):  # close entities
                    entities[(starts[j], i, previous_labels[j][2:])] = j
                previous_labels, starts = [], []
            else:
                form, ne = line.split("\t")
                if ne == "O":  # all entities ended
                    forms.append(form)
                    for j in range(len(previous_labels)):  # close entities
                        entities[(starts[j], i, previous_labels[j][2:])] = j
                    previous_labels, starts = [], []
                else:
                    labels = ne.split("|")
                    for j in range(len(labels)):
                        if labels[j] == "O":  # bad decoder output, "O" should be alone
                            labels = labels[:j]
                            break
                        if j < len(previous_labels):
                            if (
                                labels[j].startswith("B-")
                                or previous_labels[j][2:] != labels[j][2:]
                            ):
                                # Previous entity was ended by current starting
                                # entity, forcing end of all its nested
                                # entities (following in the previous list):
                                for k in range(
                                    j, len(previous_labels)
                                ):  # close entities
                                    entities[(starts[k], i, previous_labels[k][2:])] = k
                                previous_labels = previous_labels[:j]
                                starts = starts[:j]
                                starts.append(i)
                        else:  # new entity starts here
                            starts.append(i)
                    forms.append(form)
                    if len(labels) < len(previous_labels):  # close entities
                        for j in range(len(labels), len(previous_labels)):
                            entities[(starts[j], i, previous_labels[j][2:])] = j
                    previous_labels = labels
                    starts = starts[: len(labels)]

        # Sort entities
        entities = sorted(entities.items(), key=lambda x: (x[0][0], -x[0][1], x[1]))

        # Reconstruct the CoNLL output with the entities set,
        # removing duplicates and changing IOB -> BIO
        labels = [[] for _ in range(len(forms))]
        for (start, end, label), _ in entities:
            for i in range(start, end):
                labels[i].append(("B-" if i == start else "I-") + label)

        output = []
        for form, label in zip(forms, labels):
            if form:
                output.append(
                    "{}\t{}\n".format(form, "|".join(label) if label else "O")
                )
            else:
                output.append("\n")

        if output and output[-1] == "\n":
            output.pop()

        return "".join(output)

    def load_checkpoint(self, path):
        """Loads checkpoint from path."""

        print(
            'Loading previously saved checkpoint from "{}"'.format(path),
            file=sys.stderr,
            flush=True,
        )

        # Must call on fake dummy batch to force build.
        self(
            (
                keras.ops.ones((1, 1), dtype="int32"),
                keras.ops.zeros((1, 1), dtype="int32"),
                keras.ops.zeros((1,), dtype="float32"),
            )
        )

        self.load_weights(path)

        # Make sure we do not restore the number of iterations from the checkpoint.
        # For this to work, the optimizer must be already created; if it is not,
        # the next line will raise an exception.
        if hasattr(self, "optimizer"):
            self.optimizer.iterations.assign(0)

    def fit(
        self,
        epochs,
        train_collection,
        dev_collection=None,
        save_best_checkpoint=False,
        initial_epoch=0,
    ):
        """ "Trains (frozen or fine-tuning) the model."""

        callbacks = []

        if dev_collection:
            callbacks.append(MacroAverageDevF1(self._args, dev_collection))
            callbacks.append(RestoreBestWeightsCallback(objective="val_macro_avg_f1"))

        callbacks.append(TorchTensorBoardCallback(self._args.logdir))

        if save_best_checkpoint:
            print(
                "Checkpoint will be saved to logdir: {}/model".format(
                    self._args.logdir
                ),
                file=sys.stderr,
                flush=True,
            )

            # Save model training arguments
            os.makedirs("{}/model".format(self._args.logdir), exist_ok=True)
            with open(
                "{}/model/options.json".format(self._args.logdir), mode="w"
            ) as options_file:
                json.dump(vars(self._args), options_file, sort_keys=True)

            # Add ModelCheckpoint callback
            if self._model_checkpoint == None:
                self._model_checkpoint = keras.callbacks.ModelCheckpoint(
                    os.path.join(
                        self._args.logdir, "model", self._args.checkpoint_filename
                    ),
                    save_best_only=True,
                    save_weights_only=True,
                    monitor="val_macro_avg_f1",
                    mode="max",
                    verbose=2,
                )

            callbacks.append(self._model_checkpoint)

        super().fit(
            train_collection.dataloader,
            validation_data=dev_collection.dataloader if dev_collection else None,
            epochs=epochs,
            verbose=2,
            steps_per_epoch=self._args.steps_per_epoch,
            callbacks=callbacks,
            initial_epoch=initial_epoch,
        )

    def predict(self, dataset_name, dataset, args):
        """Predicts labels for NameTag3Dataset.

        No sanity check of the neural network output is done, which means:

        1. Neither correct nesting of the entities, nor correct entity openings and
        closing (correct bracketing) are guaranteed.

        2. Labels and their encoding (BIO aka IOB-2 vs. IOB) is the exact same as in
        the model trained from and underlying corpus (i.e., IOB as found in English
        CoNLL-2003 dataset).

        See the postprocess() method for correct bracketing and BIO (IOB-2) formatting
        of the output.
        """

        output = []
        for batch_output in self.yield_predicted_batches(dataset_name, dataset, args):
            output.extend(batch_output)
        return output


class NameTag3ModelSeq2seq(NameTag3Model):
    """NameTag3 model with seq2seq decoding for nested NEs."""

    def __init__(self, output_layer_dim, args, id2label, tokenizer):
        super().__init__(output_layer_dim, args, id2label, tokenizer)

        self._latent_dim = args.latent_dim
        self._max_labels_per_token = args.max_labels_per_token

    # Never remove the training argument for magical reasons.
    # The magical reason being that the training argument must be set at least
    # once on the layer stack for Keras to infer the training parameters for
    # all subsequent layers from the context.
    def call(self, inputs, training=False):
        """Forward pass."""

        # Make sure we are in correct training/inference mode, as HF
        # Transformer loaded with from_config() by default sets training, while
        # from_pretrained() by default sets inference.
        if (training or False) != self._embeddings.training:
            self._embeddings.train(training or False)

        input_ids, word_ids, _ = inputs
        embeddings = self._embeddings(input_ids)
        gathered = self._gathered(embeddings, word_ids=word_ids)
        dropout = self._dropout(gathered)
        return self._decoder_prediction_layer(dropout, word_ids)

    def build(self, _input_shape):
        self._decoder_training_layer = DecoderTraining(
            self._output_layer_dim, self._latent_dim
        )
        self._decoder_prediction_layer = DecoderPrediction(
            self._decoder_training_layer,
            self._output_layer_dim,
            self._latent_dim,
            self._max_labels_per_token,
        )

    def train_step(self, data):
        """Override train_step to use DecoderTraining."""

        x, y = data
        input_ids, word_ids, _ = x

        # Compute predictions.
        embeddings = self._embeddings(input_ids, training=True)
        gathered = self._gathered(embeddings, word_ids=word_ids, training=True)
        dropout = self._dropout(gathered, training=True)
        y_pred = self._decoder_training_layer(
            dropout, y, training=True
        )  # use decoder training

        # Call torch.nn.Module.zero_grad() to clear the leftover gradients
        # for the weights from the previous train step.
        self.zero_grad()

        loss = self.compute_loss(x=x, y=y, y_pred=y_pred)
        self._loss_tracker.update_state(loss)

        # Compute gradients.
        if self.trainable_weights:
            # Call torch.Tensor.backward() on the loss to compute gradients
            # for the weights.
            loss.backward()

            trainable_weights = self.trainable_weights[:]
            gradients = [v.value.grad for v in trainable_weights]

            # Update weights.
            with torch.no_grad():
                self.optimizer.apply(gradients, trainable_weights)

        return self.compute_metrics(x, y, y_pred)

    def test_step(self, data):
        """Override test_step to avoid loss computation.

        Computing loss is complicated for generated output which can differ in
        length from the gold output.
        """

        x, y = data
        input_ids, word_ids, _ = x

        y_pred = self(x, training=False)

        return self.compute_metrics(x, y, y_pred)

    def _create_metrics(self):
        return [NestedF1Score(self._id2label, name="f1")]

    def yield_predicted_batches(self, dataset_name, dataset, args):
        """Yields batches with predicted nested labels for NameTag3Dataset.

        No sanity check of the neural network output is done, which means:

        1. Neither correct nesting of the entities, nor correct entity openings and
        closing (correct bracketing) are guaranteed.

        2. Labels and their encoding (BIO aka IOB-2 vs. IOB) is the exact same as in
        the model trained from and underlying corpus (i.e., IOB as found in English
        CoNLL-2003 dataset).

        See the postprocess() method for correct bracketing and BIO (IOB-2) formatting
        of the output.
        """

        # For simplicity, seq2seq batch decoding is implemented for
        # --context_type=sentence only. The sentences are never concatenated to
        # create a larger context and are always processed one by one. The only
        # disturbance is when the sentence is too long and must be splitted
        # into two splits, but even then the sentences (their splits) are
        # always processed separately.

        predicted_tag_ids = []  # all predicted tag ids (sentences x tags)
        batch_output = []  # accumulated batch output to be yielded
        forms = dataset.forms()
        docstarts = dataset.docstarts()
        batch_iterator = iter(dataset.create_torch_dataloader(args, shuffle=False))
        yield_batch = False  # yield batch at the end of sentence

        for s in range(len(forms)):  # original sentences
            batch_output.append("")

            if docstarts[s]:
                batch_output.append(docstarts[s])

            t = 0
            for f in range(len(forms[s])):  # original words
                # Not enough sentences predicted or sentence split between
                # batches => predict next batch.
                # TODO: This will always lead to the first sentence being
                # yielded separately in the first batch actually, add
                # a condition to prevent this.
                if s >= len(predicted_tag_ids) or (
                    t >= len(predicted_tag_ids[s])
                    and len(predicted_tag_ids) < len(forms)
                ):
                    inputs, _ = next(batch_iterator)
                    for sentence_predicted_tag_ids in self.predict_on_batch(inputs):
                        predicted_tag_ids.append(
                            sentence_predicted_tag_ids[
                                sentence_predicted_tag_ids != nametag3_dataset.BATCH_PAD
                            ].tolist()
                        )
                    t = 0
                    yield_batch = True

                labels = []
                while (
                    t < len(predicted_tag_ids[s])
                    and predicted_tag_ids[s][t] != nametag3_dataset.EOW
                ):
                    sublabel = self._id2label[predicted_tag_ids[s][t]]
                    if sublabel not in nametag3_dataset.CONTROL_LABELS:
                        labels.append(sublabel)
                    t += 1

                if t < len(predicted_tag_ids[s]):
                    t += 1  # skip the EOW
                label = "|".join(labels) if labels else "O"

                batch_output[-1] += "{}\t{}\n".format(forms[s][f], label)

            batch_output[-1] += "\n"

            if yield_batch:
                yield batch_output
                batch_output = []
                yield_batch = False

        if batch_output:  # flush the last batch
            yield batch_output


class NameTag3ModelClassification(NameTag3Model):
    """NameTag3 model with classification."""

    def __init__(self, output_layer_dim, args, id2label, tokenizer):
        super().__init__(output_layer_dim, args, id2label, tokenizer)

    # Never remove the training argument for magical reasons.
    # The magical reason being that the training argument must be set at least
    # once on the layer stack for Keras to infer the training parameters for
    # all subsequent layers from the context.
    def call(self, inputs, training=False):
        """Forward pass."""

        # Make sure we are in correct training/inference mode, as HF
        # Transformer loaded with from_config() by default sets training, while
        # from_pretrained() by default sets inference.
        if (training or False) != self._embeddings.training:
            self._embeddings.train(training or False)

        input_ids, word_ids, tagset_masks = inputs
        embeddings = self._embeddings(input_ids)
        gathered = self._gathered(embeddings, word_ids=word_ids)
        dropout = self._dropout(gathered)
        outputs = self._outputs(dropout)
        return self._tagset_masked_outputs(outputs, tagset_masks)

    def build(self, _input_shape):
        self._outputs = keras.layers.Dense(self._output_layer_dim)
        self._tagset_masked_outputs = TagsetMaskLayer()

    def _create_metrics(self):
        return [SeqevalF1Score(self._id2label, name="f1")]

    def yield_predicted_batches(self, dataset_name, dataset, args):
        """Yields batches with predicted flat labels for NameTag3Dataset.

        No sanity check of the neural network output is done, which means:

        1. Neither correct nesting of the entities, nor correct entity openings and
        closing (correct bracketing) are guaranteed.

        2. Labels and their encoding (BIO aka IOB-2 vs. IOB) is the exact same as in
        the model trained from and underlying corpus (i.e., IOB as found in English
        CoNLL-2003 dataset).

        See the postprocess() method for correct bracketing and BIO (IOB-2) formatting
        of the output.
        """

        # Unlike seq2seq, we allow all kinds of contexts for the softmax
        # classification head, including the entire document and/or the maximum
        # subwords window. This means the original sentences and the sentence
        # splits in batches to not match 1:1 and the indices move
        # independently. On the other hand, there is always exactly one tag per
        # token.

        predicted_tag_ids = []  # all predicted tag ids (sentences x tags)
        predicted_s = -1  # sentences/splits in predicted_tag_ids
        t = 0  # tags within sentences in predicted_tag_ids
        batch_output = []  # accumulated batch output to be yielded
        forms = dataset.forms()
        docstarts = dataset.docstarts()
        batch_iterator = iter(dataset.create_torch_dataloader(args, shuffle=False))
        yield_batch = False  # yield batch at the end of sentence

        for s in range(len(forms)):  # original sentences
            batch_output.append("")

            if docstarts[s]:
                batch_output.append(docstarts[s])

            for f in range(len(forms[s])):  # original words

                # No sentence split predicted yet or the last sentence split exhausted.
                if predicted_s == -1 or t >= len(predicted_tag_ids[predicted_s]):
                    predicted_s += 1  # move to the next sentence split

                    # Not enough sentences predicted => predict next batch.
                    # TODO: This will always lead to the first sentence being
                    # yielded separately in the first batch actually, add
                    # a condition to prevent this.
                    if predicted_s >= len(predicted_tag_ids):
                        inputs, _ = next(batch_iterator)
                        _, word_ids, tagset_masks = inputs
                        word_ids = word_ids.numpy(force=True)
                        tagset_masks = tagset_masks.numpy(force=True)

                        predicted_logits = self.predict_on_batch(inputs)

                        for i in range(len(predicted_logits)):
                            predicted_tag_ids.append(
                                np.argmax(
                                    predicted_logits[i][
                                        word_ids[i] != nametag3_dataset.BATCH_PAD
                                    ],
                                    axis=-1,
                                ).tolist()
                            )

                        yield_batch = True

                    t = 0

                # Read next label
                label = self._id2label[predicted_tag_ids[predicted_s][t]]
                if dataset.tagset:  # remove the tagset appendix
                    label = label.rsplit("-", 1)[0]
                t += 1

                batch_output[-1] += "{}\t{}\n".format(forms[s][f], label)

            batch_output[-1] += "\n"

            if yield_batch:
                yield batch_output
                batch_output = []
                yield_batch = False

        if batch_output:  # flush the last batch
            yield batch_output
