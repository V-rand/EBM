import pytest
import json


@pytest.mark.asyncio
async def test_research_state_guides_reasoning_before_search():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="research-state-1")

    started = await handle_research_state(
        operation="start",
        question_model={
            "answer_type": "entity",
            "hard_constraints": ["associative clue"],
            "output_fields": ["answer"],
        },
    )
    assert started.success

    focused = await handle_research_state(
        operation="focus_constraint",
        active_constraint="associative clue",
        expected_gain="decide whether candidate background resolves the clue",
    )
    assert focused.success

    guidance = await handle_research_state(operation="next_action")
    data = guidance.data

    assert data["control"]["must_inventory_known_facts"] is True
    assert data["control"]["answer_allowed"] is False
    assert data["next_action"] == "inventory_known_facts"

    inventoried = await handle_research_state(
        operation="inventory_known_facts",
        candidate="Fleming",
        known_facts=["Scottish scientist", "discovered penicillin"],
        reasoning_paths=["Scottish -> Highlands -> green mountains"],
    )
    assert inventoried.success

    guidance = await handle_research_state(operation="next_action")
    assert guidance.data["control"]["must_inventory_known_facts"] is False
    assert guidance.data["next_action"] in {"reason_from_known_facts", "discriminating_search"}
    assert "action_card" in guidance.data
    assert guidance.data["action_card"]["active_constraint"] == "associative clue"
    assert "allowed_next_tools" in guidance.data["action_card"]


@pytest.mark.asyncio
async def test_research_state_counts_no_progress_and_failed_pivots():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="research-state-2")
    await handle_research_state(operation="start", question_model={"answer_type": "entity"})
    await handle_research_state(operation="focus_constraint", active_constraint="hard clue")

    for _ in range(3):
        await handle_research_state(operation="round_update", progress=False)

    guidance = await handle_research_state(operation="next_action")
    assert guidance.data["control"]["must_pivot"] is True
    assert guidance.data["state"]["failed_pivots"] == 1

    await handle_research_state(operation="pivot", pivot_strategy="change frame")
    for _ in range(3):
        await handle_research_state(operation="round_update", progress=False)

    guidance = await handle_research_state(operation="next_action")
    assert guidance.data["control"]["must_stop_or_answer_uncertain"] is True
    assert guidance.data["state"]["failed_pivots"] == 2


def test_research_state_tool_is_registered(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_API_KEY", "")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")

    from agent_os import AgentOS

    osys = AgentOS(data_dir=str(tmp_path))
    try:
        schema_names = [schema["function"]["name"] for schema in osys.list_tool_schemas()]
        assert "research_state" in schema_names
        research_schema = next(schema for schema in osys.list_tool_schemas() if schema["function"]["name"] == "research_state")
        props = research_schema["function"]["parameters"]["properties"]
        assert "working_notes" in props["operation"]["enum"]
        assert {"claim_inventory", "strategy_frame", "path_choice"} <= set(props["operation"]["enum"])
        assert {
            "question_type", "active_goal", "current_action", "known", "unknown",
            "failed_paths", "evidence_target", "exit_condition", "next_move",
        } <= set(props)
        assert {
            "verified_facts", "hypotheses", "nodes", "edges", "anchors",
            "candidate_paths", "chosen_path", "narrowest_node", "first_action", "reject_reason",
        } <= set(props)
    finally:
        import asyncio

        asyncio.run(osys.stop())


@pytest.mark.asyncio
async def test_research_state_persists_to_session_research_file(tmp_path):
    from agent_os.tools.registry import set_session_context
    from agent_os.tools import research
    from agent_os.tools.research import handle_research_state

    session_id = "research-state-persist"
    set_session_context(work_dir=str(tmp_path), session_id=session_id)

    await handle_research_state(
        operation="start",
        question_model={"answer_type": "entity", "hard_constraints": ["constraint"]},
    )
    await handle_research_state(operation="focus_constraint", active_constraint="constraint")

    state_path = tmp_path / "research" / "research_state.json"
    assert state_path.exists()
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["active_constraint"] == "constraint"

    research._states.pop(session_id, None)
    restored = await handle_research_state(operation="next_action")
    assert restored.data["state"]["active_constraint"] == "constraint"


