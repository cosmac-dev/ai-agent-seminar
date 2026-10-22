"""親エージェントがサブエージェントへ委譲し、出典付きで結果を集約するマルチエージェント。"""

import json
import time
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

@dataclass(frozen=True)
class Evidence:
    source_id: str
    document: str
    text: str

@dataclass(frozen=True)
class Assignment:
    key: str
    title: str
    documents: tuple[str, ...]
    instruction: str

class Finding(BaseModel):
    source_id: str = Field(description="引用した資料の出典ID")
    quote: str = Field(description="出典IDの文を一字一句そのまま写した引用")

class SubagentOutput(BaseModel):
    findings: list[Finding] = Field(description="担当範囲に該当する引用。該当がなければ空")

@dataclass(frozen=True)
class WorkerResult:
    assignment_key: str
    findings: tuple[Finding, ...]
    rejected: tuple[str, ...]

    def items(self) -> dict[str, Finding]:
        # 親エージェントが参照する項目ID（例: features-1）を振る。
        return {f"{self.assignment_key}-{i}": finding
                for i, finding in enumerate(self.findings, 1)}

class Note(BaseModel):
    text: str = Field(description="担当をまたいで注意すべき点")
    finding_ids: list[str] = Field(description="根拠とした項目ID。担当が返したIDだけを使う")

class FinalReport(BaseModel):
    notes: list[Note]

@dataclass(frozen=True)
class Event:
    actor: str
    phase: str
    elapsed: float

@dataclass(frozen=True)
class WorkflowRun:
    results: tuple[WorkerResult, ...]
    final: FinalReport
    report: str
    events: tuple[Event, ...]
    messages: tuple

SAMPLE_EVIDENCE = (
    Evidence("S1-1", "製品仕様書", "製品はCSVファイルのインポートに対応する。"),
    Evidence("S1-2", "製品仕様書", "インポートできるCSVの文字コードはUTF-8のみ。"),
    Evidence("S1-3", "製品仕様書", "オフライン利用には対応しない。"),
    Evidence("S1-4", "製品仕様書", "データはクラウド上に保存される。"),
    Evidence("S1-5", "製品仕様書", "利用には最新版のWebブラウザが必要。"),
    Evidence("S2-1", "導入ガイド", "導入には管理者による初期設定が必要。"),
    Evidence("S2-2", "導入ガイド", "既存データはUTF-8のCSVに変換してから取り込む。"),
    Evidence("S2-3", "導入ガイド", "社内ネットワークから外部への443番ポートの通信を許可する。"),
    Evidence("S3-1", "利用者アンケート", "CSVの取り込み自体は便利。"),
    Evidence("S3-2", "利用者アンケート", "出張先などオフラインの環境でも使いたい。"),
    Evidence("S3-3", "利用者アンケート", "CSVの取り込み手順をもっと分かりやすくしてほしい。"),
    Evidence("S3-4", "利用者アンケート", "Shift_JISのCSVもそのまま取り込めるとよい。"),
)

ASSIGNMENTS = (
    Assignment("features", "機能", ("製品仕様書",),
               "製品が対応する機能と、対応しない機能。利用の前提条件は含めない。"),
    Assignment("requirements", "導入条件", ("製品仕様書", "導入ガイド"),
               "導入する側が事前に満たす条件や作業。製品の機能の説明は含めない。"),
    Assignment("feedback", "利用者の要望", ("利用者アンケート",),
               "利用者が変更や追加を求めている点。感想は含めない。"),
)

SUBAGENT_PROMPT = """あなたは「{title}」担当のサブエージェント。担当範囲: {instruction}
渡された資料の各文が担当範囲に当てはまるかを判断し、当てはまる文だけを引用する。
引用は各行の文を一字一句変えずに写し（行頭の出典IDは含めない）、その行の出典IDを付ける。
該当する記載がなければ findings を空にする。"""

def format_documents(evidence: tuple[Evidence, ...],
                     documents: tuple[str, ...]) -> str:
    lines = []
    for document in documents:
        lines.append(f"## {document}")
        lines += [f"[{item.source_id}] {item.text}"
                  for item in evidence if item.document == document]
    return "\n".join(lines)

async def run_subagent(model: BaseChatModel, assignment: Assignment, request: str,
                       evidence: tuple[Evidence, ...]) -> SubagentOutput:
    subagent = create_agent(
        model,
        system_prompt=SUBAGENT_PROMPT.format(
            title=assignment.title, instruction=assignment.instruction),
        response_format=SubagentOutput,
        name=f"{assignment.key}_agent",
    )
    documents = format_documents(evidence, assignment.documents)
    content = f"依頼: {request}\n\n資料:\n{documents}"
    state = await subagent.ainvoke({"messages": [{"role": "user", "content": content}]})
    return state["structured_response"]

