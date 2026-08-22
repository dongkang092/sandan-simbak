#!/usr/bin/env python3
"""⚠ 가상(mock) 건물 데이터 생성. 실제 공장 위치가 아니다 — 느낌 확인용 임시 파일.

팩토리온(전국산업단지및공장정보표준데이터) 실데이터를 확보하면
이 스크립트와 출력 파일(data/processed/buildings.mock.json) 을 **삭제**한다.
실데이터 파이프라인은 build_data.py 다. 이 파일은 거기에 손대지 않는다.

입력  : data/processed/frames.json  (path 가 이미 900x700 픽셀 좌표계다)
출력  : data/processed/buildings.mock.json

출력에는 건물 목록과 함께 **클러스터 요약**(clusters)이 들어간다. 건물을 격자로
뭉쳐 놓는 단위가 이미 클러스터이므로, 그 무리의 무게중심·개수·바닥면적을
그대로 적어 준다. scripts/build_mock_clusters.py 가 이 좌표를 읽어
clusters.mock.json (위기도 시계열) 을 만든다.

가상 데이터는 **MOCK_REGIONS 의 지역에만** 만든다 (지금은 안동시 하나). 22개 시군구
전부에 깔면 파일이 커지고 지도가 점으로 뒤덮여, 느낌을 보는 목적에도 오히려 방해가
된다. 실데이터가 오면 이 스크립트 자체가 사라지므로 범위를 넓힐 이유도 없다.

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
    "가상 데이터. 실제 공장 위치도, 실제 산업단지 경계도 아니다. "
    "팩토리온 실데이터로 교체 후 이 파일을 삭제할 것."
)

# 가상 데이터를 만들 지역. frames.json 의 regions 키. 여기 없는 지역은
# 건물도 클러스터도 없다 — 전체 지도에서 점이 안동시에만 찍힌다.
MOCK_REGIONS = ("andong",)

# 잘라내기(out[:target]) 후 이만큼도 남지 않은 무리는 클러스터로 보지 않는다.
# 건물 한두 채에 점을 찍으면 지도에서 산업단지가 아니라 먼지로 읽힌다.
MIN_MEMBERS = 3

# 무게중심이 sp(격자 간격) 의 이 배수 안에 있는 무리는 한 클러스터로 합친다.
# 배치는 중심을 여러 번 다시 뽑기 때문에(build_region) 같은 자리에 두세 무리가
# 겹쳐 앉는다 — 합치지 않으면 전체 지도에서 점 두세 개가 한 점처럼 포개진다.
MERGE_SP = 2.0

# 면적(px²) 당 건물 1개. 1px ≈ 278m 이므로 1px² ≈ 0.077km².
DENSITY = 180.0
MIN_N, MAX_N = 10, 120

# 클러스터 격자 간격. 건물 크기는 전부 이 값의 비율로 정하므로
# sp 를 키우면 건물이 같은 비율로 커진다. 땅 폭이 90~200px 인데
# 예전 sp(3~6)로는 건물이 1~4px 밖에 안 돼 화면에서 읽히지 않았다.
SP_MIN, SP_MAX = 6.5, 13.0
SP_DIV = 8.0        # sp = sqrt(면적) / SP_DIV, 위 범위로 clamp

# 건물 사이 최소 간격(px). 격자 여유와 겹침 판정 양쪽에서 이 값을 뺀다 —
# 상자가 맞붙으면 벽면이 이어져 한 덩어리로 읽힌다.
GAP = 1.0

# 건물 종류. w = sp 의 비율, d = w 의 비율, h = min(w,d) 의 배수.
# 높이를 **바닥 대비 비율**로 주는 게 핵심이다. 절대값으로 주면 전부 비슷한
# 키가 되어 아파트 단지처럼 보인다. 화면에서는 rotateX 로 높이만 cos(52°)≈0.62
# 배 눌리므로, 실루엣 비율은 (h × 0.62) / w 로 읽힌다.
#   hall  : 큰 공장동. 넓고 낮다 (실루엣 0.25~0.4).
#   shed  : 작은 창고. 다수. 낮다 (0.55~0.9).
#   block : 중간 (0.8~1.2).
#   tower : 좁고 높다. 전체의 10~15% 만 (1.8~2.8).
#            (w_lo, w_hi, dw_lo, dw_hi, h_lo, h_hi)
CLASSES = {
    "hall":  (0.62, 0.90, 0.40, 0.75, 0.75, 1.15),
    "shed":  (0.26, 0.42, 0.55, 1.10, 1.15, 1.75),
    "block": (0.44, 0.60, 0.70, 1.15, 1.40, 2.10),
    "tower": (0.20, 0.30, 0.85, 1.25, 3.00, 4.60),
}
# 배치 후 실현 비율은 이것과 다르다 — 바닥이 큰 hall 이 경계/겹침 판정에서
# 더 많이 탈락하고 tower 가 더 많이 살아남는다. tower 는 실현 12% 를 노려
# 낮게 잡는다. 바꿨으면 --stats 로 실현 비율을 확인할 것.
MIX = {"tower": 0.11, "hall": 0.15, "block": 0.22}   # 나머지는 shed
H_MIN = 2.0   # 아무리 낮아도 상자로 보이게 하는 하한


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
    """이미 놓인 건물과 바닥이 GAP 안으로 접근하는가. 클러스터 중심은 서로
    독립이라 클러스터끼리 포개질 수 있어 여기서 한 번 걸러야 한다."""
    ax0, ax1 = a["x"] - GAP, a["x"] + a["w"] + GAP
    ay0, ay1 = a["y"] - a["d"] - GAP, a["y"] + GAP
    for b in placed:
        if (ax0 < b["x"] + b["w"] and b["x"] < ax1
                and ay0 < b["y"] and b["y"] - b["d"] < ay1):
            return True
    return False


def kind_mix(want, rng):
    """종류를 비율대로 섞은 리스트. tower 는 MIX 비율만큼만 — 좁고 높은 게
    많아지면 특징이 아니라 기본값이 된다."""
    kinds = []
    for kind, frac in MIX.items():
        kinds += [kind] * round(want * frac)
    kinds += ["shed"] * max(0, want - len(kinds))
    rng.shuffle(kinds)
    return kinds[:want]


def cluster(ring, center, want, sp, rng, placed, cid):
    """클러스터 하나. 격자 + jitter 로 산업단지처럼 뭉쳐 배치한다.
    placed 에 통과한 건물을 직접 넣는다. cid 는 임시 id — 배치가 끝난 뒤
    collect_clusters() 에서 최종 id(gumi-1 …) 로 다시 붙인다."""
    cx, cy = center
    kinds = kind_mix(want, rng)
    # 칸을 개수보다 넉넉히 잡아 격자를 다 채우지 않는다 — 꽉 채우면
    # 블록처럼 규칙적으로 보이고, 경계에 걸린 칸 때문에 개수도 못 채운다.
    side = max(2, math.ceil(math.sqrt(want * 1.4)))
    cells = [(i, j) for i in range(side) for j in range(side)]
    rng.shuffle(cells)

    made = 0
    for kind, (i, j) in zip(kinds, cells):
        w_lo, w_hi, dw_lo, dw_hi, h_lo, h_hi = CLASSES[kind]
        # 한 칸(sp)에서 GAP 을 뺀 만큼만 쓴다 → 이웃 칸과 최소 간격이 남는다.
        room = max(1.0, sp - GAP)
        w = min(room, sp * rng.uniform(w_lo, w_hi))
        # 정사각형만 나오지 않게 깊이를 따로 흔든다.
        d = min(room, w * rng.uniform(dw_lo, dw_hi))
        # 높이는 바닥의 짧은 변 기준. hall 은 1배 미만, tower 는 3~4배.
        h = max(H_MIN, min(w, d) * rng.uniform(h_lo, h_hi))
        # 격자 중심 + 흔들림. jitter 는 칸에 남는 여유의 절반까지만.
        gx = cx + (i - (side - 1) / 2) * sp
        gy = cy + (j - (side - 1) / 2) * sp
        gx += rng.uniform(-1, 1) * max(0.0, sp - w - GAP) * 0.5
        gy += rng.uniform(-1, 1) * max(0.0, sp - d - GAP) * 0.5
        # x,y = 좌하단 (y 는 아래로 증가). 반올림한 값으로 판정해야
        # 출력 좌표 기준으로 내부가 보장된다.
        b = {
            "x": round(gx - w / 2, 1), "y": round(gy + d / 2, 1),
            "w": round(w, 2), "d": round(d, 2),
            "h": round(h, 2),
            "clusterId": cid,
        }
        b["_kind"] = kind   # 통계용. 출력 직전에 지운다.
        if not fits(b["x"], b["y"], b["w"], b["d"], ring):
            continue
        if overlaps(b, placed):
            continue
        placed.append(b)
        made += 1
    return made


def build_region(ring, rng, key):
    area = area_of(ring)
    target = max(MIN_N, min(MAX_N, round(area / DENSITY)))
    sp = max(SP_MIN, min(SP_MAX, math.sqrt(area) / SP_DIV))
    n_clusters = max(2, min(4, 2 + target // 40))

    out = []
    seq = 0
    # 클러스터 중심이 좁은 자락에 걸리면 격자가 거의 다 밖으로 나간다 →
    # 목표 개수에 못 미치면 중심을 다시 뽑아 몇 번 더 시도한다.
    for attempt in range(n_clusters * 6):
        if len(out) >= target:
            break
        c = pick_interior(ring, rng)
        if c is None:
            break
        want = max(3, round(target / n_clusters))
        seq += 1
        cluster(ring, c, want, sp, rng, out, f"{key}#{seq}")
    return out[:target], sp


def merge_near(groups, dist):
    """무게중심이 dist 안에 있는 무리를 단일 연결(single-linkage)로 합친다.
    무리 수가 지역당 열 몇 개라 O(n²) 반복으로 충분하다."""
    def cen(g):
        return (sum(b["x"] + b["w"] / 2 for b in g) / len(g),
                sum(b["y"] - b["d"] / 2 for b in g) / len(g))

    groups = [list(g) for g in groups]
    merged = True
    while merged:
        merged = False
        cs = [cen(g) for g in groups]
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if math.dist(cs[i], cs[j]) < dist:
                    groups[i] += groups[j]
                    del groups[j]
                    merged = True
                    break
            if merged:
                break
    return groups


def collect_clusters(key, buildings, sp):
    """클러스터 요약 + 최종 id. 씨앗 중심이 아니라 **살아남은 건물의 무게중심**을
    쓴다 — 경계·겹침 판정과 잘라내기로 배치가 한쪽으로 치우치므로, 전체 지도의
    점이 건물 무리와 같은 자리에 찍히려면 결과를 보고 정해야 한다.

    MIN_MEMBERS 미달 무리는 버린다. 그 건물들은 임시 id 를 그대로 들고 있으므로
    호출한 쪽에서 걸러낸다 (반환된 dict 에 없는 clusterId).
    """
    groups = {}
    for b in buildings:
        groups.setdefault(b["clusterId"], []).append(b)

    keep = merge_near(groups.values(), sp * MERGE_SP)
    keep = [g for g in keep if len(g) >= MIN_MEMBERS]
    keep.sort(key=lambda g: -len(g))

    out = {}
    for n, g in enumerate(keep, start=1):
        cid = f"{key}-{n}"
        for b in g:
            b["clusterId"] = cid
        # 건물 바닥 중심의 평균. y 는 아래로 증가하고 바닥은 (y-d)~y 구간이다.
        out[cid] = {
            "region": key,
            "cx": round(sum(b["x"] + b["w"] / 2 for b in g) / len(g), 1),
            "cy": round(sum(b["y"] - b["d"] / 2 for b in g) / len(g), 1),
            "count": len(g),
            "area": round(sum(b["w"] * b["d"] for b in g), 1),
        }
    return out


def report(buildings):
    """CLASSES / MIX 를 손본 뒤 실제로 어떤 분포가 나왔는지 확인하는 용도."""
    allb = [b for v in buildings.values() for b in v]
    n = len(allb)
    def q(vals, p):
        vals = sorted(vals)
        return vals[int(p * (len(vals) - 1))]
    print("  종류      개수   비율   바닥w(중앙)  높이h(중앙)  실루엣 h*.62/w")
    for kind in ("hall", "shed", "block", "tower"):
        g = [b for b in allb if b["_kind"] == kind]
        if not g:
            continue
        sil = [b["h"] * 0.62 / b["w"] for b in g]
        print(f"    {kind:6s} {len(g):5d} {100*len(g)/n:5.1f}%"
              f"      {q([b['w'] for b in g], .5):5.1f}"
              f"      {q([b['h'] for b in g], .5):6.1f}"
              f"       {q(sil, .5):.2f}")
    ws = [b["w"] for b in allb]
    hs = [b["h"] for b in allb]
    print(f"  바닥 w  p05/p50/p95 = {q(ws,.05):.1f} / {q(ws,.5):.1f} / {q(ws,.95):.1f}")
    print(f"  높이 h  p05/p50/p95 = {q(hs,.05):.1f} / {q(hs,.5):.1f} / {q(hs,.95):.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=20260822,
                    help="난수 시드. 같은 시드면 같은 배치가 나온다.")
    ap.add_argument("--stats", action="store_true",
                    help="종류별 실현 비율 / 바닥·높이 분포를 찍는다.")
    args = ap.parse_args()

    data = json.loads(SRC.read_text(encoding="utf-8"))
    rng = random.Random(args.seed)

    buildings = {}
    clusters = {}
    for key in MOCK_REGIONS:
        region = data["regions"][key]
        ring = parse_ring(region["path"])
        placed, sp = build_region(ring, rng, key)
        found = collect_clusters(key, placed, sp)
        clusters.update(found)
        # 클러스터에 못 든 낙오 건물은 버린다 — 소속 없는 clusterId 가 남으면
        # clusters.mock.json 과 짝이 맞지 않는다.
        buildings[key] = [b for b in placed if b["clusterId"] in found]

    if args.stats:
        report(buildings)

    # _kind 는 스키마에 없다. 출력 전에 제거한다.
    for v in buildings.values():
        for b in v:
            b.pop("_kind", None)

    OUT.write_text(
        json.dumps({"_WARNING": WARNING, "clusters": clusters,
                    "buildings": buildings},
                   ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")

    total = sum(len(v) for v in buildings.values())
    print(f"{OUT.relative_to(ROOT)}  ⚠ 가상 데이터")
    print(f"  지역 {len(buildings)}개 / 건물 {total}개 / "
          f"클러스터 {len(clusters)}개 / seed {args.seed}")
    for key, v in sorted(buildings.items(), key=lambda kv: -len(kv[1])):
        n = sum(1 for c in clusters.values() if c["region"] == key)
        print(f"    {key:11s} 건물 {len(v):4d}  클러스터 {n}")


if __name__ == "__main__":
    main()