@pytest.mark.asyncio
async def test_research_state_records_compact_working_notes(tmp_path):
    from agent_os.tools.registry import set_session_context
    from agent_os.tools import research
    from agent_os.tools.research import handle_research_state

    session_id = "research-state-working-notes"
    set_session_context(work_dir=str(tmp_path), session_id=session_id)

    await handle_research_state(
        operation="start",
        question_model={"answer_type": "publication_name"},
    )
    recorded = await handle_research_state(
        operation="working_notes",
        question_type="literature_lookup",
        active_goal="identify the paper venue",
        current_action="search",
        known=["12.4% validation sample", "ordinal probit model"],
        unknown=["journal name"],
        failed_paths=["country-first broad web queries"],
        evidence_target="paper satisfying sample-size and ordinal-probit constraints",
        exit_condition="candidate title and publication venue found or fingerprint family exhausted",
        next_move="search high-entropy numeric/method fingerprint",
    )

    assert recorded.success
    assert recorded.data["working_notes_recorded"] is True
    notes = recorded.data["state"]["working_notes"]
    assert notes["question_type"] == "literature_lookup"
    assert notes["active_goal"] == "identify the paper venue"
    assert notes["current_action"] == "search"
    assert notes["failed_paths"] == ["country-first broad web queries"]
    assert notes["evidence_target"] == "paper satisfying sample-size and ordinal-probit constraints"
    assert notes["exit_condition"] == "candidate title and publication venue found or fingerprint family exhausted"

    research._states.pop(session_id, None)
    restored = await handle_research_state(operation="next_action")
    assert restored.data["state"]["working_notes"]["next_move"] == "search high-entropy numeric/method fingerprint"


@pytest.mark.asyncio
async def test_claim_inventory_separates_verified_facts_from_hypotheses():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="claim-inventory-test")
    await handle_research_state(operation="start", question_model={"answer_type": "person"})

    out = await handle_research_state(
        operation="claim_inventory",
        verified_facts=[
            "2018 Lantern Prize feature winners include two digital museum publications"
        ],
        hypotheses=[
            "One listed critic may have written the later conservation review"
        ],
        unknown=[
            "which later review references a conservation-science study"
        ],
    )

    assert out.success
    state = out.data["state"]
    assert state["claim_inventory"]["verified_facts"] == [
        "2018 Lantern Prize feature winners include two digital museum publications"
    ]
    assert state["claim_inventory"]["hypotheses"] == [
        "One listed critic may have written the later conservation review"
    ]
    assert "hypotheses_are_not_facts" in out.data["guidance"]


@pytest.mark.asyncio
async def test_strategy_frame_records_problem_graph_nodes_and_edges():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="strategy-frame-test")
    await handle_research_state(operation="start", question_model={"answer_type": "person"})

    out = await handle_research_state(
        operation="strategy_frame",
        nodes=[
            "critic",
            "digital feature prize",
            "later review",
            "referenced conservation scientist",
            "three-author conservation study",
            "heritage materials workshop presenter",
        ],
        edges=[
            "critic won prize",
            "critic wrote later review",
            "review references scientist",
            "scientist coauthored study",
            "one coauthor presented workshop five years before prize",
        ],
        anchors=[
            "heritage society workshop records",
            "OpenAlex conservation publications",
            "digital feature prize winner lists",
        ],
    )

    assert out.success
    frame = out.data["state"]["strategy_frame"]
    assert "heritage materials workshop presenter" in frame["nodes"]
    assert "OpenAlex conservation publications" in frame["anchors"]
    assert out.data["next_action"] == "choose_path"
    assert out.data["action_card"]["search_needed"] == "after_path_choice"


@pytest.mark.asyncio
async def test_path_choice_prefers_narrowest_searchable_node():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="path-choice-test")
    await handle_research_state(operation="start", question_model={"answer_type": "person"})
    await handle_research_state(
        operation="strategy_frame",
        nodes=["critic", "prize list", "later review", "conservation study", "workshop presenter"],
        anchors=["prize list", "workshop presenter"],
    )

    out = await handle_research_state(
        operation="path_choice",
        candidate_paths=[
            "forward: critic -> prize -> review -> scientist -> workshop",
            "backward: workshop presenter -> conservation study -> cited review -> critic",
            "anchor-first: prize list + workshop records intersection",
        ],
        chosen_path="backward: workshop presenter -> conservation study -> cited review -> critic",
        narrowest_node="workshop presenter / conservation publication cluster",
        first_action='openalex_works(query="conservation scientist workshop materials study")',
        reject_reason=[
            "forward path starts from broad critic universe",
            "prize list alone has many media candidates",
        ],
    )

    assert out.success
    choice = out.data["state"]["path_choice"]
    assert choice["narrowest_node"] == "workshop presenter / conservation publication cluster"
    assert "openalex_works" in choice["first_action"]
    assert out.data["path_choice_recorded"] is True
    assert "pivot to the next candidate path" in out.data["guidance"][1]


