from mary.personality.banter import build_banter_brief, score_banter_candidate


def test_explicit_roast_builds_bounded_specific_angles():
    brief = build_banter_brief(
        "Roast me. I said I never miss and immediately whiffed the easiest shot in the game lol.",
        recent_conversation=[
            {
                "role": "user",
                "content": "Yesterday I called that tutorial boss free XP and got folded twice.",
            }
        ],
        familiarity="familiar",
        drive="react",
        playfulness=0.9,
        allow_teasing=True,
    )

    assert brief.active is True
    assert brief.intensity >= 0.8
    assert brief.target == "game_or_situation"
    assert brief.callback_scope == "session_only"
    assert brief.callback_cue.startswith("Yesterday I called")
    techniques = [item.technique for item in brief.candidate_angles]
    assert techniques[0] == "callback"
    assert "dry_reversal" in techniques
    assert len(techniques) <= 3


def test_serious_character_context_suppresses_banter_even_when_invited():
    brief = build_banter_brief(
        "Roast me lol, I'm grieving and trying not to think about the funeral.",
        familiarity="familiar",
        drive="tease",
        playfulness=1.0,
        allow_teasing=True,
        active_patterns=["grief_or_hurt"],
    )

    assert brief.active is False
    assert brief.intensity == 0.0
    assert brief.target == "none"
    assert brief.candidate_angles == ()
    assert "suppresses" in brief.rationale


def test_callback_filter_does_not_turn_sensitive_recent_context_into_a_bit():
    brief = build_banter_brief(
        "Bro this game is robbing me lol.",
        recent_conversation=[
            {"role": "user", "content": "I was at the hospital talking about a medical diagnosis."},
        ],
        familiarity="familiar",
        playfulness=0.9,
        allow_teasing=True,
    )

    assert brief.active is True
    assert brief.callback_cue == ""
    assert brief.callback_scope == "none"
    assert "callback" not in [item.technique for item in brief.candidate_angles]


def test_no_specific_opening_means_no_forced_sass():
    brief = build_banter_brief(
        "Can you explain how the save system works?",
        familiarity="familiar",
        playfulness=0.95,
        allow_teasing=True,
    )

    assert brief.active is False
    assert "natural conversation wins" in brief.rationale


def test_specific_compact_line_scores_above_generic_insult():
    brief = build_banter_brief(
        "Roast me. I called the tutorial boss free XP and lost twice.",
        recent_conversation=[
            {"role": "user", "content": "I called that tutorial boss free XP before the first round."}
        ],
        familiarity="familiar",
        playfulness=0.9,
        allow_teasing=True,
    )

    specific = score_banter_candidate(
        "Free XP has apparently started collecting payments.",
        brief=brief,
        current_input="I called the tutorial boss free XP and lost twice.",
    )
    generic = score_banter_candidate(
        "You suck, idiot.",
        brief=brief,
        current_input="I called the tutorial boss free XP and lost twice.",
    )

    assert specific.total > generic.total
    assert generic.genericness_penalty == 1.0
    assert specific.brevity == 1.0


def test_repeated_line_is_penalized():
    brief = build_banter_brief(
        "Lmao this controller hates me.",
        familiarity="familiar",
        playfulness=0.9,
        allow_teasing=True,
    )
    line = "The controller has filed a formal complaint."

    fresh = score_banter_candidate(line, brief=brief, current_input="This controller hates me.")
    repeated = score_banter_candidate(
        line,
        brief=brief,
        current_input="This controller hates me.",
        recent_mary_lines=[line],
    )

    assert repeated.repetition_penalty == 1.0
    assert repeated.total < fresh.total
