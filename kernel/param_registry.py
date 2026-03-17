"""
US-101: Learnable Weight Schema — Unified Parameter Registry (Python Loader)

Loads config/learnable-params.json and validates all group constraints.
Provides get_param(), get_group(), and get_all_params() for downstream consumers.
"""

import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).parent.parent / "config" / "learnable-params.json"


class ParamRegistryError(Exception):
    pass


class ParamRegistry:
    def __init__(self, registry_path: str | Path | None = None):
        self.registry_path = Path(registry_path) if registry_path else REGISTRY_PATH
        self.params: dict[str, dict[str, Any]] = {}
        self.groups: dict[str, dict[str, Any]] = {}
        self.bandit_enabled: bool = False
        self._load()

    def _load(self) -> None:
        try:
            raw = self.registry_path.read_text()
        except FileNotFoundError:
            raise ParamRegistryError(f"Cannot read {self.registry_path}")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ParamRegistryError(f"Malformed JSON in {self.registry_path}: {e}")

        if not isinstance(data.get("parameters"), list):
            raise ParamRegistryError('Missing "parameters" array')
        if not isinstance(data.get("groups"), dict):
            raise ParamRegistryError('Missing "groups" object')

        self.bandit_enabled = data.get("banditEnabled", False) is True
        self.groups = data["groups"]

        for p in data["parameters"]:
            self._validate_param(p)
            self.params[p["id"]] = dict(p)

        self._validate_constraints()

    def _validate_param(self, p: dict) -> None:
        required = ["id", "configFile", "jsonPath", "value", "min", "max", "learnRate", "group"]
        for field in required:
            if field not in p or p[field] is None:
                raise ParamRegistryError(
                    f'Parameter missing required field "{field}": {json.dumps(p)}'
                )

        if not all(isinstance(p[k], (int, float)) for k in ("value", "min", "max")):
            raise ParamRegistryError(f'value/min/max must be numbers for "{p["id"]}"')

        if p["value"] < p["min"] or p["value"] > p["max"]:
            raise ParamRegistryError(
                f'Value {p["value"]} out of bounds [{p["min"]}, {p["max"]}] for "{p["id"]}"'
            )

        # Integer constraint validation
        if p.get("integerOnly") and not isinstance(p["value"], int):
            # Allow float values that are whole numbers (e.g. 5.0)
            if not (isinstance(p["value"], float) and p["value"] == int(p["value"])):
                raise ParamRegistryError(
                    f'Value {p["value"]} must be integer for "{p["id"]}"'
                )

        if not (0 < p["learnRate"] <= 1):
            raise ParamRegistryError(f'learnRate must be in (0, 1] for "{p["id"]}"')

    def _validate_constraints(self) -> None:
        for group_name, group_def in self.groups.items():
            members = self.get_group(group_name)

            if group_def.get("constraint") == "sumMustEqual":
                total = sum(p["value"] for p in members)
                target = group_def["target"]
                if abs(total - target) > 0.01:
                    raise ParamRegistryError(
                        f'Group "{group_name}" sum constraint violated: '
                        f"sum={total:.4f}, target={target}"
                    )

            if group_def.get("constraint") == "monotonic":
                values = sorted(p["value"] for p in members)
                if group_def.get("direction") == "ascending":
                    for i in range(1, len(values)):
                        if values[i] < values[i - 1]:
                            raise ParamRegistryError(
                                f'Group "{group_name}" monotonic ascending constraint violated'
                            )

    def get_param(self, param_id: str) -> dict[str, Any]:
        if param_id not in self.params:
            raise ParamRegistryError(f'Unknown parameter "{param_id}"')
        return dict(self.params[param_id])

    def get_group(self, group_name: str) -> list[dict[str, Any]]:
        return [dict(p) for p in self.params.values() if p["group"] == group_name]

    def get_all_params(self) -> list[dict[str, Any]]:
        return [dict(p) for p in self.params.values()]

    def get_group_names(self) -> list[str]:
        return list(self.groups.keys())

    def get_group_constraint(self, group_name: str) -> dict[str, Any] | None:
        return self.groups.get(group_name)

    def is_bandit_enabled(self) -> bool:
        return self.bandit_enabled

    def to_weight_map(self, group_name: str) -> dict[str, float]:
        members = self.get_group(group_name)
        result = {}
        for p in members:
            key = p["id"].split("_", 1)[-1] if "_" in p["id"] else p["id"]
            # Strip group prefix (e.g. "graph_entropy_weight" -> "entropy_weight")
            prefix = group_name + "_"
            if key.startswith(prefix.split("_", 1)[-1]):
                key = key[len(prefix.split("_", 1)[-1]):]
                key = key.lstrip("_")
            result[key] = p["value"]
        return result


_instance: ParamRegistry | None = None


def get_registry(registry_path: str | Path | None = None) -> ParamRegistry:
    global _instance
    if _instance is None:
        _instance = ParamRegistry(registry_path)
    return _instance


def reset_registry() -> None:
    global _instance
    _instance = None