@pytest.mark.asyncio
async def test_inventory_known_facts_warns_that_hypotheses_are_not_facts():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="inventory-guidance-test")
    await handle_research_state(operation="start", question_model={"answer_type": "person"})
    out = await handle_research_state(
        operation="inventory_known_facts",
        known_facts=["confirmed fact"],
        reasoning_paths=["possible path"],
    )

    assert out.success
    assert "claim_inventory.hypotheses" in out.data["guidance"][0]


def test_research_guardrail_reminds_after_nine_blind_retrieval_rounds():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    search = [{"name": "web_search", "arguments": {"query": "first"}}]
    read = [{"name": "web_read", "arguments": {"url": "https://example.com"}}]
    with_state = [{"name": "research_state", "arguments": {"operation": "next_action"}}]

    blind_rounds = 0
    # hint fires on 9th round (next_count==9), soft reminder at >=9 (not a block)
    for call in [search, read, search, read, search, search, read, search, search]:
        blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
            call,
            consecutive_blind_search_rounds=blind_rounds,
            messages=messages,
        )
        assert blocked is False
        assert reminder == ""
        if blind_rounds != 9:
            assert hint == ""

    # 10th round — soft reminder, not blocked
    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        read,
        consecutive_blind_search_rounds=blind_rounds,
        messages=messages,
    )
    assert blocked is False
    assert reminder == ""
    assert hint == ""
    assert blind_rounds == 9  # not incremented, stays at 9
    assert messages[-1]["role"] == "user"
    assert "连续盲搜" in messages[-1]["content"]

    blocked, _, blind_rounds, hint = loop._research_search_guardrail(
        with_state,
        consecutive_blind_search_rounds=blind_rounds,
        messages=messages,
    )
    assert blocked is False
    assert blind_rounds == 0  # research_state resets counter
    assert hint == ""


def test_research_guardrail_counts_structured_retrieval_tools():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    calls = [
        [{"name": "arxiv_search", "arguments": {"query": "first"}}],
        [{"name": "openalex_works", "arguments": {"title": "first"}}],
        [{"name": "pubmed_search", "arguments": {"query": "first"}}],
        [{"name": "opencitations_search", "arguments": {"doi": "10.123/test"}}],
        [{"name": "crossref_search", "arguments": {"title": "first"}}],
        [{"name": "web_search", "arguments": {"query": "first"}}],
        [{"name": "arxiv_search", "arguments": {"query": "second"}}],
        [{"name": "pubmed_search", "arguments": {"query": "second"}}],
        [{"name": "crossref_search", "arguments": {"title": "second"}}],
    ]

    blind_rounds = 0
    for index, call in enumerate(calls, start=1):
        blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
            call,
            consecutive_blind_search_rounds=blind_rounds,
            messages=messages,
        )
        assert blind_rounds == index
        assert blocked is False


def test_research_guardrail_uses_registry_toolset_for_plugin_retrieval_tools():
    from agent_os.kernel.agent_loop import AgentLoop

    class Tools:
        def get_entry(self, name):
            if name == "custom_literature_search":
                return type("Entry", (), {"toolset": "retrieval"})()
            if name == "disabled_search":
                return None
            return None

    loop = AgentLoop.__new__(AgentLoop)
    loop.tools = Tools()
    messages = []

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        [{"name": "custom_literature_search", "arguments": {"query": "first"}}],
        consecutive_blind_search_rounds=0,
        messages=messages,
    )
    assert blocked is False
    assert reminder == ""
    assert hint == ""
    assert blind_rounds == 1

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        [{"name": "disabled_search", "arguments": {"query": "first"}}],
        consecutive_blind_search_rounds=blind_rounds,
        messages=messages,
    )
    assert blocked is False
    assert reminder == ""
    assert hint == ""
    assert blind_rounds == 1


