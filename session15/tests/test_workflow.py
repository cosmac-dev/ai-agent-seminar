import asyncio
import json
from pathlib import Path
import re
import sys
from typing import Any
import unittest

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cooperative_workflow import (
    ASSIGNMENTS, SAMPLE_EVIDENCE, SUPERVISOR_PROMPT, Assignment, Evidence,
    FinalReport, Finding, Note, SubagentOutput, WorkerResult, render_report,
    run_supervisor, validate_findings,
)

REQUEST = "この製品の機能、導入条件、利用者の要望を確認したい。"

class ScriptedModel(BaseChatModel):
    """API を呼ばず、受け取ったメッセージから応答を組み立てる模擬モデル。"""

    respond: Any

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError("非同期で呼び出す")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        message = await self.respond(messages)
        return ChatResult(generations=[ChatGeneration(message=message)])

def call_tools(*calls: tuple[str, dict]) -> AIMessage:
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": f"call-{index}-{name}"}
        for index, (name, args) in enumerate(calls)
    ])

def is_supervisor(messages) -> bool:
    return messages[0].content == SUPERVISOR_PROMPT

def subagent_assignment(messages, assignments) -> Assignment:
    return next(item for item in assignments if f"「{item.title}」" in messages[0].content)

def received_lines(messages) -> list[tuple[str, str]]:
    content = [m for m in messages if isinstance(m, HumanMessage)][-1].content
    return re.findall(r"^\[(\S+)\] (.+)$", content, flags=re.MULTILINE)

def tool_findings(messages) -> list[str]:
    return [item["id"] for m in messages if isinstance(m, ToolMessage)
            for item in json.loads(m.content)["findings"]]

def scripted_model(assignments=ASSIGNMENTS, *, before_subagent=None,
                   notes=None, received=None) -> ScriptedModel:
    """親は全担当を1回の応答で呼び、担当は受け取った文をすべて引用する。"""

    async def respond(messages):
        if is_supervisor(messages):
            if not any(isinstance(m, ToolMessage) for m in messages):
                return call_tools(*[(item.key, {"request": f"{item.title}を確認する"})
                                    for item in assignments])
            ids = tool_findings(messages)
            final = notes if notes is not None else [{"text": "所見", "finding_ids": ids[:1]}]
            return call_tools(("FinalReport", {"notes": final}))
        assignment = subagent_assignment(messages, assignments)
        lines = received_lines(messages)
        if received is not None:
            received[assignment.key] = lines
        if before_subagent is not None:
            await before_subagent(assignment)
        findings = [{"source_id": source_id, "quote": text} for source_id, text in lines]
        return call_tools(("SubagentOutput", {"findings": findings}))

    return ScriptedModel(respond=respond)

class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_subagents_start_before_any_result_is_merged(self):
        entered = set()
        gate = asyncio.Event()

        async def wait_for_all(assignment):
            entered.add(assignment.key)
            if len(entered) == len(ASSIGNMENTS):
                gate.set()
            await asyncio.wait_for(gate.wait(), timeout=2)

        run = await asyncio.wait_for(
            run_supervisor(scripted_model(before_subagent=wait_for_all), REQUEST), timeout=5)
        fan_out = [m for m in run.messages if isinstance(m, AIMessage) and m.tool_calls]
        self.assertEqual([call["name"] for call in fan_out[0].tool_calls],
                         [item.key for item in ASSIGNMENTS])
        starts = [i for i, event in enumerate(run.events) if event.phase == "start"]
        ends = [i for i, event in enumerate(run.events) if event.phase == "end"]
        self.assertLess(max(starts), min(ends))
        for item in SAMPLE_EVIDENCE:
            self.assertIn(f"{item.text} [{item.source_id}]", run.report)

    async def test_report_follows_assignments_not_completion_order(self):
        delays = {"features": 0.06, "requirements": 0.03, "feedback": 0.0}

        async def delay(assignment):
            await asyncio.sleep(delays[assignment.key])

        run = await run_supervisor(scripted_model(before_subagent=delay), REQUEST)
        self.assertEqual([result.assignment_key for result in run.results],
                         ["feedback", "requirements", "features"])
        positions = [run.report.index(f"## {item.title}") for item in ASSIGNMENTS]
        self.assertEqual(positions, sorted(positions))

    async def test_subagents_receive_only_their_documents(self):
        received = {}
        await run_supervisor(scripted_model(received=received), REQUEST)
        for assignment in ASSIGNMENTS:
            expected = [(item.source_id, item.text) for item in SAMPLE_EVIDENCE
                        if item.document in assignment.documents]
            self.assertEqual(received[assignment.key], expected)

    async def test_supervisor_cannot_cite_unreturned_findings(self):
        model = scripted_model(notes=[{"text": "根拠のない所見", "finding_ids": ["features-99"]}])
        with self.assertRaisesRegex(ValueError, "features-99"):
            await run_supervisor(model, REQUEST)

    async def test_another_assignment_needs_no_runner_change(self):
        evidence = (*SAMPLE_EVIDENCE, Evidence("S4-1", "料金表", "月額料金は利用者数に比例する。"))
        assignments = (*ASSIGNMENTS, Assignment("pricing", "料金", ("料金表",), "料金の条件。"))
        run = await run_supervisor(scripted_model(assignments), REQUEST, evidence, assignments)
        self.assertEqual(len(run.results), 4)
        self.assertIn("月額料金は利用者数に比例する。 [S4-1] (pricing-1)", run.report)

    async def test_runs_do_not_share_results_or_events(self):
        left, right = await asyncio.gather(
            run_supervisor(scripted_model(), REQUEST),
            run_supervisor(scripted_model(), REQUEST),
        )
        self.assertEqual(left.report, right.report)
        self.assertEqual(len(left.results), len(ASSIGNMENTS))
        self.assertEqual(len(left.events), 2 * len(ASSIGNMENTS))
        self.assertIsNot(left.events, right.events)

class ValidationTests(unittest.TestCase):
    def test_findings_outside_scope_or_changed_are_rejected(self):
        output = SubagentOutput(findings=[
            Finding(source_id="S1-3", quote=" オフライン利用には対応しない。 "),
            Finding(source_id="S1-3", quote="オフライン利用に対応する。"),
            Finding(source_id="S3-2", quote="出張先などオフラインの環境でも使いたい。"),
            Finding(source_id="missing", quote="資料にない記載"),
        ])
        result = validate_findings(ASSIGNMENTS[0], SAMPLE_EVIDENCE, output)
        self.assertEqual(result.findings,
                         (Finding(source_id="S1-3", quote="オフライン利用には対応しない。"),))
        self.assertEqual(len(result.rejected), 3)

    def test_empty_missing_and_duplicate_results_are_distinguished(self):
        features = WorkerResult("features", (Finding(source_id="S1-1", quote="x"),), ())
        empty = WorkerResult("feedback", (), ())
        report = render_report(ASSIGNMENTS, (features, empty), FinalReport(notes=[]))
        self.assertIn("## 導入条件\n- 担当の結果が届いていない。", report)
        self.assertIn("## 利用者の要望\n- 該当する記載なし。", report)
        with self.assertRaises(ValueError):
            render_report(ASSIGNMENTS, (features, features), FinalReport(notes=[]))
        with self.assertRaises(ValueError):
            render_report(ASSIGNMENTS, (features,), FinalReport(notes=[
                Note(text="根拠のない所見", finding_ids=["requirements-1"]),
            ]))

if __name__ == "__main__":
    unittest.main()
