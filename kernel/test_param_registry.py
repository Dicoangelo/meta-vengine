"""US-101: Param Registry — Python Unit Tests"""

import json
import tempfile
from pathlib import Path

import pytest

from kernel.param_registry import ParamRegistry, ParamRegistryError, reset_registry

VALID_REGISTRY = {
    "version": "1.0.0",
    "banditEnabled": False,
    "parameters": [
        {"id": "w1", "configFile": "a.json", "jsonPath": "x.y", "value": 0.6, "min": 0.1, "max": 0.9, "learnRate": 0.02, "group": "test_group"},
        {"id": "w2", "configFile": "a.json", "jsonPath": "x.z", "value": 0.4, "min": 0.1, "max": 0.9, "learnRate": 0.02, "group": "test_group"},
        {"id": "ind1", "configFile": "b.json", "jsonPath": "y", "value": 5.0, "min": 1.0, "max": 10.0, "learnRate": 0.05, "group": "ind_group"},
    ],
    "groups": {
        "test_group": {"constraint": "sumMustEqual", "target": 1.0, "description": "Test sum group"},
        "ind_group": {"constraint": "independent", "description": "Test independent group"},
    },
}


@pytest.fixture(autouse=True)
def _reset():
    reset_registry()
    yield
    reset_registry()


def write_temp(data: dict) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestValidRegistry:
    def test_loads_cleanly(self):
        reg = ParamRegistry(write_temp(VALID_REGISTRY))
        assert len(reg.get_all_params()) == 3

    def test_get_param(self):
        reg = ParamRegistry(write_temp(VALID_REGISTRY))
        p = reg.get_param("w1")
        assert p["value"] == 0.6
        assert p["group"] == "test_group"

    def test_get_group(self):
        reg = ParamRegistry(write_temp(VALID_REGISTRY))
        group = reg.get_group("test_group")
        assert len(group) == 2

    def test_get_group_names(self):
        reg = ParamRegistry(write_temp(VALID_REGISTRY))
        names = reg.get_group_names()
        assert set(names) == {"test_group", "ind_group"}

    def test_bandit_disabled_by_default(self):
        reg = ParamRegistry(write_temp(VALID_REGISTRY))
        assert reg.is_bandit_enabled() is False

    def test_bandit_enabled(self):
        data = {**VALID_REGISTRY, "banditEnabled": True}
        reg = ParamRegistry(write_temp(data))
        assert reg.is_bandit_enabled() is True


class TestMalformedRegistry:
    def test_missing_parameters(self):
        with pytest.raises(ParamRegistryError, match="parameters"):
            ParamRegistry(write_temp({"groups": {}}))

    def test_missing_groups(self):
        with pytest.raises(ParamRegistryError, match="groups"):
            ParamRegistry(write_temp({"parameters": []}))

    def test_missing_required_field(self):
        data = {**VALID_REGISTRY, "parameters": [{"id": "x"}]}
        with pytest.raises(ParamRegistryError, match="missing required field"):
            ParamRegistry(write_temp(data))

    def test_value_out_of_bounds(self):
        data = {
            **VALID_REGISTRY,
            "parameters": [
                {"id": "oob", "configFile": "a.json", "jsonPath": "x", "value": 2.0, "min": 0.0, "max": 1.0, "learnRate": 0.02, "group": "ind_group"}
            ],
            "groups": {"ind_group": {"constraint": "independent"}},
        }
        with pytest.raises(ParamRegistryError, match="out of bounds"):
            ParamRegistry(write_temp(data))

    def test_invalid_learn_rate(self):
        data = {
            **VALID_REGISTRY,
            "parameters": [
                {"id": "lr", "configFile": "a.json", "jsonPath": "x", "value": 0.5, "min": 0.0, "max": 1.0, "learnRate": 0, "group": "ind_group"}
            ],
            "groups": {"ind_group": {"constraint": "independent"}},
        }
        with pytest.raises(ParamRegistryError, match="learnRate"):
            ParamRegistry(write_temp(data))

    def test_malformed_json(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("{bad json!!!")
        f.close()
        with pytest.raises(ParamRegistryError, match="Malformed JSON"):
            ParamRegistry(Path(f.name))

    def test_nonexistent_file(self):
        with pytest.raises(ParamRegistryError, match="Cannot read"):
            ParamRegistry(Path("/tmp/does-not-exist-12345.json"))

    def test_unknown_param(self):
        reg = ParamRegistry(write_temp(VALID_REGISTRY))
        with pytest.raises(ParamRegistryError, match="Unknown parameter"):
            reg.get_param("nonexistent")


class TestConstraints:
    def test_sum_constraint_violation(self):
        data = {
            **VALID_REGISTRY,
            "parameters": [
                {"id": "w1", "configFile": "a.json", "jsonPath": "x", "value": 0.3, "min": 0.1, "max": 0.9, "learnRate": 0.02, "group": "test_group"},
                {"id": "w2", "configFile": "a.json", "jsonPath": "y", "value": 0.3, "min": 0.1, "max": 0.9, "learnRate": 0.02, "group": "test_group"},
            ],
            "groups": {"test_group": {"constraint": "sumMustEqual", "target": 1.0}},
        }
        with pytest.raises(ParamRegistryError, match="sum constraint violated"):
            ParamRegistry(write_temp(data))


class TestRealRegistry:
    def test_real_learnable_params_loads(self):
        real_path = Path(__file__).parent.parent / "config" / "learnable-params.json"
        reg = ParamRegistry(real_path)
        assert len(reg.get_all_params()) == 19
        assert len(reg.get_group_names()) == 5
        assert reg.is_bandit_enabled() is False
