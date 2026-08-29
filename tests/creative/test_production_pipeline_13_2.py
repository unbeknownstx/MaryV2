from mary.creative import CharacterAnchor, Shot, build_production_plan, capability_jobs
from mary.skills.registry import SkillRegistry

def test_production_is_plan_not_execution():
    mary=CharacterAnchor("mary","Mary",("red hair","blue eyes"),voice_profile="mary")
    plan=build_production_plan(title="Late Night",objective="A Mary character short",characters=[mary],shots=[Shot("s1",5,"medium","Mary looks up from her computer",dialogue="You're still awake?",continuity=("red hair","blue eyes" ,))])
    jobs=capability_jobs(plan)
    assert plan.stage=="storyboard"
    assert {j["kind"] for j in jobs}=={"video.render","voice.synthesize","edit.assemble"}
    assert all(j["requires_approval"] for j in jobs)
    assert plan.fingerprint

def test_production_skill_is_internal_and_enabled():
    snap={x["key"]:x for x in SkillRegistry().snapshot()}
    assert snap["production"]["enabled"] is True
    assert snap["production"]["external"] is False
