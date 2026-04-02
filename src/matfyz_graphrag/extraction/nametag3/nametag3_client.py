#!/usr/bin/env python3

# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University in Prague, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""NameTag 3 REST API client.

This is a simple script for accessing NameTag 3 webservice.

The script only requires basic Python and does not need any additional
installed packages or downloading the trained models.

By default, the script will call the NameTag 3 server. Do not send personal or
private data unless you are authorized and comfortable with it being processed
by NameTag 3.

Example Usage:

Get this script either by cloning the entire NameTag 3 repository:

git clone https://github.com/ufal/nametag3

or by simply downloading just this script specifically from the NameTag
3 repository by opening

https://github.com/ufal/nametag3/blob/main/nametag3_client.py

and hitting the download button ("Download raw file").

Save your text in a plaintext file, see an example in examples/cs_input.txt.
At the command line, type the following command:

./nametag3_client.py examples/cs_input.txt

The output will be printed to the standard output. To redirect the output
into a file, you can type:

./nametag3_client.py examples/cs_input.txt > output_file.xml

Or you can specify the output filename:

./nametag3_client.py examples/cs_input.txt --outfile=output_file.xml

Additionally, you can specify the language of your data or the exact required
model for your data. The language options are `arabic`, `chinese`, `croatian`,
`czech`, `danish`, `dutch`, `english`, `german`, `maghrebi`,
`norwegian_bokmaal`, `norwegian_nynorsk`, `portuguese`, `serbian`, `slovak`,
`spanish`, `swedish`, and `ukrainian`.

./nametag3_client.py examples/en_input.txt --model=english > output_file.xml

The list of available models can be obtained by:

./nametag3_client.py --list_models

E.g.:

./nametag3_client.py examples/cs_input.txt --model=nametag3-czech-cnec2.0-240830

For other available input and output formats, as well as other options, see the
commandlind-line arguments below.
"""

import argparse
import json
import os
import random
import sys
import urllib.error
import urllib.request


def perform_request(server, method, params={}):
    if not params:
        request_headers, request_data = {}, None
    else:
        boundary = "{:x}".format(random.getrandbits(50 * 4))
        request_headers = {
            "Content-Type": 'multipart/form-data; boundary="{}"'.format(boundary)
        }
        request_data = []
        for name, value in params.items():
            request_data.extend(
                [
                    "--" + boundary,
                    'Content-Disposition: form-data; name="{}"'.format(name),
                    "Content-Transfer-Encoding: 8bit",
                    "Content-Type: text/plain; charset=utf-8",
                    "",
                    value,
                ]
            )
        request_data.extend(["--" + boundary + "--", ""])
        request_data = "\r\n".join(request_data).encode("utf-8")

    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                url="{}/{}".format(server, method),
                headers=request_headers,
                data=request_data,
            )
        ) as request:
            return json.loads(request.read())
    except urllib.error.HTTPError as e:
        print(
            "An exception was raised during NameTag 3 'recognize' REST request.\n"
            "The service returned the following error:\n"
            "  {}".format(e.fp.read().decode("utf-8")),
            file=sys.stderr,
        )
        raise
    except json.JSONDecodeError as e:
        print(
            "Cannot parse the JSON response of NameTag 3 'recognize' REST request.\n"
            "  {}".format(e.msg),
            file=sys.stderr,
        )
        raise


def list_models(args):
    response = perform_request(args.service, "models")
    if "models" in response:
        for model in response["models"]:
            print(model)
    if "default_model" in response:
        print("Default model:", response["default_model"])


def recognize(args, data):
    data = {
        "input": args.input,
        "output": args.output,
        "data": data,
    }
    if args.model is not None:
        data["model"] = args.model

    response = perform_request(args.service, "recognize", data)
    if "model" not in response or "result" not in response:
        raise ValueError(
            "Cannot parse the NameTag 3 'recognize' REST request response."
        )

    print(
        "NameTag 3 generated an output using the model '{}'.".format(response["model"]),
        file=sys.stderr,
    )
    print(
        "Please respect the model licence (CC BY-NC-SA unless stated otherwise).",
        file=sys.stderr,
    )

    return response["result"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Most of the options are passed directly to the service. For documentation, "
            "see https://lindat.mff.cuni.cz/services/udpipe/api-reference.php ."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=str,
        help="Optional input files; stdin if not specified.",
    )
    parser.add_argument(
        "--list_models",
        default=False,
        action="store_true",
        help="List available models",
    )
    parser.add_argument("--input", default="untokenized", type=str, help="Input format")
    parser.add_argument("--model", default=None, type=str, help="Model to use")
    parser.add_argument("--output", default="xml", type=str, help="Output format")
    parser.add_argument(
        "--outfile",
        default=None,
        type=str,
        help="Output path template; use {} as basename",
    )
    parser.add_argument(
        "--service",
        default="https://lindat.mff.cuni.cz/services/nametag/api",
        type=str,
        help="Service URL",
    )
    args = parser.parse_args()

    if args.list_models:
        list_models(args)
    else:
        outfile = None  # No output file opened.

        for input_path in args.inputs or [sys.stdin]:
            # Use stdin if no inputs are specified
            if input_path != sys.stdin:
                with open(
                    input_path, "r", encoding="utf-8-sig", newline=""
                ) as input_file:
                    data = input_file.read()
            else:
                data = sys.stdin.read()

            if args.outfile and not outfile:
                outfile = args.outfile.replace(
                    "{}",
                    (
                        os.path.splitext(os.path.basename(input_path))[0]
                        if input_path != sys.stdin
                        else "{}"
                    ),
                )
                outfile = open(outfile, "w", encoding="utf-8")

            (outfile or sys.stdout).write(recognize(args, data))

            if args.outfile and "{}" in args.outfile:
                outfile.close()
                outfile = None

        if outfile:
            outfile.close()
