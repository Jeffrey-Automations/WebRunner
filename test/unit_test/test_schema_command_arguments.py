"""The action schema checks an action's arguments object against its command's signature."""
import glob
import inspect
import json
import re
import unittest
from pathlib import Path
from typing import Any, Callable  # noqa: F401  (named in the sample's string annotations)

from je_web_runner.utils.schema.action_schema import build_action_schema, schema_text
from je_web_runner.utils.schema.command_arguments import (
    NUMBER_TEXT_REF,
    PLACEHOLDER_REF,
    arguments_schema,
    command_argument_rules,
    value_schema,
)

try:
    import jsonschema
except ImportError:  # the package is not a dependency; the structural tests still run
    jsonschema = None

REPOSITORY = Path(__file__).resolve().parents[2]


def sample(url: str, timeout: float = 10, retries: int | None = None, tags: list[str] | None = None,
           options: dict | None = None, strict: bool = False, anything=None, callback: "Callable | None" = None,
           either: "str | dict[str, Any]" = "") -> None:
    """A command with one parameter of each kind the mapping knows, and two it does not."""


def open_ended(name: str, **extra) -> None:
    """A command that takes any other keyword."""


class TestArgumentsSchema(unittest.TestCase):

    def setUp(self):
        self.schema = arguments_schema(sample)
        self.properties = self.schema["properties"]

    def test_names_and_required(self):
        self.assertEqual(list(self.properties), ["url", "timeout", "retries", "tags", "options", "strict",
                                                 "anything", "callback", "either"])
        self.assertEqual(self.schema["required"], ["url"])
        self.assertFalse(self.schema["additionalProperties"])

    def test_string_needs_no_placeholder_alternative(self):
        self.assertEqual(self.properties["url"], {"type": "string"})
        self.assertEqual(self.properties["either"], {"type": ["string", "object"]})

    def test_numbers_are_loose_and_take_placeholders_and_number_text(self):
        self.assertEqual(self.properties["timeout"], {"anyOf": [{"type": "number"}, PLACEHOLDER_REF, NUMBER_TEXT_REF]})
        self.assertEqual(self.properties["retries"],
                         {"anyOf": [{"type": ["number", "null"]}, PLACEHOLDER_REF, NUMBER_TEXT_REF]})

    def test_containers_and_booleans(self):
        self.assertEqual(self.properties["tags"], {"anyOf": [{"type": ["array", "null"]}, PLACEHOLDER_REF]})
        self.assertEqual(self.properties["options"], {"anyOf": [{"type": ["object", "null"]}, PLACEHOLDER_REF]})
        self.assertEqual(self.properties["strict"], {"anyOf": [{"type": "boolean"}, PLACEHOLDER_REF]})

    def test_unknown_annotations_put_no_constraint(self):
        self.assertEqual(self.properties["anything"], {})
        self.assertEqual(self.properties["callback"], {})

    def test_annotations_that_are_objects_read_like_their_source(self):
        # A module with ``from __future__ import annotations`` carries text, one without carries objects.
        # Both must give the same schema on every Python version (3.14 names a union "Union").
        cases = {
            "str": str, "float": float, "bool": bool, "int | None": int | None,
            "list[str] | None": list[str] | None, "dict[str, Any]": dict[str, Any], "str | dict[str, Any]": str | dict,
        }
        for written, annotation in cases.items():
            with self.subTest(annotation=written):
                as_text = inspect.Parameter("x", inspect.Parameter.KEYWORD_ONLY, annotation=written)
                as_object = inspect.Parameter("x", inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
                self.assertEqual(value_schema(as_object), value_schema(as_text))
                self.assertNotEqual(value_schema(as_object), {})

    def test_keyword_catch_all_allows_other_names(self):
        schema = arguments_schema(open_ended)
        self.assertTrue(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["name"])

    def test_unreadable_signature_gives_none(self):
        self.assertIsNone(arguments_schema(42))


class TestSchemaForms(unittest.TestCase):

    def test_the_small_form_has_no_argument_rules(self):
        schema = build_action_schema(arguments=False)
        self.assertEqual(list(schema["definitions"]), ["action"])
        self.assertNotIn("allOf", schema["definitions"]["action"])
        self.assertLess(len(json.dumps(schema)), 100_000)

    def test_exported_text_is_the_same_schema_with_one_line_per_command(self):
        schema = build_action_schema()
        text = schema_text(schema)
        self.assertEqual(json.loads(text), schema)
        lines = text.splitlines()
        self.assertTrue(any(line.strip().startswith('"WR_to_url": {"type": "object"') for line in lines))
        self.assertLess(len(lines), 3 * len(schema["definitions"]["arguments"]) + 2500)


class TestRules(unittest.TestCase):

    def test_aliases_share_one_definition(self):
        definitions, rules, _ = command_argument_rules({"WR_b_alias": sample, "WR_a": sample, "WR_open": open_ended})
        self.assertEqual(sorted(definitions), ["WR_a", "WR_open"])
        by_ref = {rule["then"]["prefixItems"][1]["$ref"]: rule["if"]["prefixItems"][0]["pattern"] for rule in rules}
        self.assertEqual(by_ref, {"#/definitions/arguments/WR_a": "^(WR_a|WR_b_alias)$",
                                  "#/definitions/arguments/WR_open": "^(WR_open)$"})

    def test_rules_apply_to_the_keyword_form_only(self):
        _, rules, _ = command_argument_rules({"WR_a": sample})
        self.assertEqual(rules[0]["if"]["prefixItems"][1], {"type": "object"})
        self.assertEqual(rules[0]["if"]["minItems"], 2)

    def test_repeated_value_schemas_are_shared(self):
        definitions, _, values = command_argument_rules({"WR_a": sample})
        properties = definitions["WR_a"]["properties"]
        self.assertEqual(properties["timeout"], {"$ref": "#/definitions/values/number"})
        self.assertEqual(properties["retries"], {"$ref": "#/definitions/values/number_or_null"})
        self.assertEqual(properties["url"], {"type": "string"})
        self.assertEqual(values["number"], {"anyOf": [{"type": "number"}, PLACEHOLDER_REF, NUMBER_TEXT_REF]})
        self.assertEqual(set(values), {"number", "number_or_null", "array_or_null", "object_or_null", "boolean"})

    def test_every_registered_command_has_a_rule(self):
        schema = build_action_schema()
        action = schema["definitions"]["action"]
        patterns = [re.compile(rule["if"]["prefixItems"][0]["pattern"]) for rule in action["allOf"]]
        for name in action["prefixItems"][0]["enum"]:
            self.assertEqual(sum(1 for pattern in patterns if pattern.match(name)), 1, name)
        for rule in action["allOf"]:
            name = rule["then"]["prefixItems"][1]["$ref"].rsplit("/", 1)[-1]
            self.assertIn(name, schema["definitions"]["arguments"])


@unittest.skipIf(jsonschema is None, "jsonschema is not installed")
class TestValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = build_action_schema()
        jsonschema.Draft202012Validator.check_schema(cls.schema)
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_accepts_what_runs(self):
        for action in (
                ["WR_to_url", {"url": "https://example.test"}],
                ["WR_to_url", ["https://example.test"]],
                ["WR_set_var", {"name": "a", "value": "${b}"}],
                ["WR_wait_for_element", {"selector": "#a", "timeout": "${seconds}"}],
                ["WR_wait_for_element", {"selector": "#a", "timeout": "3"}],
                ["WR_quit_all"],
        ):
            with self.subTest(action=action):
                self.assertTrue(self.validator.is_valid([action]))

    def test_rejects_wrong_names_missing_and_wrong_types(self):
        for action in (
                ["WR_to_url", {"urll": "https://example.test"}],
                ["WR_to_url", {}],
                ["WR_wait_for_element", {"selector": "#a", "timeout": [3]}],
                ["WR_wait_for_element", {"selector": "#a", "timeout": "soon"}],
        ):
            with self.subTest(action=action):
                self.assertFalse(self.validator.is_valid([action]))

    def test_the_action_files_of_the_repository_stay_valid(self):
        loose = json.loads(json.dumps(self.schema))
        loose["definitions"]["action"].pop("allOf")
        without_arguments = jsonschema.Draft202012Validator(loose)
        for folder in ("examples", "test"):
            for path in glob.glob(str(REPOSITORY / folder / "**" / "*.json"), recursive=True):
                try:
                    document = json.loads(Path(path).read_text(encoding="utf-8"))
                except ValueError:
                    continue
                if without_arguments.is_valid(document):
                    with self.subTest(path=path):
                        self.assertTrue(self.validator.is_valid(document))


if __name__ == "__main__":
    unittest.main()