def test_research_guardrail_parallel_retrieval_batch_counts_as_one_round():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    batch = [
        {"name": "arxiv_search", "arguments": {"query": "first"}},
        {"name": "openalex_works", "arguments": {"title": "first"}},
        {"name": "crossref_search", "arguments": {"query": "first"}},
    ]

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        batch,
        consecutive_blind_search_rounds=0,
        messages=messages,
    )

    assert blocked is False
    assert reminder == ""
    assert hint == ""
    assert blind_rounds == 1


def test_research_guardrail_reminds_on_multiple_web_search_calls_in_one_turn():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    batch = [
        {"name": "web_search", "arguments": {"query": "first"}},
        {"name": "web_search", "arguments": {"query": "second"}},
    ]

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        batch,
        consecutive_blind_search_rounds=5,
        messages=messages,
    )

    assert blocked is False  # soft reminder, not hard block
    assert "同一轮只能调用一次" in messages[-1]["content"]
    assert blind_rounds == 5  # unchanged
    assert hint == ""


def test_research_guardrail_does_not_count_workspace_search_as_blind_external_retrieval():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    call = [{"name": "workspace_search", "arguments": {"query": "first"}}]

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        call,
        consecutive_blind_search_rounds=3,
        messages=messages,
    )

    assert blocked is False
    assert reminder == ""
    assert hint == ""
    assert blind_rounds == 3


@pytest.mark.asyncio
async def test_research_state_analyzes_associative_constraint_with_action_card():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="research-state-3")
    await handle_research_state(operation="start", question_model={"answer_type": "entity"})
    await handle_research_state(
        operation="focus_constraint",
        active_constraint="name evokes someone living in green mountains",
    )

    empty = await handle_research_state(
        operation="analyze_constraint",
        active_constraint="name evokes someone living in green mountains",
        candidate="Alexander Fleming",
        constraint_type="associative",
    )
    assert empty.data["control"]["must_inventory_known_facts"] is True

    analyzed = await handle_research_state(
        operation="analyze_constraint",
        active_constraint="name evokes someone living in green mountains",
        candidate="Alexander Fleming",
        constraint_type="associative",
        known_facts=["Scottish scientist", "surname Fleming"],
    )

    card = analyzed.data["action_card"]
    assert analyzed.data["next_action"] == "reason_from_known_facts"
    assert analyzed.data["constraint_analysis"]["constraint_type"] == "associative"
    assert analyzed.data["control"]["reasoning_preferred"] is False
    assert "nationality / geography" in card["reasoning_lenses"]
    assert card["search_needed"] == "only_for_verification"
    assert card["search_policy"] == "associative_prefer_reasoning_after_first_failed_match"
    assert card["blocked_next_tools"] == []


@pytest.mark.asyncio
async def test_associative_no_progress_prefers_reasoning_without_hard_block():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="research-state-4")
    await handle_research_state(operation="start", question_model={"answer_type": "entity"})
    await handle_research_state(
        operation="focus_constraint",
        active_constraint="name reminds of a mountain resident",
    )
    await handle_research_state(
        operation="inventory_known_facts",
        candidate="Fleming",
        known_facts=["Scottish scientist"],
        reasoning_paths=["Scottish -> Highlands"],
    )
    await handle_research_state(operation="round_update", progress=False)

    guidance = await handle_research_state(operation="next_action")
    assert guidance.data["next_action"] == "reason_from_known_facts"
    assert guidance.data["control"]["reasoning_preferred"] is True


def test_research_guardrail_hints_at_nine_consecutive_blind_retrieval_rounds():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    search = [{"name": "web_search", "arguments": {"query": "first"}}]

    for i in range(8):
        blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
            search,
            consecutive_blind_search_rounds=(i),
            messages=messages,
        )
        assert blocked is False
        assert reminder == ""
        assert hint == ""
        assert blind_rounds == i + 1

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        search,
        consecutive_blind_search_rounds=blind_rounds,
        messages=messages,
    )
    assert blocked is False
    assert reminder == ""
    assert "research_state" in hint
    assert blind_rounds == 9


def test_research_guardrail_reminds_on_mixed_state_and_retrieval_batch():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    mixed = [
        {"name": "web_search", "arguments": {"query": "first"}},
        {"name": "research_state", "arguments": {"operation": "next_action"}},
    ]

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        mixed,
        consecutive_blind_search_rounds=0,
        messages=messages,
    )

    assert blocked is False  # soft reminder
    assert "不要将 research_state" in messages[-1]["content"]
    assert blind_rounds == 0
    assert hint == ""


