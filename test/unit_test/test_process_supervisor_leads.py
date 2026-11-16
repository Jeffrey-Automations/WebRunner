"""process_supervisor: the tasklist CSV is read as CSV, so a comma inside a quoted field does not lose a row."""
from je_web_runner.utils.process_supervisor import supervisor

TASKLIST_CSV = (
    '"System Idle Process","0","Services","0","8 K"\n'
    '"chromedriver.exe","4321","Console","1","12,345 K"\n'
    '"report, final.exe","5150","Console","1","2,048 K"\n'
)


def test_tasklist_row_with_a_comma_in_the_image_name_is_kept(monkeypatch):
    monkeypatch.setattr(supervisor.subprocess, "check_output", lambda *args, **kwargs: TASKLIST_CSV)
    listed = {finding.pid: finding.name for finding in supervisor._tasklist_windows_lister()}
    assert listed == {0: "System Idle Process", 4321: "chromedriver.exe", 5150: "report, final.exe"}
