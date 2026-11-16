"""
One CODEOWNERS file, three readers (test_owners_map, test_blame_owner, test_debt_dashboard): they agree.

``BEFORE`` records what each reader returned for this file before they shared one parser and one matcher,
as ``(test_blame_owner, test_debt_dashboard, test_owners_map)``; test_blame_owner drops the ``@``.
"""
import pytest

from je_web_runner.utils.test_blame_owner import owner as blame_owner
from je_web_runner.utils.test_debt_dashboard import debt
from je_web_runner.utils.test_owners_map import owners as owners_map

CODEOWNERS = """\
# comment
*                       @platform
*.md                    @docs
/test/unit/             @unit-team
docs/*                  @docs-team
/apps/github            @gh-team
test/**/auth_*.py       @auth   # trailing
/scripts/build.py       @org/build#1
"""

# path -> the owner GitHub gives it (the last matching rule wins)
EXPECTED = {
    "README.md": "@docs",
    "src/a.py": "@platform",
    "docs/guide/intro.md": "@docs",           # "docs/*" owns direct children only
    "docs/intro.md": "@docs-team",
    "docs/img/logo.png": "@platform",
    "test/unit/test_x.py": "@unit-team",      # "/test/unit/" is anchored at the root
    "apps/github/hook.py": "@gh-team",        # "/apps/github" names a directory
    "test/e2e/auth_login.py": "@auth",
    "test/auth_login.py": "@auth",            # "**/" also matches no directory at all
    "scripts/build.py": "@org/build#1",       # a "#" inside an owner is not a comment
}

BEFORE = {
    "README.md": ("docs", "@docs", "@docs"),
    "src/a.py": ("platform", "@platform", "@platform"),
    "docs/guide/intro.md": ("docs-team", "@docs", "@docs"),
    "docs/intro.md": ("docs-team", "@docs-team", "@docs-team"),
    "docs/img/logo.png": ("docs-team", "@platform", "@platform"),
    "test/unit/test_x.py": ("platform", "@platform", "@unit-team"),
    "apps/github/hook.py": ("platform", "@platform", "@platform"),
    "test/e2e/auth_login.py": ("auth", "@auth", "@auth"),
    "test/auth_login.py": ("platform", "@platform", "@platform"),
    "scripts/build.py": ("platform", "@org/build", "@org/build#1"),
}


def test_the_recorded_table_covers_every_path():
    assert set(BEFORE) == set(EXPECTED)


@pytest.mark.parametrize("path", sorted(EXPECTED))
def test_owners_map_gives_the_github_owner(path):
    assert owners_map.parse_codeowners(CODEOWNERS).lookup(path) == [EXPECTED[path]]


@pytest.mark.parametrize("path", sorted(EXPECTED))
def test_blame_owner_agrees(path):
    rules = blame_owner.parse_codeowners(CODEOWNERS)
    assert blame_owner.owners_from_codeowners(rules, path) == [EXPECTED[path].lstrip("@")]


@pytest.mark.parametrize("path", sorted(EXPECTED))
def test_debt_dashboard_agrees(path):
    assert debt.parse_codeowners(CODEOWNERS).owner_for(path) == EXPECTED[path]


def test_debt_dashboard_matches_a_windows_path():
    index = debt.parse_codeowners("* @platform\ntest/unit/ @unit-team\n")
    assert index.owner_for("C:\\repo\\test\\unit\\test_x.py") == "@unit-team"


def test_pattern_matches_is_the_shared_matcher():
    assert owners_map.pattern_matches("docs/*", "docs/intro.md")
    assert not owners_map.pattern_matches("docs/*", "docs/guide/intro.md")
    assert owners_map.pattern_matches("/apps/github", "apps/github/hook.py")
    assert not owners_map.pattern_matches("/apps/github", "apps/github2/hook.py")
    assert not owners_map.pattern_matches("/apps/github", "src/apps/github/hook.py")
    assert owners_map.pattern_matches("**/logs", "build/logs/out.txt")
    assert owners_map.pattern_matches("*.py", "a/b/c.py")
