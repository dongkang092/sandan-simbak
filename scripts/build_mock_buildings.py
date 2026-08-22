#!/usr/bin/env python3
"""⚠ 가상(mock) 건물 데이터 생성. 실제 공장 위치가 아니다 — 느낌 확인용 임시 파일.

팩토리온 실데이터를 확보하면 이 스크립트와 출력 파일을 **삭제**한다.
실데이터 파이프라인은 build_data.py 다. 이 파일은 거기에 손대지 않는다.
실데이터에 무엇이 있고 없는지는 CLAUDE.md "실데이터 스키마" 절에 정리돼 있다.

입력  : data/processed/frames.json  (path 가 이미 900x700 픽셀 좌표계다)
출력  : data/processed/buildings.mock.json

건물을 흩뿌리지 않는다. **클러스터 하나 = 업종 하나**이고, 그 업종을 상징하는
구성으로 세운다 (제강동+고로+굴뚝 / 팹+사무동 / 탱크팜+굴뚝 / 사일로 …).
구성은 INDUSTRIES 에 데이터로 적혀 있다.

각 클러스터는 **앵커 1채 + 부속 + 위성 다수** 구조다. 앵커(중심 대기업)와
위성(협력 중소)의 차이는 **크기와 높이로만** 표현한다 — 둘을 잇는 선은 그리지
않는다. 기업 간 협력 관계는 공개 데이터에 없다 (CLAUDE.md "연쇄 층").

가상 데이터는 MOCK_REGIONS 의 지역에만 만든다 (지금은 안동시 하나). 안동은
시험용 무대이고, 업종은 **경상북도 주요 업종을 골고루** 넣어 디자인을 확인한다 —
안동의 실제 업종 구성이 아니다. 실데이터에서 업종은 단지별 입주기업 업종명에서
온다 (경북 입주기업 현황 + 생산품 텍스트 사전).

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
    "가상 데이터. 실제 공장 위치도, 실제 산업단지도, 실제 업종 구성도 아니다. "
    "업종은 경북 주요 업종을 디자인 확인용으로 흩어 놓은 것이다. "
    "팩토리온·산단 경계 실데이터로 교체 후 이 파일을 삭제할 것."
)

# 가상 데이터를 만들 지역. frames.json 의 regions 키.
MOCK_REGIONS = ("andong",)

# 건물 치수의 기준 단위(px). 지역 크기에 비례시켜 어느 시군이든 같은 비율로 보이게
# 한다. 안동은 sqrt(면적)=141 → BASE≈4.1px. 아래 INDUSTRIES 의 숫자는 전부
# 이 단위의 배수다.
BASE_DIV = 34.0
BASE_MIN, BASE_MAX = 2.6, 5.2

# 클러스터 반경(부속·위성이 앉는 범위)과 클러스터 중심 간 최소 거리. BASE 배수.
# 산업단지는 필지가 붙어 있다 — 반경을 넓게 주면 건물이 흩어져 "단지"로 안 읽히고,
# detail 화면의 단지 바닥(모폴로지 닫기)도 하나로 붙지 않는다.
CLUSTER_R = 5.0
CENTER_GAP = 13.0

# 건물 사이 최소 간격(px). 상자가 맞붙으면 벽면이 이어져 한 덩어리로 읽힌다.
GAP = 1.0


def part(role, kind, n, w, d, h, label, row=False):
    """구성 요소 하나. w/d/h 는 BASE 배수.
    role  : anchor(중심 대기업) / prop(앵커 부속) / sat(협력 중소)
    kind  : box(상자) / cyl(원통 — 탱크·사일로·굴뚝·고로)
    row   : True 면 n 개를 일렬로 세운다 (사일로·탱크팜은 줄이 서야 읽힌다)
    """
    return {"role": role, "kind": kind, "n": n,
            "w": w, "d": d, "h": h, "label": label, "row": row}


# 경상북도 주요 업종. 순서대로 클러스터에 배정된다.
# 형태의 요점은 **실루엣이 서로 달라야 한다**는 것이다. rotateX 때문에 높이는
# 0.44배로 눌리므로(CLAUDE.md), 높이 차이는 과장해야 화면에서 구분된다.
INDUSTRIES = {
    "steel": {
        "name": "철강·1차금속", "where": "포항",
        # 아주 길고 낮은 제강·압연동 + 고로 + 굴뚝. 수평이 지배한다.
        "parts": [
            part("anchor", "box", 1, 4.2, 1.3, 1.0, "제강동"),
            part("prop", "box", 1, 3.2, 0.8, 0.7, "압연동"),
            part("prop", "cyl", 2, 0.9, 0.9, 3.4, "고로", row=True),
            part("prop", "cyl", 2, 0.3, 0.3, 4.8, "굴뚝"),
            part("sat", "box", 5, 0.8, 0.7, 0.6, "협력사"),
        ],
    },
    "electronics": {
        "name": "전자·영상음향", "where": "구미",
        # 거대한 단일 매스(팹) + 사무 타워. 덩어리 하나가 압도한다.
        "parts": [
            part("anchor", "box", 1, 3.0, 2.3, 1.7, "팹"),
            part("prop", "box", 2, 1.3, 0.9, 0.9, "부속동"),
            part("prop", "box", 1, 0.7, 0.6, 2.8, "사무동"),
            part("sat", "box", 6, 0.7, 0.6, 0.5, "협력사"),
        ],
    },
    "chemical": {
        "name": "화학·고무플라스틱", "where": "김천",
        # 탱크팜이 주인공. 낮은 원통 여러 개 + 아주 높은 굴뚝 + 파이프랙.
        "parts": [
            part("anchor", "box", 1, 1.6, 1.2, 1.1, "반응동"),
            part("prop", "cyl", 6, 1.0, 1.0, 1.0, "저장탱크", row=True),
            part("prop", "cyl", 1, 0.28, 0.28, 5.4, "굴뚝"),
            part("prop", "box", 1, 3.0, 0.18, 0.4, "파이프랙"),
            part("sat", "box", 4, 0.7, 0.6, 0.5, "협력사"),
        ],
    },
    "auto": {
        "name": "자동차부품", "where": "경산·영천",
        # 중간 크기 프레스·조립동이 여러 채. 비슷한 덩어리의 반복.
        "parts": [
            part("anchor", "box", 1, 2.4, 1.5, 0.9, "프레스동"),
            part("prop", "box", 2, 1.7, 1.2, 0.7, "조립동"),
            part("sat", "box", 6, 0.9, 0.8, 0.6, "협력사"),
        ],
    },
    "bio": {
        "name": "바이오·백신", "where": "안동",
        # 작고 정갈한 고층 + 저온탱크. 바닥은 작은데 키가 크다.
        "parts": [
            part("anchor", "box", 1, 1.3, 1.1, 2.2, "생산동"),
            part("prop", "box", 1, 1.0, 0.7, 1.6, "연구동"),
            part("prop", "cyl", 3, 0.45, 0.45, 1.1, "저온탱크", row=True),
            part("sat", "box", 4, 0.6, 0.5, 0.7, "협력사"),
        ],
    },
    "food": {
        "name": "식료품", "where": "안동·영주",
        # 낮은 가공동 + 사일로 줄. 실루엣이 톱니처럼 뾰족하다.
        "parts": [
            part("anchor", "box", 1, 1.8, 1.1, 0.6, "가공동"),
            part("prop", "cyl", 5, 0.55, 0.55, 2.0, "사일로", row=True),
            part("prop", "box", 1, 1.2, 0.8, 0.5, "저장동"),
            part("sat", "box", 5, 0.7, 0.6, 0.45, "협력사"),
        ],
    },
}

# 화면에서 높이만 cos(64°)≈0.44 배로 눌린다 (detail.html #tilt). 아래 INDUSTRIES
# 의 높이 값은 눌리기 전 기준이라, 눌린 뒤에도 실루엣이 읽히도록 한 번 키운다.
# **틸트 각도를 바꾸면 이 값도 다시 본다.** 0.62/0.44 ≈ 1.4 가 기준선이다.
HEIGHT_GAIN = 1.45

JITTER = 0.14        # 치수 흔들림 (±비율). 0 이면 복제품처럼 보인다
SAT_JITTER = 0.35    # 위성은 더 들쭉날쭉해야 한다
TRIES = 120          # 위치 rejection sampling 횟수


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
    """이미 놓인 건물과 바닥이 GAP 안으로 접근하는가. 원통도 바닥은 정사각형으로
    본다 — 이 투영에서는 원통이 사각형 자리를 차지한다."""
    ax0, ax1 = a["x"] - GAP, a["x"] + a["w"] + GAP
    ay0, ay1 = a["y"] - a["d"] - GAP, a["y"] + GAP
    for b in placed:
        if (ax0 < b["x"] + b["w"] and b["x"] < ax1
                and ay0 < b["y"] and b["y"] - b["d"] < ay1):
            return True
    return False


def make(spec, base, rng, cid, jitter):
    """치수만 정한 건물 하나 (위치는 아직 없다)."""
    j = lambda: 1.0 + rng.uniform(-jitter, jitter)
    w = max(0.6, spec["w"] * base * j())
    d = max(0.6, spec["d"] * base * j())
    if spec["kind"] == "cyl":
        d = w                      # 원통은 바닥이 정사각형(지름)이다
    h = max(1.2, spec["h"] * base * HEIGHT_GAIN * j())
    return {"w": round(w, 2), "d": round(d, 2), "h": round(h, 2),
            "shape": spec["kind"], "role": spec["role"],
            "part": spec["label"], "clusterId": cid}


def try_put(b, x, y, ring, placed):
    """좌하단 (x, y) 에 놓아 본다. 반올림한 좌표로 판정해야 출력 기준으로 맞다."""
    b = dict(b, x=round(x, 1), y=round(y, 1))
    if not fits(b["x"], b["y"], b["w"], b["d"], ring):
        return None
    if overlaps(b, placed):
        return None
    placed.append(b)
    return b


def scatter(b, center, radius, ring, rng, placed):
    """클러스터 반경 안에 아무 데나. 중심 쪽이 조금 더 촘촘하게 (sqrt 분포)."""
    cx, cy = center
    for _ in range(TRIES):
        a = rng.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(rng.random())
        if try_put(b, cx + r * math.cos(a) - b["w"] / 2,
                   cy + r * math.sin(a) + b["d"] / 2, ring, placed):
            return True
    return False


def put_row(items, center, radius, ring, rng, placed):
    """n 개를 일렬로. 사일로·탱크팜은 줄이 서 있어야 시설로 읽힌다.
    줄을 세울 자리를 못 찾으면 흩뿌리는 것으로 물러난다."""
    cx, cy = center
    pitch = max(i["w"] for i in items) + GAP * 1.6
    span = pitch * len(items)
    for _ in range(TRIES):
        a = rng.uniform(0, 2 * math.pi)
        r = radius * rng.uniform(0.35, 1.0)
        x0 = cx + r * math.cos(a) - span / 2
        y0 = cy + r * math.sin(a)
        # 줄 전체가 들어가는지 먼저 확인한다 — 절반만 서면 더 어색하다.
        probe = [dict(it, x=round(x0 + k * pitch, 1), y=round(y0, 1))
                 for k, it in enumerate(items)]
        if all(fits(p["x"], p["y"], p["w"], p["d"], ring) for p in probe) \
                and not any(overlaps(p, placed) for p in probe):
            placed.extend(probe)
            return True
    return all(scatter(it, center, radius, ring, rng, placed) for it in items)


def build_cluster(ring, center, industry, base, rng, cid, placed):
    """클러스터 하나. 앵커를 중심에 세우고 부속·위성을 그 주위에 앉힌다.
    앵커가 못 서면 이 클러스터는 포기한다 (좁은 자락에 걸린 경우)."""
    spec = INDUSTRIES[industry]
    radius = CLUSTER_R * base
    anchor_spec = next(p for p in spec["parts"] if p["role"] == "anchor")
    cx, cy = center
    # try_put 은 좌표가 붙은 **새 dict** 를 준다. 그걸 받아야 cx/cy 를 읽을 수 있다.
    anchor = try_put(make(anchor_spec, base, rng, cid, JITTER),
                     cx, cy, ring, placed)
    if anchor is None:
        return None

    for p in spec["parts"]:
        if p["role"] == "anchor":
            continue
        jit = SAT_JITTER if p["role"] == "sat" else JITTER
        items = [make(p, base, rng, cid, jit) for _ in range(p["n"])]
        if p["row"] and len(items) > 1:
            put_row(items, center, radius, ring, rng, placed)
        else:
            for it in items:
                scatter(it, center, radius, ring, rng, placed)
    return anchor


def pick_centers(ring, n, gap, rng):
    """서로 gap 이상 떨어진 클러스터 중심 n 개. 못 채우면 있는 만큼만 준다."""
    centers = []
    for _ in range(n * 200):
        if len(centers) >= n:
            break
        c = pick_interior(ring, rng)
        if c is None:
            break
        if all(math.dist(c, o) >= gap for o in centers):
            centers.append(c)
    return centers


def build_region(ring, key, rng):
    """지역 하나. 업종 목록을 순서대로 클러스터에 배정한다."""
    base = max(BASE_MIN, min(BASE_MAX, math.sqrt(area_of(ring)) / BASE_DIV))
    keys = list(INDUSTRIES)
    centers = pick_centers(ring, len(keys), CENTER_GAP * base, rng)

    placed, clusters = [], {}
    n = 0
    for center, ind in zip(centers, keys):
        cid = f"{key}-{n + 1}"
        before = len(placed)
        anchor = build_cluster(ring, center, ind, base, rng, cid, placed)
        if anchor is None:
            continue
        n += 1
        members = placed[before:]
        clusters[cid] = {
            "region": key,
            "industry": ind,
            "industryName": INDUSTRIES[ind]["name"],
            # 점을 찍는 자리는 앵커 위다 — 클러스터의 무게중심이 아니라
            # 사람이 "여기가 그 단지"라고 보는 지점이다.
            "cx": round(anchor["x"] + anchor["w"] / 2, 1),
            "cy": round(anchor["y"] - anchor["d"] / 2, 1),
            "count": len(members),
            "area": round(sum(b["w"] * b["d"] for b in members), 1),
        }
    return placed, clusters, base


def report(buildings, clusters):
    """INDUSTRIES 를 손본 뒤 실제로 어떤 구성이 나왔는지 확인하는 용도."""
    print("  업종            앵커 바닥(w×d)  최고 높이  요소  실루엣(h*.44/w)")
    for cid, c in clusters.items():
        bs = [b for v in buildings.values() for b in v if b["clusterId"] == cid]
        a = next(b for b in bs if b["role"] == "anchor")
        tall = max(bs, key=lambda b: b["h"])
        print(f"  {c['industryName']:14s} {a['w']:5.1f}×{a['d']:4.1f}"
              f"    {tall['h']:6.1f}  {len(bs):4d}"
              f"   {a['h'] * 0.44 / a['w']:.2f}  ({tall['part']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=20260822,
                    help="난수 시드. 같은 시드면 같은 배치가 나온다.")
    ap.add_argument("--stats", action="store_true",
                    help="클러스터별 구성·치수를 찍는다.")
    args = ap.parse_args()

    data = json.loads(SRC.read_text(encoding="utf-8"))
    rng = random.Random(args.seed)

    buildings, clusters = {}, {}
    for key in MOCK_REGIONS:
        ring = parse_ring(data["regions"][key]["path"])
        placed, found, base = build_region(ring, key, rng)
        buildings[key] = placed
        clusters.update(found)
        print(f"  {key}: BASE {base:.1f}px")

    if args.stats:
        report(buildings, clusters)

    OUT.write_text(
        json.dumps({"_WARNING": WARNING, "clusters": clusters,
                    "buildings": buildings},
                   ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")

    total = sum(len(v) for v in buildings.values())
    print(f"{OUT.relative_to(ROOT)}  ⚠ 가상 데이터")
    print(f"  지역 {len(buildings)}개 / 건물 {total}개 / "
          f"클러스터 {len(clusters)}개 / seed {args.seed}")
    for cid, c in clusters.items():
        print(f"    {cid:11s} {c['industryName']:14s} 요소 {c['count']:3d}")


if __name__ == "__main__":
    main()
