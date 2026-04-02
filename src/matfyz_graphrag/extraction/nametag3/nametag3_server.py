#!/usr/bin/env python3

# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University in Prague, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""NameTag 3 server.

Starting NameTag 3 server
-------------------------

The mandatory arguments are given in this order:

- port
- default model name
- each following quadruple of arguments defines a model, of which
    - the first argument is the model name,
    - the second argument is the model directory,
    - the third argument is the tagset of the model or empty string for models
        trained without tagsets,
    - the fourth argument are the acknowledgements to append.

If the model has been trained as a multitagset one, a single instance of such
trained model can be used with several tagset variants, just like in the
following example, in which one model ("models/nametag3-multilingual-250203/")
is served as a "nametag3-multilingual-conll-250203" model, then as
a "nametag3-multilingual-uner-250203" model, and finally, also as
a "nametag3-multilingual-onto-250203" model.

Furthermore, the model name in the first argument can be extended with aliases,
delimited by colons. In the following example, the Czech model
"nametag3-czech-cnec2.0-240830" is also served as "czech" and "cs".

Example Usage
-------------

In the following example, the server is loading two models, a Czech one, and
a multilingual one, which is also served with three different tagsets:

venv/bin/python3 ./nametag3_server.py 8001 nametag3-czech-cnec2.0-240830 \
    nametag3-czech-cnec2.0-240830:czech:cs models/nametag3-czech-cnec2.0-240830/ "" "czech-ack" \
    nametag3-multilingual-conll-250203 models/nametag3-multilingual-250203/ "conll" "multilingual-conll-250203-ack" \
    nametag3-multilingual-uner-250203 models/nametag3-multilingual-250203/ "uner" "multilingual-uner-250203-ack" \
    nametag3-multilingual-onto-250203 models/nametag3-multilingual-250203/ "onto" "multilingual-onto-250203-ack"

Example server usage with three monolingual models with name aliases, and the
models do not use specific tagsets (see the empty strings in their
corresponding third arguments):

$ venv/bin/python3 nametag3_server.py 8001 czech-cnec2.0-240830 \
    czech-cnec2.0-240830:cs:ces models/nametag3-czech-cnec2.0-240830/ "" czech-cnec2_acknowledgements \
    english-CoNLL2003-conll-240830:en:eng models/nametag3-english-CoNLL2003-conll-240830/ "" english-CoNLL2003-conll_acknowledgements \
    spanish-CoNLL2002-conll-240830:es:spa models/nametag3-spanish-CoNLL2002-conll-240830/ "" spanish-CoNLL2002-conll_acknowledgements

Sending requests to the NameTag 3 server
----------------------------------------

Example commandline call with curl:

$ curl -F data=@examples/cs_input.conll -F input="vertical" -F output="conll" localhost:8001/recognize | jq -j .result

Expected commandline output:

Jmenuji	O
se	O
Jan	B-P|B-pf
Novák	I-P|B-ps
.	O

