from mary.creative import (
    CreativeReference,
    ProductionFormat,
    Shot,
    build_production_plan,
    capability_jobs,
)


def _unit(text="Mary turns toward the window", dialogue=""):
    return Shot("u1", 3.0, "scene", text, dialogue=dialogue, source_refs=("drawing://mary-window",))


def test_book_pipeline_emits_text_and_document_jobs_without_pretending_to_render_video():
    plan = build_production_plan(
        title="Unbeknownst Book Pass",
        objective="Develop one scene while preserving authored prose",
        shots=[_unit()],
        format=ProductionFormat.BOOK.value,
        references=[CreativeReference("file://manuscript.docx", "manuscript")],
    )
    jobs = capability_jobs(plan)
    assert [job["kind"] for job in jobs] == ["text.develop", "text.edit", "document.assemble"]
    assert all(job["kind"] != "video.render" for job in jobs)


def test_manga_pipeline_carries_creator_reference_and_lettering():
    plan = build_production_plan(
        title="Manga page",
        objective="Create a page from the user's drawing",
        shots=[_unit(dialogue="Dave, move.")],
        format=ProductionFormat.MANGA.value,
        references=[CreativeReference("file://drawing.png", "drawing", role="visual_authority")],
        style_constraints=["preserve the creator's linework identity"],
    )
    jobs = capability_jobs(plan)
    assert jobs[0]["kind"] == "image.generate"
    assert jobs[1]["kind"] == "layout.letter"
    assert jobs[0]["prompt"]["reference_assets"][0]["provenance"] == "creator_authored"


def test_animation_pipeline_plans_reference_frame_video_voice_and_edit_with_budget_gate():
    plan = build_production_plan(
        title="Mary Meeting Scene",
        objective="Animate an existing storyboard and voice performance",
        shots=[_unit(dialogue="You're late.")],
        format=ProductionFormat.ANIMATION.value,
        budget_ceiling_usd=5.0,
    )
    jobs = capability_jobs(plan)
    assert [job["kind"] for job in jobs] == ["image.generate", "video.render", "voice.synthesize", "edit.assemble"]
    assert all(job["budget_ceiling_usd"] == 5.0 for job in jobs)
    assert all(job["requires_approval"] for job in jobs)
