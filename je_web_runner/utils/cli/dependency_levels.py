"""
依相依層級分批執行
Running files that declare ``meta.depends_on`` in parallel: the files are grouped into levels, where every
file of a level depends only on files of earlier levels, and each level is handed to the pool as one batch.
A file whose dependency failed (or was itself skipped) is not run.
"""
from __future__ import annotations

from typing import Callable, Mapping

from je_web_runner.utils.test_filter.dependency import DependencyError

RunBatch = Callable[[list[str]], Mapping[str, bool]]
Skipped = Callable[[str], None]


def dependency_levels(graph: Mapping[str, list[str]]) -> list[list[str]]:
    """
    The files of ``graph`` (file -> the files it depends on) as levels, each in the graph's own order.

    :raises DependencyError: when the dependencies form a cycle.
    """
    remaining = {node: [dep for dep in deps if dep in graph] for node, deps in graph.items()}
    levels: list[list[str]] = []
    done: set[str] = set()
    while remaining:
        level = [node for node, deps in remaining.items() if all(dep in done for dep in deps)]
        if not level:
            raise DependencyError("dependency cycle detected; cannot order tests")
        levels.append(level)
        done.update(level)
        for node in level:
            del remaining[node]
    return levels


def run_in_levels(graph: Mapping[str, list[str]], run_batch: RunBatch, skipped: Skipped,
                  fail_fast: bool = False) -> dict[str, bool]:
    """
    Run every level of ``graph`` through ``run_batch`` (files -> passed per file) and return passed per
    file. A file with a failed dependency is reported to ``skipped`` and counts as not passed. With
    ``fail_fast`` nothing after the first level that had a failure is run.
    """
    outcome: dict[str, bool] = {}
    for level in dependency_levels(graph):
        runnable = []
        for path in level:
            if all(outcome.get(dep, True) for dep in graph.get(path, [])):
                runnable.append(path)
            else:
                outcome[path] = False
                skipped(path)
        outcome.update(run_batch(runnable) if runnable else {})
        if fail_fast and not all(outcome.get(path, True) for path in level):
            break
    return outcome