def test_research_guardrail_reminds_on_mixed_state_and_structured_retrieval_batch():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    messages = []
    mixed = [
        {"name": "openalex_works", "arguments": {"title": "first"}},
        {"name": "research_state", "arguments": {"operation": "next_action"}},
    ]

    blocked, reminder, blind_rounds, hint = loop._research_search_guardrail(
        mixed,
        consecutive_blind_search_rounds=0,
        messages=messages,
    )

    assert blocked is False  # soft reminder
    assert "不要将 research_state" in messages[-1]["content"]
    assert blind_rounds == 0
    assert hint == ""


@pytest.mark.asyncio
async def test_structured_retrieval_tool_results_are_archived(tmp_path):
    from agent_os.kernel.agent_loop import AgentLoop
    from agent_os.tools.registry import ToolResult

    class Sessions:
        async def get(self, session_id):
            return type("Session", (), {"work_dir": str(tmp_path)})()

    class WorkspaceMemory:
        def __init__(self):
            self.saved = None

        async def upsert_artifact(self, session_id, *, path, content, artifact_type, title, summary, metadata):
            self.saved = {
                "session_id": session_id,
                "path": path,
                "content": content,
                "artifact_type": artifact_type,
                "title": title,
                "summary": summary,
                "metadata": metadata,
            }
            return {"id": "artifact"}

    loop = AgentLoop.__new__(AgentLoop)
    loop.workspace_memory = WorkspaceMemory()
    loop.sessions = Sessions()

    archived_path = await loop._archive_external_tool_result(
        "s1",
        "openalex_works",
        {"title": "test paper"},
        ToolResult.ok(data={
            "results": [{
                "title": "Test Paper",
                "url": "https://example.test/paper",
                "authors": ["A. Researcher"],
                "content": "Abstract text.",
            }],
            "count": 1,
        }),
    )

    assert archived_path
    assert archived_path.startswith("raw_search/openalex_works/")
    assert loop.workspace_memory.saved["artifact_type"] == "external_retrieval"
    assert "Test Paper" in loop.workspace_memory.saved["content"]
    assert loop.workspace_memory.saved["metadata"]["lineage"]["source_urls"] == ["https://example.test/paper"]


@pytest.mark.asyncio
async def test_error_only_retrieval_results_are_not_archived(tmp_path):
    from agent_os.kernel.agent_loop import AgentLoop
    from agent_os.tools.registry import ToolResult

    class Tools:
        def get_entry(self, name):
            if name == "wikipedia_lookup":
                return type("Entry", (), {"toolset": "retrieval"})()
            return None

    class WorkspaceMemory:
        async def upsert_artifact(self, *args, **kwargs):
            raise AssertionError("error-only retrieval result should not be archived")

    loop = AgentLoop.__new__(AgentLoop)
    loop.tools = Tools()
    loop.workspace_memory = WorkspaceMemory()

    archived_path = await loop._archive_external_tool_result(
        "s1",
        "wikipedia_lookup",
        {"query": "garfield"},
        ToolResult.ok(data={"query": "garfield", "error": "not_found", "summary": "not found"}),
    )

    assert archived_path is None


@pytest.mark.asyncio
async def test_plugin_retrieval_tool_results_are_archived_by_toolset(tmp_path):
    from agent_os.kernel.agent_loop import AgentLoop
    from agent_os.tools.registry import ToolResult

    class Tools:
        def get_entry(self, name):
            if name == "custom_literature_search":
                return type("Entry", (), {"toolset": "retrieval"})()
            return None

    class WorkspaceMemory:
        def __init__(self):
            self.saved = None

        async def upsert_artifact(self, session_id, *, path, content, artifact_type, title, summary, metadata):
            self.saved = {"path": path, "content": content, "metadata": metadata}
            return {"id": "artifact"}

    loop = AgentLoop.__new__(AgentLoop)
    loop.tools = Tools()
    loop.workspace_memory = WorkspaceMemory()

    archived_path = await loop._archive_external_tool_result(
        "s1",
        "custom_literature_search",
        {"query": "test"},
        ToolResult.ok(data={"query": "test", "results": [{"title": "Plugin Result", "url": "https://example.test"}]}),
    )

    assert archived_path
    assert archived_path.startswith("raw_search/custom_literature_search/")
    assert "Plugin Result" in loop.workspace_memory.saved["content"]


