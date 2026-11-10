"""Pull one string field out of a JSON object while it is still streaming, and cut text at sentence ends."""
import re

_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_SENTENCE_END = re.compile(r"(?<=[.!?。؟:])\s+|\n")


class JsonFieldStream:
    """Feed raw JSON deltas, get back newly decoded text of `field` (a top-level string value)."""

    def __init__(self, field: str = "answer"):
        self.key = re.compile(rf'"{field}"\s*:\s*"')
        self.buf, self.pos, self.done = "", None, False

    def feed(self, delta: str) -> str:
        self.buf += delta
        if self.done:
            return ""
        if self.pos is None:
            m = self.key.search(self.buf)
            if not m:
                return ""
            self.pos = m.end()
        out, i = [], self.pos
        while i < len(self.buf):
            c = self.buf[i]
            if c == '"':
                self.done = True
                i += 1
                break
            if c == "\\":
                if i + 1 >= len(self.buf):
                    break
                nxt = self.buf[i + 1]
                if nxt == "u":
                    if i + 6 > len(self.buf):
                        break
                    out.append(chr(int(self.buf[i + 2:i + 6], 16)))
                    i += 6
                    continue
                out.append(_ESCAPES.get(nxt, nxt))
                i += 2
                continue
            out.append(c)
            i += 1
        self.pos = i
        return "".join(out)


class SentenceBuffer:
    """Hold text until a sentence (or line) is complete, so each piece can be checked before it is shown."""

    def __init__(self):
        self.pending = ""

    def push(self, text: str) -> list[str]:
        self.pending += text
        parts = _SENTENCE_END.split(self.pending)
        if len(parts) == 1:
            return []
        cut = len(self.pending) - len(parts[-1])
        ready, self.pending = self.pending[:cut], parts[-1]
        return [ready]

    def flush(self) -> list[str]:
        ready, self.pending = self.pending, ""
        return [ready] if ready else []


if __name__ == "__main__":
    import json

    raw = json.dumps({"answerable": True, "cited_ids": ["P1"], "answer": 'Costs $18,995.\nIncludes "IV" café é ok.'})
    f, got = JsonFieldStream(), ""
    for i in range(0, len(raw), 3):
        got += f.feed(raw[i:i + 3])
    assert got == 'Costs $18,995.\nIncludes "IV" café é ok.', got
    sb = SentenceBuffer()
    assert sb.push("It costs $18,") == [] and sb.push("995. It inc") == ["It costs $18,995. "]
    assert sb.flush() == ["It inc"]
    print("streaming ok")
