#!/usr/bin/env python3
"""세션의 컨텍스트가 커지면 한 번 알린다 (UserPromptSubmit 훅).

모델은 턴마다 지금까지의 대화를 통째로 다시 읽는다. 사이클을 한 세션에서 며칠씩 이어 가면 그 크기가 수십만 토큰이 되고,
그것이 토큰과 시간의 대부분을 먹는다. 사이클 문서나 인계 메모(handoff 스킬)로 새 세션에서 이어 가면 된다 — 그 말을 제때 하게 한다.

게임 저장소(kit.config.json 이 있는 곳) 안에서만, 20만 토큰을 넘을 때 한 번, 그 뒤로 10만 토큰이 늘 때마다 한 번 적는다.
아무 일 없으면 아무것도 적지 않는다 (적은 글은 컨텍스트에 들어간다). 무슨 일이 있어도 0 으로 끝난다 — 사용자의 입력을 막지 않는다.
"""
import json
import os
import sys
import tempfile

FIRST, STEP = 200_000, 100_000
TAIL = 600_000  # 기록의 끝에서 이만큼만 읽는다


def in_game(cwd):
    d = os.path.abspath(cwd or ".")
    while True:
        if os.path.exists(os.path.join(d, "kit.config.json")):
            return True
        up = os.path.dirname(d)
        if up == d:
            return False
        d = up


def context_size(path):
    """기록의 마지막 응답이 읽은 토큰 수."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL))
        lines = f.read().decode("utf-8", "replace").split("\n")
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        u = (d.get("message") or {}).get("usage")
        if d.get("type") == "assistant" and u and not d.get("isSidechain"):
            return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    return 0


def main():
    data = json.load(sys.stdin)
    path = data.get("transcript_path") or ""
    if not os.path.exists(path) or not in_game(data.get("cwd")):
        return
    size = context_size(path)
    level = 0 if size < FIRST else 1 + (size - FIRST) // STEP
    mark = os.path.join(tempfile.gettempdir(), "gamedev-kit-context", str(data.get("session_id") or "session"))
    try:
        told = int(open(mark).read())
    except (OSError, ValueError):
        told = 0
    if level != told:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        with open(mark, "w") as f:
            f.write(str(level))
    if level > told:
        print(f"[gamedev-kit] 이 세션의 컨텍스트가 약 {size // 10000}만 토큰이다 — 턴마다 이만큼을 다시 읽는다. "
              "지금 하던 일의 끊을 자리(결정을 묻는 곳 · 차수가 끝난 곳 · 사이클이 끝난 곳)에 오면 사용자에게 한 줄로 권한다: "
              "새 세션으로 넘어가면 가볍다 — 사이클 중이면 새 세션에서 `/gamedev-kit:cycle next` (문서에 상태가 다 있다), "
              "사이클 밖의 일이면 여기서 `/gamedev-kit:handoff` 로 메모를 남기고 새 세션에서 `/gamedev-kit:handoff resume`. "
              "권하기만 하고, 사용자가 그냥 가자고 하면 하던 일을 계속한다.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
