from argparse import ArgumentParser, ArgumentTypeError
import json
import os
import re
import yaml

from robopipe_api.robopipe import app


def check_path(path: str):
    if not re.match(r"^.*\.(json|yml|yaml)$", path):
        raise ArgumentTypeError("Path must be either json ot yaml")

    return path


def export_openapi_spec(save_path: str | None = None):
    openapi = app.openapi()

    if save_path is not None:
        _, fmt = os.path.splitext(save_path)

        with open(save_path, "w") as f:
            if fmt == ".json":
                json.dump(openapi, f, indent=2)
            else:
                yaml.dump(openapi, f, sort_keys=False)
    else:
        print(json.dumps(openapi, indent=2))


if __name__ == "__main__":
    parser = ArgumentParser(prog="Save OpenAPI specification")
    parser.add_argument("-f", "--file", type=check_path)
    args = parser.parse_args()

    export_openapi_spec(args.file)
