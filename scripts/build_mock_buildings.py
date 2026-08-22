#!/usr/bin/env python3
"""⚠ 가상(mock) 건물 데이터 생성. 실제 공장 위치가 아니다 — 느낌 확인용 임시 파일.

팩토리온(전국산업단지및공장정보표준데이터) 실데이터를 확보하면
이 스크립트와 출력 파일(data/processed/buildings.mock.json) 을 **삭제**한다.
실데이터 파이프라인은 build_data.py 다. 이 파일은 거기에 손대지 않는다.

입력  : data/processed/frames.json  (path 가 이미 900x700 픽셀 좌표계다)
출력  : data/processed/buildings.mock.json

건물 수는 지역 면적에만 비례한다. "구미가 더 산업적이다" 같은 의미를
넣지 않는다 — 가상 데이터가 실제 통계처럼 읽히면 안 된다.

표준 라이브러리만 사용한다.
"""

import argparse
import json
import math
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "processed" / "frames.json"
OUT = ROOT / "data" / "processed" / "buildings.mock.json"

WARNING = (
    "가상 데이터. 실제 공장 위치가 아니다. "
    "팩토리온 실데이터로 교체 후 이 파일을 삭제할 것."
)

# 면적(px²) 당 건물 1개. 1px ≈ 278m 이므로 1px² ≈ 0.077km².
DENSITY = 180.0
MIN_N, MAX_N = 10, 120

# 클러스터 격자 간격. 지역이 크면 넓게 — 건물이 붙어 한 덩어리로 안 보이게.
SP_MIN, SP_MAX = 3.0, 6.0

# 격자 간격 대비 바닥 크기 / 겹 수(높이). (크기 하한, 상한, 높이 하한, 상한)
CLASSES = {
    "large":  (0.66, 0.86, 7, 13),   # 큰 공장동
    "medium": (0.44, 0.62, 4, 8),
    "small":  (0.26, 0.40, 2, 5),    # 낮은 창고
}


# ── 기하 (순수 파이썬) ──────────────────────────────────

def parse_ring(d):
    """frames.json 의 path 는 M/L/Z 절대좌표 단일 링이다. 숫자만 순서대로 읽는다."""
    nums = [float(t) for t in re.findall(r"-?\d*\.?\d+", d)]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def inside(x, y, ring):
    """ray casting. 점이 링 내부인가."""
    hit = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xc:
                hit = not hit
    return hit


def area_of(ring):
    """shoelace. px²."""
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def bbox_of(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def pick_interior(ring, rng, tries=400):
    """폴리곤 내부의 임의 지점. bbox 안에서 뽑아 판정 (rejection sampling)."""
    x0, y0, x1, y1 = bbox_of(ring)
    for _ in range(tries):
        x = rng.uniform(x0, x1)
        y = rng.uniform(y0, y1)
        if inside(x, y, ring):
            return x, y
    return None


# ── 배치 ────────────────────────────────────────────────

def fits(x, y, w, d, ring):
    """네 모서리 전부 내부여야 통과. 건물이 경계를 물면 땅 밖으로 떠 보인다."""
    return (inside(x, y, ring) and inside(x + w, y, ring)
            and inside(x, y - d, ring) and inside(x + w, y - d, ring))


def overlaps(a, placed):
    """이미 놓인 건물과 바닥이 겹치는가. 클러스터 중심은 서로 독립이라
    클러스터끼리 포개질 수 있어 여기서 한 번 걸러야 한다."""
    for b in placed:
        if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                and a["y"] - a["d"] < b["y"] and b["y"] - b["d"] < a["y"]):
            return True
    return False


def cluster(ring, center, want, sp, rng, placed):
    """클러스터 하나. 격자 + jitter 로 산업단지처럼 뭉쳐 배치한다.
    placed 에 통과한 건물을 직접 넣는다."""
    cx, cy = center
    side = max(2, math.ceil(math.sqrt(want)))
    # 대형 1~2개 + 중형 몇 개 + 소형 다수
    n_large = rng.randint(1, 2)
    n_medium = max(1, round(want * 0.25))
    kinds = (["large"] * n_large + ["medium"] * n_medium)
    kinds += ["small"] * max(0, want - len(kinds))
    rng.shuffle(kinds)

    cells = [(i, j) for i in range(side) for j in range(side)]
    rng.shuffle(cells)

    made = 0
    for kind, (i, j) in zip(kinds, cells):
        lo, hi, h_lo, h_hi = CLASSES[kind]
        w = sp * rng.uniform(lo, hi)
        # 정사각형만 나오지 않게. 격자 칸을 넘으면 옆 건물과 겹쳐 버려지므로 제한한다.
        d = min(w * rng.uniform(0.7, 1.25), sp * 0.88)
        # 격자 중심 + 흔들림. jitter 는 남는 여유의 절반까지만 — 겹치지 않는다.
        gx = cx + (i - (side - 1) / 2) * sp
        gy = cy + (j - (side - 1) / 2) * sp
        gx += rng.uniform(-1, 1) * max(0.0, sp - w) * 0.45
        gy += rng.uniform(-1, 1) * max(0.0, sp - d) * 0.45
        # x,y = 좌하단 (y 는 아래로 증가). 반올림한 값으로 판정해야
        # 출력 좌표 기준으로 내부가 보장된다.
        b = {
            "x": round(gx - w / 2, 1), "y": round(gy + d / 2, 1),
            "w": round(w, 2), "d": round(d, 2),
            "h": rng.randint(h_lo, h_hi),
        }
        if not fits(b["x"], b["y"], b["w"], b["d"], ring):
            continue
        if overlaps(b, placed):
            continue
        placed.append(b)
        made += 1
    return made


def build_region(ring, rng):
    area = area_of(ring)
    target = max(MIN_N, min(MAX_N, round(area / DENSITY)))
    sp = max(SP_MIN, min(SP_MAX, math.sqrt(area) / 18))
    n_clusters = max(2, min(4, 2 + target // 40))

    out = []
    # 클러스터 중심이 좁은 자락에 걸리면 격자가 거의 다 밖으로 나간다 →
    # 목표 개수에 못 미치면 중심을 다시 뽑아 몇 번 더 시도한다.
    for attempt in range(n_clusters * 4):
        if len(out) >= target:
            break
        c = pick_interior(ring, rng)
        if c is None:
            break
        want = max(3, round(target / n_clusters))
        cluster(ring, c, want, sp, rng, out)
    return out[:target]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=20260822,
                    help="난수 시드. 같은 시드면 같은 배치가 나온다.")
    args = ap.parse_args()

    data = json.loads(SRC.read_text(encoding="utf-8"))
    rng = random.Random(args.seed)

    buildings = {}
    for key, region in data["regions"].items():
        ring = parse_ring(region["path"])
        buildings[key] = build_region(ring, rng)

    OUT.write_text(
        json.dumps({"_WARNING": WARNING, "buildings": buildings},
                   ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")

    total = sum(len(v) for v in buildings.values())
    print(f"{OUT.relative_to(ROOT)}  ⚠ 가상 데이터")
    print(f"  지역 {len(buildings)}개 / 건물 {total}개 / seed {args.seed}")
    for key, v in sorted(buildings.items(), key=lambda kv: -len(kv[1])):
        print(f"    {key:11s} {len(v):4d}")


if __name__ == "__main__":
    main()
