"""Run evals/questions.yaml against a running bot (POST /api/v1/chat) and write TEST_RESULTS.md."""
import argparse
import sys
import time
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas.chat import ChatResponse  # noqa: E402
from app.services.guards import money_amounts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def check(case: dict, r: ChatResponse) -> list[str]:
    fails, text, urls = [], r.answer.lower(), " ".join(s.url for s in r.sources)
    amounts = money_amounts(r.answer)
    if "answered" in case and r.answered != case["answered"]:
        fails.append(f"answered={r.answered}")
    if missing := set(case.get("amounts", [])) - amounts:
        fails.append(f"missing amounts {sorted(missing)}")
    if bad := set(case.get("forbid", [])) & amounts:
        fails.append(f"forbidden amounts {sorted(bad)}")
    if case.get("source") and case["source"] not in urls:
        fails.append(f"no source matching {case['source']}")
    if case.get("any_of") and not any(w.lower() in text for w in case["any_of"]):
        fails.append(f"none of {case['any_of']}")
    if any(w in r.answer for w in case.get("forbid_any", [])):
        fails.append(f"contains one of {case['forbid_any']}")
    if case.get("intent") and r.intent != case["intent"]:
        fails.append(f"intent={r.intent}")
    if r.intent in case.get("forbid_intent", []):
        fails.append(f"intent={r.intent}")
    if case.get("lead_form") and not r.show_lead_form:
        fails.append("no lead form")
    return fails


def main(url: str, only: str | None) -> int:
    client = httpx.Client(base_url=url, timeout=120)
    health = client.get("/api/v1/health").json()
    cases = yaml.safe_load((ROOT / "evals/questions.yaml").read_text())
    cases = [c for c in cases if not only or c["id"].startswith(only)]
    rows, passed = [], 0
    for c in cases:
        hist = [{"role": r, "content": t} for r, t in c.get("history", [])]
        t0 = time.time()
        resp = client.post("/api/v1/chat", json={"message": c["q"], "history": hist})
        resp.raise_for_status()
        r = ChatResponse(**resp.json())
        fails = check(c, r)
        passed += not fails
        print(f"{'PASS' if not fails else 'FAIL'} {c['id']:24} {time.time() - t0:5.1f}s {'; '.join(fails)}")
        rows.append((c, r, fails, time.time() - t0))

    out = [f"# Test results\n\nProvider `{health['llm']}`, answer model `{health['answer_model']}`, run against "
           f"`{url}`. **{passed}/{len(cases)} passed.** Checks are rule-based "
           f"(amounts, sources, intent), see `evals/questions.yaml`.\n"]
    for c, r, fails, secs in rows:
        hist = "".join(f"> _{role}: {text}_\n>\n" for role, text in c.get("history", []))
        src = "\n".join(f"- [{s.title}]({s.url})" for s in r.sources) or "- none"
        out.append(f"## {c['id']} · {c['type']} · {'✅ pass' if not fails else '❌ ' + '; '.join(fails)}\n\n"
                   f"{hist}**Q:** {c['q']}\n\n**A:** {r.answer}\n\n**Sources:**\n{src}\n\n"
                   f"intent `{r.intent}` · answered `{r.answered}` · lead form `{r.show_lead_form}` · {secs:.1f}s\n")
    Path(ROOT / "TEST_RESULTS.md").write_text("\n".join(out))
    print(f"\n{passed}/{len(cases)} passed -> TEST_RESULTS.md")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000", help="base URL of a running bot")
    ap.add_argument("--only", help="run cases whose id starts with this")
    a = ap.parse_args()
    raise SystemExit(main(a.url, a.only))
