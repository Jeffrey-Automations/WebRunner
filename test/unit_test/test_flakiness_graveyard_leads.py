"""flakiness_graveyard: an unreadable registry file is a FlakinessGraveyardError."""
import json

import pytest

from je_web_runner.utils.flakiness_graveyard.graveyard import FlakinessGraveyardError, load


def test_registry_that_is_not_json(tmp_path):
    path = tmp_path / "graveyard.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(FlakinessGraveyardError, match="not JSON"):
        load(str(path))


def test_registry_entry_with_an_unknown_status(tmp_path):
    path = tmp_path / "graveyard.json"
    path.write_text(json.dumps([{"test_name": "t", "status": "zombie"}]), encoding="utf-8")
    with pytest.raises(FlakinessGraveyardError, match="zombie"):
        load(str(path))
