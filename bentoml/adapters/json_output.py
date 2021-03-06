# Copyright 2019 Atalaya Tech, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Iterable
import json

import numpy as np
import argparse

from bentoml.marshal.utils import SimpleResponse, SimpleRequest
from bentoml.adapters.base_output import BaseOutputAdapter


class NumpyJsonEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """

    def default(self, o):  # pylint: disable=method-hidden
        if isinstance(o, np.generic):
            return o.item()

        if isinstance(o, np.ndarray):
            return o.tolist()

        return json.JSONEncoder.default(self, o)


def jsonize(result):
    try:
        return json.dumps(result, cls=NumpyJsonEncoder)
    except (TypeError, OverflowError):
        # when result is not JSON serializable
        return json.dumps({"result": str(result)})


class JsonSerializableOutput(BaseOutputAdapter):
    """
    Converts result of user defined API function into specific output.

    Args:
        cors (str): The value of the Access-Control-Allow-Origin header set in the
            AWS Lambda response object. Default is "*". If set to None,
            the header will not be set.
    """

    def to_batch_response(
        self,
        result_conc,
        slices=None,
        fallbacks=None,
        requests: Iterable[SimpleRequest] = None,
    ) -> Iterable[SimpleResponse]:
        # TODO(bojiang): header content_type

        if slices is None:
            slices = [i for i, _ in enumerate(result_conc)]
        if fallbacks is None:
            fallbacks = [None] * len(slices)

        responses = [None] * len(slices)

        for i, (s, f) in enumerate(zip(slices, fallbacks)):
            if s is None:
                responses[i] = f
                continue

            result = result_conc[s]
            try:
                json_output = jsonize(result)
                responses[i] = SimpleResponse(
                    200, (("Content-Type", "application/json"),), json_output
                )
            except AssertionError as e:
                responses[i] = SimpleResponse(400, None, str(e))
            except Exception as e:  # pylint: disable=broad-except
                responses[i] = SimpleResponse(500, None, str(e))
        return responses

    def to_cli(self, result, args):
        """Handles an CLI command call, convert CLI arguments into
        corresponding data format that user API function is expecting, and
        prints the API function result to console output

        :param args: CLI arguments
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("-o", "--output", default="str", choices=["str", "json"])
        parsed_args = parser.parse_args(args)

        if parsed_args.output == 'json':
            result = jsonize(result)
        else:
            result = str(result)
        print(result)

    def to_aws_lambda_event(self, result, event):

        result = jsonize(result)

        # Allow disabling CORS by setting it to None
        if self.cors:
            return {
                "statusCode": 200,
                "body": result,
                "headers": {"Access-Control-Allow-Origin": self.cors},
            }

        return {"statusCode": 200, "body": result}