def test_constraint_reasoning_skill_exists():
    from pathlib import Path

    skill = Path("skills/research/constraint_reasoning/SKILL.md")
    text = skill.read_text(encoding="utf-8")

    assert "associative" in text
    assert "linguistic" in text
    assert "geographic" in text


def test_prune_orphaned_tool_messages_removes_incomplete_middle_group():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    msgs = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1", "function": {"name": "web_search", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "tc1", "content": "{}"},
        {"role": "assistant", "content": "ok"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "tc2", "function": {"name": "web_search", "arguments": "{}"}}]},
        {"role": "user", "content": "q2"},
    ]

    pruned = loop._prune_orphaned_tool_messages(msgs)
    assert [m["role"] for m in pruned] == ["user", "assistant", "tool", "assistant", "user"]
    assert all(
        not (
            m.get("role") == "assistant"
            and any(tc.get("id") == "tc2" for tc in (m.get("tool_calls") or []))
        )
        for m in pruned
    )


def test_prune_orphaned_tool_messages_drops_orphan_tools_and_keeps_complete_groups():
    from agent_os.kernel.agent_loop import AgentLoop

    loop = AgentLoop.__new__(AgentLoop)
    msgs = [
        {"role": "tool", "tool_call_id": "orphan", "content": "{}"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "tc3", "function": {"name": "web_search", "arguments": "{}"}},
            {"id": "tc4", "function": {"name": "web_read", "arguments": "{}"}},
        ]},
        {"role": "tool", "tool_call_id": "tc3", "content": "{}"},
        {"role": "tool", "tool_call_id": "tc4", "content": "{}"},
        {"role": "assistant", "content": "done"},
    ]

    pruned = loop._prune_orphaned_tool_messages(msgs)
    assert [m["role"] for m in pruned] == ["assistant", "tool", "tool", "assistant"]


def test_enforce_research_action_card_no_state_file_is_noop():
    from agent_os.tools.research import enforce_research_state_action_card

    blocked, reminder = enforce_research_state_action_card("/tmp/nonexistent", ["web_search"])
    assert not blocked
    assert reminder is None


def test_enforce_research_action_card_no_blocked_tools_when_state_empty(tmp_path):
    from agent_os.tools.research import enforce_research_state_action_card

    state = {}
    state_dir = tmp_path / "research"
    state_dir.mkdir()
    (state_dir / "research_state.json").write_text(json.dumps(state))

    blocked, reminder = enforce_research_state_action_card(str(tmp_path), ["web_search"])
    assert not blocked
    assert reminder is None


def test_enforce_research_action_card_does_not_hard_block_inventory_guidance(tmp_path):
    from agent_os.tools.research import enforce_research_state_action_card

    state = {
        "question_model": {"answer_type": "entity", "hard_constraints": ["year clue"]},
        "active_constraint": "year clue",
        "active_constraint_type": "temporal",
        "expected_gain": "find which entity matches",
        "candidates": {},
        "evidence": [],
        "known_fact_inventory": {},
        "reasoning_paths": {},
        "no_progress_rounds": 0,
        "failed_pivots": 0,
        "last_progress": {},
    }
    state_dir = tmp_path / "research"
    state_dir.mkdir()
    (state_dir / "research_state.json").write_text(json.dumps(state))

    blocked, reminder = enforce_research_state_action_card(str(tmp_path), ["web_search"])
    assert not blocked, "inventory guidance should not hard-block candidate discovery retrieval"
    assert reminder is None


def test_enforce_research_action_card_allows_search_when_action_card_says_pivot(tmp_path):
    from agent_os.tools.research import enforce_research_state_action_card

    state = {
        "question_model": {"answer_type": "entity", "hard_constraints": ["year clue"]},
        "active_constraint": "year clue",
        "candidates": {},
        "evidence": [],
        "known_fact_inventory": {"candidate1": ["fact1"]},
        "reasoning_paths": {},
        "no_progress_rounds": 0,
        "failed_pivots": 1,
        "last_progress": {"progress": False},
    }
    state_dir = tmp_path / "research"
    state_dir.mkdir()
    (state_dir / "research_state.json").write_text(json.dumps(state))

    # failed_pivots=1 with known facts → next_action=pivot → web_search is allowed
    blocked, reminder = enforce_research_state_action_card(str(tmp_path), ["web_search"])
    assert not blocked, "should allow web_search during pivot phase"