def validate_findings(assignment: Assignment,
                      evidence: tuple[Evidence, ...],
                      output: SubagentOutput) -> WorkerResult:
    sources = {item.source_id: item for item in evidence
               if item.document in assignment.documents}
    accepted, rejected = [], []
    for finding in output.findings:
        source = sources.get(finding.source_id)
        quote = finding.quote.strip()
        if source is None:
            rejected.append(f"担当範囲にない出典: {finding.source_id}")
        elif quote != source.text:
            rejected.append(f"原文と一致しない引用: {finding.quote}")
        else:
            accepted.append(Finding(source_id=finding.source_id, quote=quote))
    return WorkerResult(assignment.key, tuple(accepted), tuple(rejected))

def make_subagent_tool(model: BaseChatModel,
                       assignment: Assignment,
                       evidence: tuple[Evidence, ...],
                       results: list[WorkerResult],
                       events: list[Event],
                       started: float):
    def record(phase: str) -> None:
        events.append(Event(assignment.key, phase,
                            round(time.perf_counter() - started, 2)))

    @tool(assignment.key,
          description=f"「{assignment.title}」担当のサブエージェントへ調査を依頼する。"
                      "結果は項目ID付きの引用で返る。")
    async def delegate(request: str) -> str:
        record("start")
        output = await run_subagent(model, assignment, request, evidence)
        result = validate_findings(assignment, evidence, output)
        results.append(result)
        record("end")
        items = [{"id": finding_id, **finding.model_dump()}
                 for finding_id, finding in result.items().items()]
        return json.dumps({"findings": items, "rejected": len(result.rejected)},
                          ensure_ascii=False)

    return delegate

SUPERVISOR_PROMPT = """あなたは製品調査の取りまとめ役。資料は自分で読まず、担当のサブエージェントへ調査を依頼する。
互いに依存しない担当は、同じ応答の中でまとめて呼び出す。
全担当の結果が揃ったら、複数の担当の結果を突き合わせて分かる注意点だけを notes に書き、根拠の項目IDを付ける。
各担当の結果を言い換えただけの内容は書かない。
項目IDは担当が返したものだけを使う。利用者の要望を実装済みの機能として扱わない。"""

async def run_supervisor(model: BaseChatModel,
                         request: str,
                         evidence: tuple[Evidence, ...] = SAMPLE_EVIDENCE,
                         assignments: tuple[Assignment, ...] = ASSIGNMENTS) -> WorkflowRun:
    results: list[WorkerResult] = []
    events: list[Event] = []
    started = time.perf_counter()
    tools = [make_subagent_tool(model, assignment, evidence, results, events, started)
             for assignment in assignments]
    supervisor = create_agent(model, tools, system_prompt=SUPERVISOR_PROMPT,
                              response_format=FinalReport, name="supervisor")
    state = await supervisor.ainvoke({"messages": [{"role": "user", "content": request}]})
    final = state["structured_response"]
    report = render_report(assignments, tuple(results), final)
    return WorkflowRun(tuple(results), final, report, tuple(events),
                       tuple(state["messages"]))

def render_report(assignments: tuple[Assignment, ...],
                  results: tuple[WorkerResult, ...],
                  final: FinalReport) -> str:
    # 完了順ではなく、担当の識別子で結果を対応付ける。
    by_key = {result.assignment_key: result for result in results}
    if len(by_key) != len(results):
        raise ValueError("同じ担当の結果が複数ある")
    known_ids = {finding_id for result in results for finding_id in result.items()}
    lines = ["# 製品の確認結果"]
    for assignment in assignments:
        lines.append(f"\n## {assignment.title}")
        result = by_key.get(assignment.key)
        if result is None:
            lines.append("- 担当の結果が届いていない。このレポートは未完成。")
            continue
        if not result.findings:
            lines.append("- 該当する記載なし。未確認事項は補わない。")
        for finding_id, finding in result.items().items():
            lines.append(f"- {finding.quote} [{finding.source_id}] ({finding_id})")
    lines.append("\n## 所見（親エージェントの記述。引用の検査対象外）")
    for note in final.notes:
        unknown = [i for i in note.finding_ids if i not in known_ids]
        if unknown:
            raise ValueError(f"担当が返していない項目IDを根拠にしている: {unknown}")
        evidence_ids = ", ".join(note.finding_ids) or "根拠の項目IDなし"
        lines.append(f"- {note.text} ({evidence_ids})")
    return "\n".join(lines)
