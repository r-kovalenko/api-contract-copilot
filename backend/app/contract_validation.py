"""Offline OpenAPI parsing/validation, executed in a bounded child process."""

import json
import math
import re
import sys
from typing import Any

import yaml
from jsonschema_path import SchemaPath
from openapi_spec_validator import (
    OpenAPIV30SpecValidator,
    OpenAPIV31SpecValidator,
    OpenAPIV32SpecValidator,
)
from yaml.events import AliasEvent

MAX_BYTES = 1024 * 1024
MAX_DEPTH = 40
MAX_NODES = 20000


class InvalidContract(ValueError):
    def __init__(self, code: str, message: str, path: list | None = None):
        super().__init__(message)
        self.detail = {"code": code, "message": message, "path": path or []}


def reject(code: str, message: str) -> None:
    raise InvalidContract(code, message)


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if not isinstance(key, str):
            reject("invalid_key", "Object keys must be strings; quote YAML response codes.")
        if key in result:
            reject("duplicate_key", "Duplicate object keys are not allowed.")
        result[key] = value
    return result


class BoundedLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.depth = 0
        self.nodes = 0

    def compose_node(self, parent, index):
        if self.check_event(AliasEvent):
            reject("yaml_alias", "YAML aliases are not supported; inline the referenced values.")
        self.depth += 1
        self.nodes += 1
        if self.depth > MAX_DEPTH or self.nodes > MAX_NODES:
            reject("complexity_limit", "Contract exceeds the depth or node limit.")
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            reject("invalid_yaml", "Expected a YAML mapping.")
        return unique_object(
            [
                (self.construct_object(key, deep=deep), self.construct_object(value, deep=deep))
                for key, value in node.value
            ]
        )


def inspect_tree(spec: dict) -> None:
    stack = [(spec, 0)]
    count = 0
    references = []
    dialects = {
        "https://json-schema.org/draft/2020-12/schema",
        "https://spec.openapis.org/oas/3.1/dialect/base",
        "https://spec.openapis.org/oas/3.2/dialect/base",
    }
    while stack:
        value, depth = stack.pop()
        count += 1
        if depth > MAX_DEPTH or count > MAX_NODES:
            reject("complexity_limit", "Contract exceeds 40 nesting levels or 20,000 nodes.")
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"$id", "$dynamicRef", "$recursiveRef"}:
                    reject(
                        "unsupported_reference",
                        "Schema IDs and dynamic references are unsupported.",
                    )
                if key in {"$schema", "jsonSchemaDialect"} and (
                    not isinstance(item, str) or item not in dialects
                ):
                    reject("unsupported_dialect", "Use the default OpenAPI JSON Schema dialect.")
                if key == "$ref":
                    if not isinstance(item, str) or not item.startswith("#/"):
                        reject(
                            "external_reference",
                            "Only local #/ JSON Pointer references are allowed.",
                        )
                    references.append(item)
                stack.extend([(key, depth + 1), (item, depth + 1)])
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            if "\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                reject("invalid_text", "Strings must be valid Unicode without null characters.")
        elif isinstance(value, float):
            if not math.isfinite(value):
                reject("invalid_number", "Non-finite numbers are not allowed.")
        elif value is not None and type(value) not in {bool, int}:
            reject(
                "invalid_type", "Use JSON-compatible values; quote YAML dates and special scalars."
            )
    for ref in references:
        target: Any = spec
        try:
            for token in ref[2:].split("/"):
                if re.search(r"~(?![01])", token) or "%" in token:
                    raise ValueError
                token = token.replace("~1", "/").replace("~0", "~")
                if isinstance(target, list):
                    if not re.fullmatch(r"0|[1-9][0-9]*", token):
                        raise ValueError
                    target = target[int(token)]
                else:
                    target = target[token]
        except (KeyError, IndexError, TypeError, ValueError):
            reject("unresolved_reference", "A local JSON Pointer reference does not resolve.")


def parse_contract(raw: bytes, media_type: str) -> dict:
    if not raw or len(raw) > MAX_BYTES:
        reject("size_limit", "Provide a nonempty contract of at most 1 MiB.")
    try:
        text = raw.decode("utf-8-sig")
        if media_type == "application/json":
            spec = json.loads(text, object_pairs_hook=unique_object)
        else:
            loader = BoundedLoader(text)
            try:
                spec = loader.get_single_data()
            finally:
                loader.dispose()
    except (UnicodeError, json.JSONDecodeError, yaml.YAMLError, RecursionError):
        reject("invalid_document", "Provide one valid UTF-8 JSON or safe YAML document.")
    if not isinstance(spec, dict):
        reject("invalid_document", "The contract root must be an object.")
    inspect_tree(spec)
    version = spec.get("openapi")
    if not isinstance(version, str) or not re.fullmatch(r"3\.[012]\.\d{1,3}", version):
        reject("unsupported_openapi", "Supported OpenAPI versions are 3.0.x, 3.1.x and 3.2.x.")
    validator = {
        "0": OpenAPIV30SpecValidator,
        "1": OpenAPIV31SpecValidator,
        "2": OpenAPIV32SpecValidator,
    }[version.split(".")[1]]
    # No HTTP, file, or fallback handlers: validation must never fetch uploaded references.
    error = next(validator(SchemaPath.from_dict(spec, handlers={})).iter_errors(), None)
    if error is not None:
        path = [str(part)[:100] for part in error.absolute_path]
        message = f"OpenAPI validation failed ({error.validator})."
        if error.validator == "required" and isinstance(error.instance, dict):
            missing = [name for name in error.validator_value if name not in error.instance]
            message = "Missing required OpenAPI fields: " + ", ".join(missing[:10]) + "."
        raise InvalidContract("invalid_openapi", message, path)
    return spec


def main() -> None:
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    try:
        spec = parse_contract(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1])
        result = {"specification": spec}
    except InvalidContract as exc:
        result = {"error": exc.detail}
    except (ValueError, TypeError, RecursionError, KeyError, OverflowError):
        result = {
            "error": {
                "code": "invalid_openapi",
                "message": "Contract validation failed.",
                "path": [],
            }
        }
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