def test_enforce_research_action_card_blocks_all_retrieval_after_two_failed_pivots(tmp_path):
    from agent_os.tools.research import enforce_research_state_action_card

    state = {
        "question_model": {"answer_type": "entity"},
        "active_constraint": "year clue",
        "candidates": {"candidate1": {"matched": [], "failed": [], "missing": ["year"], "status": "active"}},
        "evidence": [],
        "known_fact_inventory": {"candidate1": ["fact1"]},
        "reasoning_paths": {},
        "no_progress_rounds": 0,
        "failed_pivots": 2,
        "last_progress": {"progress": False},
    }
    state_dir = tmp_path / "research"
    state_dir.mkdir()
    (state_dir / "research_state.json").write_text(json.dumps(state))

    blocked, reminder = enforce_research_state_action_card(str(tmp_path), ["web_search", "arxiv_search"])
    assert blocked, "should block all retrieval after 2 failed pivots"
    assert "answer_with_uncertainty" in reminder or "blocked" in reminder.lower()


@pytest.mark.asyncio
async def test_reset_blocks_retrieval_until_start():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state, enforce_research_state_action_card
    import tempfile, os, json

    with tempfile.TemporaryDirectory() as td:
        work_dir = os.path.join(td, "work")
        os.makedirs(work_dir)
        set_session_context(work_dir=work_dir, session_id="reset-test")

        # Normal start → retrieval is allowed (focus_constraint, blocked=[])
        await handle_research_state(operation="start", question_model={"answer_type": "entity"})
        blocked, _ = enforce_research_state_action_card(work_dir, ["web_search"])
        assert not blocked, "before reset, retrieval should be allowed"

        # Reset → after_reset flag set → retrieval BLOCKED
        await handle_research_state(operation="reset")
        blocked, reminder = enforce_research_state_action_card(work_dir, ["web_search"])
        assert blocked, "after reset, retrieval must be blocked"
        assert "restart_required" in reminder or "reset" in reminder.lower()

        # start() clears after_reset → retrieval allowed again
        await handle_research_state(operation="start", question_model={"answer_type": "entity"})
        blocked, _ = enforce_research_state_action_card(work_dir, ["web_search"])
        assert not blocked, "after start(), retrieval should be allowed again"


@pytest.mark.asyncio
async def test_reset_cleared_by_focus_constraint_then_inventory():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state, enforce_research_state_action_card
    import tempfile, os

    with tempfile.TemporaryDirectory() as td:
        work_dir = os.path.join(td, "work")
        os.makedirs(work_dir)
        set_session_context(work_dir=work_dir, session_id="reset-fc-test")

        await handle_research_state(operation="reset")
        blocked, _ = enforce_research_state_action_card(work_dir, ["web_search"])
        assert blocked, "after reset, retrieval blocked (restart_required)"

        # focus_constraint clears after_reset; inventory guidance should not hard-block retrieval.
        await handle_research_state(operation="focus_constraint", active_constraint="year clue")
        blocked, reminder = enforce_research_state_action_card(work_dir, ["web_search"])
        assert not blocked
        assert reminder is None

        # After inventory, normal flow resumes
        await handle_research_state(operation="inventory_known_facts", known_facts=["year is 1899", "drug is aspirin"])
        await handle_research_state(operation="round_update", progress=True)
        blocked, _ = enforce_research_state_action_card(work_dir, ["web_search"])
        assert not blocked, "after inventory + progress, discriminating_search allows retrieval"


@pytest.mark.asyncio
async def test_literature_discovery_goes_to_discriminating_search_without_inventory_gate():
    from agent_os.tools.registry import set_session_context
    from agent_os.tools.research import handle_research_state

    set_session_context(work_dir="", session_id="literature-discovery-test")
    await handle_research_state(
        operation="start",
        question_model={
            "answer_type": "publication_name",
            "hard_constraints": [
                "paper published in the 2010s",
                "42,137-household survey sample",
                "ordinal probit model",
            ],
        },
    )
    focused = await handle_research_state(
        operation="focus_constraint",
        active_constraint="identify the paper and publication from census/methodology constraints",
    )

    assert focused.data["next_action"] == "discriminating_search"
    assert focused.data["control"]["literature_discovery"] is True
    assert focused.data["control"]["must_inventory_known_facts"] is False
    assert focused.data["action_card"]["search_needed"] == "yes"

