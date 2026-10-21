"""no_test_weakening and tests_exercise_code on Kotlin (JUnit) tests.

Both counted only Python/JS forms, so on the Android app's tasks (2026-10-21)
a Kotlin test losing its assertEquals lines counted "0 removed", and a
changed .kt test file was "no changed test files".
"""

from __future__ import annotations

import subprocess

import pytest

from life_graph.services.verifiers import verifier_chain

TEST_PATH = "app/src/test/java/com/x/AddTest.kt"
ORIGINAL = """\
package com.x

import org.junit.Assert.assertEquals
import org.junit.Test

class AddTest {
    @Test
    fun adds() {
        assertEquals(3, add(1, 2))
        assertEquals(0, add(0, 0))
    }

    @Test
    fun addsNegatives() {
        assertEquals(-2, add(-1, -1))
    }
}
"""


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    test = tmp_path / TEST_PATH
    test.parent.mkdir(parents=True)
    test.write_text(ORIGINAL)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


async def _check(repo, name, instruction="Fix add"):
    (result,) = await verifier_chain.run_chain([name], repo, {"scope_instruction": instruction})
    return result


def _edit(repo, text, path=TEST_PATH):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


async def test_a_removed_kotlin_assertion_fails(repo):
    _edit(repo, ORIGINAL.replace("        assertEquals(0, add(0, 0))\n", ""))
    result = await _check(repo, "no_test_weakening")
    assert not result.passed and "1 fewer assertion(s)" in result.evidence["problems"]


async def test_a_removed_kotlin_test_fails(repo):
    start = ORIGINAL.index("    @Test\n    fun addsNegatives")
    _edit(repo, ORIGINAL[:start].rstrip() + "\n}\n")
    result = await _check(repo, "no_test_weakening")
    assert not result.passed and "1 fewer test(s)" in result.evidence["problems"]


async def test_ignore_is_a_new_skip(repo):
    _edit(repo, ORIGINAL.replace("    @Test\n    fun addsNegatives", "    @Ignore\n    @Test\n    fun addsNegatives"))
    result = await _check(repo, "no_test_weakening")
    assert not result.passed and any("skip" in p for p in result.evidence["problems"])


async def test_an_added_kotlin_test_passes_and_is_counted(repo):
    _edit(
        repo,
        ORIGINAL.replace(
            "    @Test\n    fun addsNegatives",
            "    @Test\n    fun addsZero() {\n        assertEquals(5, add(5, 0))\n    }\n\n"
            "    @Test\n    fun addsNegatives",
        ),
    )
    result = await _check(repo, "no_test_weakening")
    assert result.passed
    assert result.evidence["added"] == {"tests": 1, "assertions": 1}


async def test_a_kotlin_test_that_asserts_nothing_is_flagged(repo):
    _edit(
        repo,
        "package com.x\n\nimport org.junit.Test\n\nclass NewTest {\n"
        "    @Test\n    fun runs() {\n        add(1, 2)\n    }\n}\n",
        "app/src/test/java/com/x/NewTest.kt",
    )
    result = await _check(repo, "tests_exercise_code")
    assert not result.passed
    assert result.evidence["problems"] == {"app/src/test/java/com/x/NewTest.kt": ["asserts nothing"]}


async def test_a_kotlin_test_that_reads_the_source_is_flagged(repo):
    _edit(
        repo,
        "package com.x\n\nimport java.io.File\nimport org.junit.Assert.assertTrue\nimport org.junit.Test\n\n"
        "class NewTest {\n    @Test\n    fun mentionsAdd() {\n"
        '        assertTrue(File("app/src/main/java/com/x/Add.kt").readText().contains("fun add"))\n'
        "    }\n}\n",
        "app/src/test/java/com/x/NewTest.kt",
    )
    result = await _check(repo, "tests_exercise_code")
    assert not result.passed
    (smells,) = result.evidence["problems"].values()
    assert smells == ["reads a source file instead of running the code"]


async def test_a_real_kotlin_test_passes_tests_exercise_code(repo):
    _edit(repo, ORIGINAL.replace("assertEquals(0, add(0, 0))", "val e = assertThrows(Exception::class.java) { add(0, 0) }"))
    result = await _check(repo, "tests_exercise_code")
    assert result.passed and result.evidence["checked"] == [TEST_PATH]
