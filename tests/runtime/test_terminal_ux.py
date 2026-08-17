from __future__ import annotations

from mary.runtime.application import (
    looks_like_terminal_command,
    terminal_command_guidance,
)


def test_terminal_commands_are_detected_without_execution():
    assert looks_like_terminal_command("Test-Path mary_write_test.txt")
    assert looks_like_terminal_command("Get-Content mary_write_test.txt")
    assert looks_like_terminal_command("Remove-Item mary_write_test.txt")
    assert looks_like_terminal_command("python -m pytest tests -q")
    assert looks_like_terminal_command("python main.py")
    assert looks_like_terminal_command("git status")


def test_natural_language_about_terminal_commands_still_reaches_mary():
    assert not looks_like_terminal_command("what does Test-Path do?")
    assert not looks_like_terminal_command("how do I use Get-Content?")
    assert not looks_like_terminal_command("explain python -m pytest tests -q")
    assert not looks_like_terminal_command("direct me to the memory manager")


def test_terminal_guidance_states_command_was_not_executed():
    message = terminal_command_guidance("Test-Path test.txt")
    assert "did not execute" in message
    assert "PowerShell prompt" in message
    assert "Test-Path test.txt" in message