"""

import argparse
import collections
import email.parser
import http.server
import itertools
import io
import json
import os
import pickle
import socketserver
import sys
import time
import unicodedata
import urllib.parse

os.environ.setdefault("KERAS_BACKEND", "torch")

import torch
import transformers

from nametag3_dataset_collection import NameTag3DatasetCollection
from nametag3_model import nametag3_model_factory
import ufal.udpipe

SEP = "\t"


class UDPipeTokenizer:
    class Token:
        def __init__(self, token, spaces_before, spaces_after):
            self.token = token
            self.spaces_before = spaces_before
            self.spaces_after = spaces_after

    def __init__(self, path):
        self._model = ufal.udpipe.Model.load(path)
        if self._model is None:
            raise RuntimeError("Cannot load tokenizer from {}".format(path))

    def tokenize(self, text, mode="untokenized"):
        if mode == "untokenized":
            tokenizer = self._model.newTokenizer(self._model.DEFAULT)
        elif mode == "vertical":
            tokenizer = ufal.udpipe.InputFormat.newVerticalInputFormat()
        elif mode.startswith("conllu"):
            tokenizer = ufal.udpipe.InputFormat.newConlluInputFormat()
        else:
            raise ValueError("Unknown tokenizer mode '{}'".format(mode))
        if tokenizer is None:
            raise RuntimeError("Cannot create the tokenizer")

        sentence = ufal.udpipe.Sentence()
        processing_error = ufal.udpipe.ProcessingError()
        tokenizer.setText(text)
        while tokenizer.nextSentence(sentence, processing_error):
            yield sentence
            sentence = ufal.udpipe.Sentence()
        if processing_error.occurred():
            raise RuntimeError(
                "Cannot read input data: '{}'".format(processing_error.message)
            )


class Models:
    """Initializes NameTag 3 models, UDPipe tokenizers and HF tokenizers."""

    class Model:
        """Initializes a NameTag 3 model.

        Initializes a NameTag3 model, along with the respective id2label and
        label2id mappings, the UDPipe tokenizer and the HF tokenizer.
        """

        def __init__(self, path, name, acknowledgements, server_args):
            self._server_args = server_args
            self.name = name
            self.acknowledgements = acknowledgements

            # Read train args from model
            with open("{}/options.json".format(path), mode="r") as options_file:
                self._args = argparse.Namespace(**json.load(options_file))

            if "max_labels_per_token" not in self._args:
                self._args.max_labels_per_token = server_args.max_labels_per_token

            self._args.batch_size = self._server_args.batch_size

            print(
                "Model options loaded successfully:\n{}".format(self._args),
                file=sys.stderr,
                flush=True,
            )

            # Load the HF tokenizer
            self.hf_tokenizer = transformers.AutoTokenizer.from_pretrained(
                self._args.hf_plm,
                add_prefix_space=self._args.hf_plm
                in ["roberta-base", "roberta-large", "ufal/robeczech-base"],
            )

            # Unpickle word mappings of train data
            self._train_collection = NameTag3DatasetCollection(
                self._args,
                self.hf_tokenizer,
                tagsets=(
                    self._args.tagsets
                    if hasattr(self._args, "tagsets") and self._args.tagsets
                    else None
                ),
            )
            with open("{}/mappings.pickle".format(path), mode="rb") as mappings_file:
                self._train_collection.load_collection_mappings(path)

            # Construct the network
            self.model = nametag3_model_factory(self._args.decoding)(
                len(self._train_collection.label2id().keys()),
                self._args,
                self._train_collection.id2label(),
                self.hf_tokenizer,
            )

            # Load the checkpoint
            self.model.load_checkpoint(
                os.path.join(path, self._args.checkpoint_filename)
            )

            # Load the UDPipe tokenizer
            tokenizer_path = os.path.join(path, "udpipe.tokenizer")
            self._udpipe_tokenizer = UDPipeTokenizer(tokenizer_path)
            if self._udpipe_tokenizer is None:
                raise RuntimeError(
                    "Cannot load tokenizer from {}".format(tokenizer_path)
                )

        def yield_predicted_batches(self, dataset):
            time_start = time.time()

            for batch_output in self.model.yield_predicted_batches(
                "test", dataset, self.args
            ):
                yield batch_output

            time_end = time.time()
            print(
                "Request {:.2f}ms,".format(1000 * (time_end - time_start)),
                file=sys.stderr,
                flush=True,
            )

        def postprocess(self, text):
            return self.model.postprocess(text)

        @property
        def args(self):
            return self._args

        def conll_to_conllu(self, ner_output, sentences, encoding, n_nes_in_batches):

            def _clean_misc(misc):
                return "|".join(
                    field for field in misc.split("|") if not field.startswith("NE=")
                )

            output = []
            output_writer = ufal.udpipe.OutputFormat.newConlluOutputFormat()

            n_sentences, n_words, n_multiwords, in_sentence = 0, 1, 0, False
            open_ids = []
            for line in ner_output.split("\n"):
                if not line:
                    if in_sentence:
                        output.append(
                            output_writer.writeSentence(sentences[n_sentences])
                        )
                        n_sentences += 1
                        n_words = 1
                        n_multiwords = 0
                    in_sentence = False
                else:
                    in_sentence = True

                    # This will work for properly nested entities,
                    # hence model.postprocess is important before conll_to_conllu.
                    if encoding == "conllu-ne":
                        nes_encoded = []
                        words_in_token = 1
                        form, ne = line.split(SEP)
                        if ne == "O":  # all entities ended
                            open_ids = []
                        else:
                            labels = ne.split("|")
                            for i in range(len(labels)):
                                if i < len(open_ids):
                                    if labels[i].startswith("B-"):
                                        # previous open entity ends here
                                        # -> close it and all open nested entities
                                        open_ids = open_ids[:i]
                                        # open new entity
                                        open_ids.append(n_nes_in_batches)
                                        n_nes_in_batches += 1
                                else:  # no running entities, new entity starts here, just append
                                    open_ids.append(n_nes_in_batches)
                                    n_nes_in_batches += 1
                            for i in range(len(labels)):
                                nes_encoded.append(
                                    labels[i][2:] + "_" + str(open_ids[i])
                                )

                        # Multiword token starts here -> consume more words
                        if (
                            n_multiwords < len(sentences[n_sentences].multiwordTokens)
                            and sentences[n_sentences]
                            .multiwordTokens[n_multiwords]
                            .idFirst
                            == n_words
                        ):
                            words_in_token = (
                                sentences[n_sentences]
                                .multiwordTokens[n_multiwords]
                                .idLast
                                - sentences[n_sentences]
                                .multiwordTokens[n_multiwords]
                                .idFirst
                                + 1
                            )
                            sentences[n_sentences].multiwordTokens[
                                n_multiwords
                            ].misc = _clean_misc(
                                sentences[n_sentences]
                                .multiwordTokens[n_multiwords]
                                .misc
                            )
                            if (
                                sentences[n_sentences]
                                .multiwordTokens[n_multiwords]
                                .misc
                                and nes_encoded
                            ):
                                sentences[n_sentences].multiwordTokens[
                                    n_multiwords
                                ].misc += "|"
                            if nes_encoded:
                                sentences[n_sentences].multiwordTokens[
                                    n_multiwords
                                ].misc += "NE="

                            sentences[n_sentences].multiwordTokens[
                                n_multiwords
                            ].misc = sentences[n_sentences].multiwordTokens[
                                n_multiwords
                            ].misc + "-".join(
                                nes_encoded
                            )
                            n_multiwords += 1

                        # Write NEs to MISC
                        for i in range(
                            words_in_token
                        ):  # consume all words in multiword token
                            sentences[n_sentences].words[n_words].misc = _clean_misc(
                                sentences[n_sentences].words[n_words].misc
                            )
                            if (
                                sentences[n_sentences].words[n_words].misc
                                and nes_encoded
                            ):
                                sentences[n_sentences].words[n_words].misc += "|"
                            if nes_encoded:
                                sentences[n_sentences].words[n_words].misc += "NE="
                            sentences[n_sentences].words[n_words].misc = sentences[
                                n_sentences
                            ].words[n_words].misc + "-".join(nes_encoded)
                            n_words += 1
            return "".join(output), n_nes_in_batches

        def conll_to_vertical(self, text, n_tokens_in_batch):
            output = []
            open_ids, open_forms, open_labels = [], [], []  # open entities on i-th line

            in_sentence = False

            for i, line in enumerate(text.split("\n")):
                if not line:  # end of sentence
                    if in_sentence:
                        for j in range(len(open_ids)):  # print all open entities
                            output.append((open_ids[j], open_labels[j], open_forms[j]))
                        open_ids, open_forms, open_labels = [], [], []
                        n_tokens_in_batch += 1
                    in_sentence = False
                else:
                    in_sentence = True
                    form, ne = line.split(SEP)
                    n_tokens_in_batch += 1
                    if ne == "O":  # all entities ended
                        for j in range(len(open_ids)):  # print all open entities
                            output.append((open_ids[j], open_labels[j], open_forms[j]))
                        open_ids, open_forms, open_labels = [], [], []
                    else:
                        labels = ne.split("|")
                        for j in range(len(labels)):  # for each label line
                            if j < len(open_ids):  # all open entities
                                # previous open entity ends here, close and replace with new entity instead
                                if (
                                    labels[j].startswith("B-")
                                    or open_labels[j] != labels[j][2:]
                                ):
                                    output.append(
                                        (open_ids[j], open_labels[j], open_forms[j])
                                    )
                                    open_ids[j] = [n_tokens_in_batch]
                                    open_forms[j] = form
                                # entity continues, append ids and forms
                                else:
                                    open_ids[j].append(n_tokens_in_batch)
                                    open_forms[j] += " " + form
                                open_labels[j] = labels[j][2:]
                            else:  # no running entities, new entity starts here, just append
                                open_ids.append([n_tokens_in_batch])
                                open_forms.append(form)
                                open_labels.append(labels[j][2:])
            output.sort(
                key=lambda ids_labels_forms: (
                    ids_labels_forms[0][0],
                    -ids_labels_forms[0][-1],
                )
            )
            output = "".join(
                [
                    ",".join(map(str, ids)) + SEP + label + SEP + forms + "\n"
                    for ids, label, forms in output
                ]
            )
            return output, n_tokens_in_batch

        @staticmethod
        def encode_entities(text):
            return (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        def conll_to_xml(self, text, udpipe_tokens):
            """Converts postprocessed (!) CoNLL output of the model.

            This method expects correct bracketing and the IOB2 format of the
            encoded named entities. Hence, postprocessing (model.postprocess)
            of the model output is important before calling this method.

            Rules for whitespaces around the <sentence>, <token> and <ne> XML
            elements:

            1. There are no whitespaces inside the <token> element. The <token>
            element only holds the token.
            2. Therefore it follows that all inter-token whitespaces are
            printed in between the <token> elements.
            3. There are no leading or trailing whitespaces inside the <ne>
            element, threfore the whitespaces before the first <token> and
            after the last <token> inside the <ne> element are printed
            before/after the <ne> element.
            4. There are no leading or trailing whitespaces inside the
            <sentence> element, therefore the whitespaces before the first
            <token> and after the last <token> are printed before/after the
            <sentence> element.
            """

            output = []
            open_labels = []
            in_sentence = False

            s, t = -1, 0  # indexes to udpipe sentences and tokens inside sentences
            delayed_spaces_after = ""
            for line in text.split("\n"):

                if not line:  # end of sentence
                    for i in range(len(open_labels)):  # close all open entities
                        output.append("</ne>")
                    open_labels = []

                    if in_sentence:
                        output.append("</sentence>")  # close sentence
                        in_sentence = False
                        output.append(delayed_spaces_after)
                        delayed_spaces_after = ""
                else:  # in sentence
                    if not in_sentence:  # sentence starts
                        s += 1
                        t = 0
                        output.append(udpipe_tokens[s][t].spaces_before)
                        output.append("<sentence>")
                        in_sentence = True

                    cols = line.split(SEP)
                    form = cols[0]
                    ne = cols[1] if len(cols) == 2 else "O"

                    # This will work for properly nested entities,
                    # hence model.postprocess is important before conll_to_xml.
                    opening_tags = []
                    if ne == "O":  # all entities ended
                        for i in range(len(open_labels)):  # close all open entities
                            output.append("</ne>")
                        open_labels = []
                    else:
                        labels = ne.split("|")
                        for i in range(len(labels)):
                            if i < len(open_labels):
                                if (
                                    labels[i].startswith("B-")
                                    or open_labels[i] != labels[i][2:]
                                ):
                                    # previous open entity ends here
                                    # -> close it and all open nested entities
                                    for _ in range(i, len(open_labels)):
                                        output.append("</ne>")
                                    open_labels = open_labels[:i]
                                    # open new entity
                                    opening_tags.append(
                                        '<ne type="'
                                        + self.encode_entities(labels[i][2:])
                                        + '">'
                                    )
                                    open_labels.append(labels[i][2:])
                            else:  # no running entities, new entity starts here, just append
                                opening_tags.append(
                                    '<ne type="'
                                    + self.encode_entities(labels[i][2:])
                                    + '">'
                                )
                                open_labels.append(labels[i][2:])

                    output.append(delayed_spaces_after)

                    if t > 0:
                        output.append(
                            self.encode_entities(udpipe_tokens[s][t].spaces_before)
                        )

                    output.append("".join(opening_tags))
                    output.append("<token>" + self.encode_entities(form) + "</token>")

                    delayed_spaces_after = udpipe_tokens[s][t].spaces_after

                    t += 1

            return "".join(output)

    def __init__(self, server_args):
        self.default_model = server_args.default_model
        self.models_by_names = {}  # model names and language variants
        self.models_by_paths = {}  # paths to initialized models
        self.canonical_names = []  # canonical model names list
        self.alias_to_canonical = {}  # resolve model alias names
        self.tagsets_by_names = {}  # model name to tagset

        for i in range(0, len(server_args.models), 4):
            names, path, tagset, acknowledgements = server_args.models[i : i + 4]
            names = names.split(":")
            names = [name.split("-") for name in names]
            names = [
                "-".join(parts[: None if not i else -i])
                for parts in names
                for i in range(len(parts))
            ]

            if path in self.models_by_paths:
                print(
                    'Model in path "{}" already exists, sharing it also for model "{}"'.format(
                        path, names[0]
                    ),
                    file=sys.stderr,
                    flush=True,
                )
                model = self.models_by_paths[path]
            else:
                print(
                    'Initializing new model "{}" from path "{}"'.format(names[0], path),
                    file=sys.stderr,
                    flush=True,
                )
                model = self.Model(path, names[0], acknowledgements, server_args)

            self.models_by_paths[path] = model
            self.canonical_names.append(names[0])
            for name in names:
                self.models_by_names.setdefault(name, model)
                self.tagsets_by_names.setdefault(name, tagset if tagset else None)
                self.alias_to_canonical.setdefault(name, names[0])

        # Check the default model exists
        assert self.default_model in self.models_by_names


class NameTag3Server(socketserver.ThreadingTCPServer):
    class NameTag3ServerRequestHandler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def respond(request, content_type, code=200, additional_headers={}):
            request.close_connection = True
            request.send_response(code)
            request.send_header("Connection", "close")
            request.send_header("Content-Type", content_type)
            request.send_header("Access-Control-Allow-Origin", "*")
            for key, value in additional_headers.items():
                request.send_header(key, value)
            request.end_headers()

        def respond_error(request, message, code=400):
            request.respond("text/plain", code)
            request.wfile.write(message.encode("utf-8"))

        def start_responding(
            request, url, output_param, model_name, model_acknowledgements, infclen
        ):
            if url.path.startswith("/weblicht"):
                request.respond("application/conllu")
            else:
                request.respond(
                    "application/json",
                    additional_headers={"X-Billing-Input-NFC-Len": str(infclen)},
                )
                request.wfile.write(
                    json.dumps(
                        collections.OrderedDict(
                            [
                                ("model", model_name),
                                (
                                    "acknowledgements",
                                    [
                                        "https://ufal.mff.cuni.cz/nametag/3#acknowledgements",
                                        model_acknowledgements,
                                    ],
                                ),
                                ("result", ""),
                            ]
                        ),
                        indent=1,
                    )[:-3].encode("utf-8")
                )
                if output_param == "conllu-ne":
                    request.wfile.write(
                        json.dumps(
                            "# generator = NameTag 3, https://lindat.mff.cuni.cz/services/nametag\n"
                            "# nametag_model = {}\n"
                            "# nametag_model_licence = CC BY-NC-SA\n".format(model_name)
                        )[1:-1].encode("utf-8")
                    )

        def do_GET(request):
            # Parse the URL
            params = {}
            try:
                request.path = request.path.encode("iso-8859-1").decode("utf-8")
                url = urllib.parse.urlparse(request.path)
                for name, value in urllib.parse.parse_qsl(
                    url.query, encoding="utf-8", keep_blank_values=True, errors="strict"
                ):
                    params[name] = value
            except:
                return request.respond_error("Cannot parse request URL.")

            # Parse the body of a POST request
            if request.command == "POST":
                if (
                    request.headers.get("Transfer-Encoding", "identity").lower()
                    != "identity"
                ):
                    return request.respond_error(
                        "Only 'identity' Transfer-Encoding of payload is supported for now."
                    )

                try:
                    content_length = int(request.headers["Content-Length"])
                except:
                    return request.respond_error(
                        "The Content-Length of payload is required."
                    )

                if content_length > request.server._server_args.max_request_size:
                    return request.respond_error("The payload size is too large.")

                # Content-Type
                if url.path.startswith("/weblicht"):
                    try:
                        params["data"] = request.rfile.read(content_length).decode(
                            "utf-8"
                        )
                    except:
                        return request.respond_error("Payload not in UTF-8.")
                    params["input"] = "conllu"
                    params["output"] = "conllu-ne"
                elif request.headers.get("Content-Type", "").startswith(
                    "multipart/form-data"
                ):
                    try:
                        parser = email.parser.BytesFeedParser()
                        parser.feed(
                            b"Content-Type: "
                            + request.headers["Content-Type"].encode("ascii")
                            + b"\r\n\r\n"
                        )
                        while content_length:
                            parser.feed(request.rfile.read(min(content_length, 4096)))
                            content_length -= min(content_length, 4096)
                        for part in parser.close().get_payload():
                            name = part.get_param("name", header="Content-Disposition")
                            if name:
                                params[name] = part.get_payload(decode=True).decode(
                                    "utf-8"
                                )
                    except:
                        return request.respond_error(
                            "Cannot parse the multipart/form-data payload."
                        )
                elif request.headers.get("Content-Type", "").startswith(
                    "application/x-www-form-urlencoded"
                ):
                    try:
                        for name, value in urllib.parse.parse_qsl(
                            request.rfile.read(content_length).decode("utf-8"),
                            encoding="utf-8",
                            keep_blank_values=True,
                            errors="strict",
                        ):
                            params[name] = value
                    except:
                        return request.respond_error(
                            "Cannot parse the application/x-www-form-urlencoded payload."
                        )
                else:
                    return request.respond_error(
                        "Unsupported payload Content-Type '{}'.".format(
                            request.headers.get("Content-Type", "<none>")
                        )
                    )

            # Handle /models
            if url.path == "/models":
                response = {
                    "models": {
                        name: ["tokenize", "recognize"]
                        for name in request.server._models.canonical_names
                    },
                    "default_model": request.server._models.default_model,
                }
                request.respond("application/json")
                request.wfile.write(json.dumps(response, indent=1).encode("utf-8"))

            # Handle /tokenize and /recognize
            elif url.path in ["/recognize", "/tokenize", "/weblicht/recognize"]:

                # Data
                if "data" not in params:
                    return request.respond_error("The parameter 'data' is required.")
                params["data"] = unicodedata.normalize("NFC", params["data"])

                # Model
                model_name = params.get("model", request.server._models.default_model)
                canonical_model_name = request.server._models.alias_to_canonical[
                    model_name
                ]
                if model_name not in request.server._models.models_by_names:
                    return request.respond_error(
                        "The requested model '{}' does not exist.".format(model_name)
                    )
                tagsets = request.server._models.tagsets_by_names[model_name]
                model = request.server._models.models_by_names[model_name]

                # Input
                input_param = (
                    "untokenized"
                    if url.path == "/tokenize"
                    else params.get("input", "untokenized")
                )
                if input_param not in ["untokenized", "vertical", "conllu"]:
                    return request.respond_error(
                        "The requested input '{}' does not exist.".format(input_param)
                    )

                # Output
                output_param = params.get("output", "xml")
                if output_param not in ["xml", "vertical"] + (
                    ["conll", "conllu-ne"]
                    if url.path in ["/recognize", "/weblicht/recognize"]
                    else []
                ):
                    return request.respond_error(
                        "The requested output '{}' does not exist.".format(output_param)
                    )

                # Sentences
                try:
                    # Convert the generator to a list to raise exceptions early
                    sentences = list(
                        model._udpipe_tokenizer.tokenize(params["data"], input_param)
                    )
                except:
                    return request.respond_error(
                        "Cannot parse the input in the '{}' format.".format(input_param)
                    )

                # Billing info
                infclen = sum(
                    sum(len(word.form) for word in sentence.words[1:])
                    for sentence in sentences
                )

                # Skip multiwords, get tokens from sentences
                input_tokens, token_list = (
                    [],
                    [],
                )  # [input_tokens], [sentences x tokens]
                for sentence in sentences:
                    token_list.append([])
                    word, multiword_token = 1, 0
                    while word < len(sentence.words):
                        if (
                            multiword_token < len(sentence.multiwordTokens)
                            and sentence.multiwordTokens[multiword_token].idFirst
                            == word
                        ):
                            token = sentence.multiwordTokens[multiword_token]
                            word = sentence.multiwordTokens[multiword_token].idLast + 1
                            multiword_token += 1
                        else:
                            token = sentence.words[word]
                            word += 1
                        input_tokens.append(token.form)
                        token_list[-1].append(
                            model._udpipe_tokenizer.Token(
                                token.form,
                                token.getSpacesBefore(),
                                token.getSpacesAfter(),
                            )
                        )
                    input_tokens.append("")

                # Generate responses in batches.
                started_responding = False
                try:

                    # Handle empty requests separately by generating empty output with valid format and headers.
                    if len(input_tokens) == 0:
                        request.start_responding(
                            url,
                            output_param,
                            canonical_model_name,
                            model.acknowledgements,
                            infclen,
                        )

                    # Tokenize without calling the NameTag 3 model.
                    elif url.path == "/tokenize":
                        for i in range(0, len(token_list), model.args.batch_size):
                            batch_output = []
                            for sentence in token_list[i : i + model.args.batch_size]:
                                batch_output.append(
                                    "\n".join(
                                        [token.token for token in sentence] + [""]
                                    )
                                )
                            batch_output = "\n".join(batch_output + [""])

                            if output_param == "xml":
                                batch_output = model.conll_to_xml(
                                    batch_output,
                                    token_list[i : i + model.args.batch_size],
                                )

                            if not started_responding:
                                # The first batch is ready, we commit to generate batch_output.
                                request.start_responding(
                                    url,
                                    output_param,
                                    canonical_model_name,
                                    model.acknowledgements,
                                    infclen,
                                )
                                started_responding = True

                            request.wfile.write(
                                json.dumps(batch_output, ensure_ascii=False)[
                                    1:-1
                                ].encode("utf-8")
                            )

                    # Recognize NEs by calling the NameTag 3 model.
                    elif url.path == "/recognize" or url.path == "/weblicht/recognize":

                        # Create NameTag3Collection with only one NameTag3Dataset.
                        test_collection = NameTag3DatasetCollection(
                            model.args,
                            tokenizer=model.hf_tokenizer,
                            text="\n".join(input_tokens),
                            train_collection=model._train_collection,
                            tagsets=tagsets,
                        )

                        # Call the NameTag 3 model.
                        (
                            n_tokens_in_batches,
                            n_nes_in_batches,
                            n_sentences_in_batches,
                        ) = (0, 1, 0)
                        for batch_output in model.yield_predicted_batches(
                            test_collection.datasets[-1]
                        ):

                            # Sentences and tokens processed in this batch
                            batch_sentences = sentences[
                                n_sentences_in_batches : n_sentences_in_batches
                                + len(batch_output)
                            ]
                            batch_udpipe_tokens = token_list[
                                n_sentences_in_batches : n_sentences_in_batches
                                + len(batch_output)
                            ]
                            n_sentences_in_batches += len(batch_output)

                            # Finalize the batch output string by joining the sentence strings.
                            batch_output = "".join(batch_output)

                            batch_output = model.postprocess(batch_output)
                            if output_param == "vertical":
                                batch_output, n_tokens_in_batches = (
                                    model.conll_to_vertical(
                                        batch_output, n_tokens_in_batches
                                    )
                                )
                            if output_param == "conllu-ne":
                                batch_output, n_nes_in_batches = model.conll_to_conllu(
                                    batch_output,
                                    batch_sentences,
                                    "conllu-ne",
                                    n_nes_in_batches,
                                )
                            if output_param == "xml":
                                batch_output = model.conll_to_xml(
                                    batch_output, batch_udpipe_tokens
                                )

                            if not started_responding:
                                # The first batch is ready, we commit to generate batch_output.
                                request.start_responding(
                                    url,
                                    output_param,
                                    canonical_model_name,
                                    model.acknowledgements,
                                    infclen,
                                )
                                started_responding = True

                            if url.path.startswith("/weblicht"):
                                request.wfile.write(batch_output.encode("utf-8"))
                            else:
                                request.wfile.write(
                                    json.dumps(batch_output, ensure_ascii=False)[
                                        1:-1
                                    ].encode("utf-8")
                                )

                    if not url.path.startswith("/weblicht"):
                        request.wfile.write(b'"\n}\n')

                except:
                    import traceback

                    traceback.print_exc(file=sys.stderr)
                    sys.stderr.flush()

                    if not started_responding:
                        request.respond_error(
                            "An internal error occurred during processing."
                        )
                    else:
                        if url.path.startswith("/weblicht"):
                            request.wfile.write(
                                b"\n\nAn internal error occurred during processing, producing incorrect CoNLL-U!"
                            )
                        else:
                            request.wfile.write(
                                b'",\n"An internal error occurred during processing, producing incorrect JSON!"'
                            )

            else:
                request.respond_error(
                    "No handler for the given URL '{}'".format(url.path), code=404
                )

        def do_POST(request):
            return request.do_GET()

    daemon_threads = False

    def __init__(self, server_args, models):
        super().__init__(("", server_args.port), self.NameTag3ServerRequestHandler)

        self._server_args = server_args
        self._models = models

    def server_bind(self):
        import socket

        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()

    def service_actions(self):
        if isinstance(getattr(self, "_threads", None), list):
            if len(self._threads) >= 1024:
                self._threads = [
                    thread for thread in self._threads if thread.is_alive()
                ]


if __name__ == "__main__":
    import signal
    import threading

    # Parse server arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=int, help="Port to use")
    parser.add_argument("default_model", type=str, help="Default model")
    parser.add_argument("models", type=str, nargs="+", help="Models to serve")
    parser.add_argument("--batch_size", default=32, type=int, help="Batch size")
    parser.add_argument("--logfile", default=None, type=str, help="Log path")
    parser.add_argument(
        "--max_labels_per_token", default=5, type=int, help="Maximum labels per token."
    )
    parser.add_argument(
        "--max_request_size", default=4096 * 1024, type=int, help="Maximum request size"
    )
    parser.add_argument("--threads", default=4, type=int, help="Threads to use")
    args = parser.parse_args()

    # Set threads
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(args.threads)
    torch.backends.cuda.matmul.allow_tf32 = True  # faster, and less memory

    # Log stderr to logfile if given
    if args.logfile is not None:
        sys.stderr = open(args.logfile, "a", encoding="utf-8")

    # Load the models
    models = Models(args)

    # Create the server
    server = NameTag3Server(args, models)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("Started NameTag 3 server on port {}.".format(args.port), file=sys.stderr)
    print(
        "To stop it gracefully, either send SIGINT (Ctrl+C) or SIGUSR1.",
        file=sys.stderr,
        flush=True,
    )

    # Wait until the server should be closed
    signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGINT, signal.SIGUSR1])
    signal.sigwait([signal.SIGINT, signal.SIGUSR1])
    print("Initiating shutdown of the NameTag 3 server.", file=sys.stderr, flush=True)
    server.shutdown()
    print(
        "Stopped handling new requests, processing all current ones.",
        file=sys.stderr,
        flush=True,
    )
    server.server_close()
    print("Finished shutdown of the NameTag 3 server.", file=sys.stderr, flush=True)
