#!/usr/bin/env python3
"""경북 시군구 경계 → 화면용 SVG path + 심박 프레임 생성.

표준 라이브러리만 사용한다. shapely/numpy/geopandas 불필요.

입력  : data/geo/hangjeongdong_20260701.geojson  (행정동 경계, 전국)
출력  : data/processed/frames.json

경계 원본은 용량이 커서 git에 넣지 않는다. 없으면 아래로 받는다:

  curl -sL -o data/geo/hangjeongdong_20260701.geojson \
    https://raw.githubusercontent.com/vuski/admdongkor/master/ver20260701/HangJeongDong_ver20260701.geojson

출처: https://github.com/vuski/admdongkor (2026-07-01 기준)

현재 frames 값은 난수다. 한전 실데이터 확보 후 이 스크립트의
build_frames() 만 교체하면 프론트엔드는 수정 없이 동작한다.
"""

import argparse
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO_SRC = ROOT / "data" / "geo" / "hangjeongdong_20260701.geojson"
OUT = ROOT / "data" / "processed" / "frames.json"

SIDO = "경상북도"

# SVG 좌표계 (CLAUDE.md 고정값)
W, H = 900, 700
PAD = 34

# 울릉군은 본토에서 멀어 인셋으로 빼낸다. (x, y, 한 변 길이)
INSET = {"key": "ulleung", "x": 742, "y": 44, "size": 108}

# 시계열 범위 — 한전 데이터 가용 구간과 동일하게 맞춰둔다.
MONTH_START = (2006, 1)
MONTH_END = (2025, 6)

# 실데이터를 우선 확보할 지역. 나머지는 hasData=false 로 회색 처리한다.
SEEDED = {"gumi", "pohang", "gyeongju", "andong", "gimcheon", "gyeongsan"}

# 시군구명 → 영문 키. 포항 남/북구는 하나로 합친다.
KEYS = {
    "포항시남구": "pohang", "포항시북구": "pohang",
    "경주시": "gyeongju", "김천시": "gimcheon", "안동시": "andong",
    "구미시": "gumi", "영주시": "yeongju", "영천시": "yeongcheon",
    "상주시": "sangju", "문경시": "mungyeong", "경산시": "gyeongsan",
    "의성군": "uiseong", "청송군": "cheongsong", "영양군": "yeongyang",
    "영덕군": "yeongdeok", "청도군": "cheongdo", "고령군": "goryeong",
    "성주군": "seongju", "칠곡군": "chilgok", "예천군": "yecheon",
    "봉화군": "bonghwa", "울진군": "uljin", "울릉군": "ulleung",
}

LABELS = {
    "pohang": "포항시", "gyeongju": "경주시", "gimcheon": "김천시",
    "andong": "안동시", "gumi": "구미시", "yeongju": "영주시",
    "yeongcheon": "영천시", "sangju": "상주시", "mungyeong": "문경시",
    "gyeongsan": "경산시", "uiseong": "의성군", "cheongsong": "청송군",
    "yeongyang": "영양군", "yeongdeok": "영덕군", "cheongdo": "청도군",
    "goryeong": "고령군", "seongju": "성주군", "chilgok": "칠곡군",
    "yecheon": "예천군", "bonghwa": "봉화군", "uljin": "울진군",
    "ulleung": "울릉군",
}


# ── 기하 ────────────────────────────────────────────────

def rings_of(geom):
    """Polygon / MultiPolygon 에서 외곽 링만 뽑는다 (내부 구멍은 버린다)."""
    t = geom["type"]
    if t == "Polygon":
        return [geom["coordinates"][0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def bbox(rings):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return min(xs), min(ys), max(xs), max(ys)


def make_projector(rings, w, h, pad):
    """경위도 → 픽셀. 단일 도(道) 범위라 정거원통도법 + 위도 보정으로 충분하다."""
    lon0, lat0, lon1, lat1 = bbox(rings)
    kx = math.cos(math.radians((lat0 + lat1) / 2))  # 경도 1도의 실제 폭 보정

    span_x = (lon1 - lon0) * kx
    span_y = lat1 - lat0
    scale = min((w - 2 * pad) / span_x, (h - 2 * pad) / span_y)

    # 남는 공간만큼 가운데로 밀어준다
    off_x = (w - span_x * scale) / 2
    off_y = (h - span_y * scale) / 2

    def project(lon, lat):
        x = (lon - lon0) * kx * scale + off_x
        y = (lat1 - lat) * scale + off_y  # 화면 y축은 아래로 증가
        return x, y

    return project


def dissolve(rings, quant=7):
    """인접 폴리곤을 병합해 외곽 링만 남긴다. shapely 없이 순수 파이썬.

    원리: 같은 시군구 안에서 맞닿은 두 행정동은 경계선을 **정확히 같은
    좌표로 공유**한다. 따라서 모든 변(edge)을 세어 두 번 이상 나온 변은
    내부 경계이므로 버리고, 한 번만 나온 변을 이어 붙이면 시군구 외곽선이
    된다.

    좌표가 정확히 일치하지 않는 데이터에서는 상쇄가 일어나지 않는다.
    그 경우 None을 반환하고 호출부가 원본 링을 그대로 쓰게 한다.
    """
    def q(pt):
        return (round(pt[0], quant), round(pt[1], quant))

    count = {}
    for ring in rings:
        pts = [q(p) for p in ring]
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            if a == b:
                continue
            count[(a, b) if a <= b else (b, a)] = \
                count.get((a, b) if a <= b else (b, a), 0) + 1

    total = len(count)
    boundary = [e for e, c in count.items() if c == 1]
    if not boundary:
        return None
    # 상쇄가 거의 없으면 좌표 불일치로 보고 포기한다.
    if len(boundary) > total * 0.98 and len(rings) > 1:
        return None

    # 변들을 이어 붙여 닫힌 링으로 복원한다.
    adj = {}
    for a, b in boundary:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    used = set()
    out = []
    for start in list(adj):
        if start in used:
            continue
        ring = [start]
        used.add(start)
        cur = start
        while True:
            nxt = None
            for cand in adj.get(cur, ()):
                if cand not in used:
                    nxt = cand
                    break
            if nxt is None:
                break
            ring.append(nxt)
            used.add(nxt)
            cur = nxt
        if len(ring) >= 4:
            out.append([list(p) for p in ring])
    return out or None


def simplify(points, tol):
    """Douglas-Peucker. 픽셀 좌표 기준."""
    if len(points) < 3:
        return points

    def perp(p, a, b):
        (px, py), (ax, ay), (bx, by) = p, a, b
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        worst, idx = tol, -1
        for k in range(i + 1, j):
            d = perp(points[k], points[i], points[j])
            if d > worst:
                worst, idx = d, k
        if idx != -1:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for p, k in zip(points, keep) if k]


def to_path(rings_px, tol, min_pts=4):
    """픽셀 링 목록 → SVG path 문자열. 링마다 M...Z 서브패스."""
    parts = []
    for ring in rings_px:
        pts = simplify(ring, tol)
        if len(pts) < min_pts:
            continue
        head = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
        body = "".join(f"L{x:.1f},{y:.1f}" for x, y in pts[1:])
        parts.append(head + body + "Z")
    return "".join(parts)


def ring_centroid(ring):
    """단일 링의 면적과 무게중심. 면적은 부호 없는 값."""
    a = 0.0
    cx = cy = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-9:
        return 0.0, None
    return abs(a), (cx / (6 * a), cy / (6 * a))


def dominant_rings(rings, min_ratio=0.01):
    """가장 큰 링 면적의 min_ratio 이상인 링만 남긴다.

    울릉군 인셋에서 쓴다. 울릉군은 울릉도(경도 130.8)와 독도(경도 131.87)를
    함께 포함하는데, 둘의 경도차가 1도(약 90km)라 같은 박스에 맞추면
    울릉도가 10픽셀 이하로 찌그러진다. 이 배율에서 독도는 1픽셀도 되지
    않으므로 인셋에서는 제외한다 — 축척상의 렌더링 판단이다.
    """
    areas = [(ring_centroid(r)[0], r) for r in rings]
    if not areas:
        return []
    cap = max(a for a, _ in areas)
    return [r for a, r in areas if a >= cap * min_ratio]


def centroid(rings_px):
    """모든 링의 면적 가중 무게중심.

    행정동을 기하적으로 병합하지 않고 모으기 때문에, 링 하나만 보면
    '가장 큰 행정동'의 중심이 나온다. 시군구 전체 중심을 얻으려면
    모든 링을 면적으로 가중해 평균해야 한다.
    """
    total = 0.0
    sx = sy = 0.0
    for ring in rings_px:
        area, c = ring_centroid(ring)
        if c is None:
            continue
        total += area
        sx += c[0] * area
        sy += c[1] * area
    if total < 1e-9:
        return 0.0, 0.0
    return sx / total, sy / total


# ── 시계열 ──────────────────────────────────────────────

def month_list(start, end):
    (y0, m0), (y1, m1) = start, end
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def build_frames(key, months, rng):
    """난수 심박. 실데이터가 오면 이 함수만 교체한다.

    아직 진짜 값이 아니지만, 지역마다 성격이 다르게 보이도록
    완만한 추세 + 계절성 + 잡음으로 만든다. UI 판단에는 충분하다.
    """
    n = len(months)
    drift = rng.uniform(-0.45, 0.10)          # 장기 추세 (대체로 하락)
    season_amp = rng.uniform(0.04, 0.14)      # 계절성 진폭
    season_phase = rng.uniform(0, 2 * math.pi)
    base_size = rng.uniform(0.25, 1.0)
    noise = rng.uniform(0.01, 0.05)

    frames = []
    for i in range(n):
        t = i / max(1, n - 1)
        season = season_amp * math.sin(2 * math.pi * (i / 12) + season_phase)
        rate = 1.0 + drift * t + season + rng.gauss(0, noise)
        size = base_size * (1.0 + 0.5 * drift * t) + season * 0.3
        irr = min(1.0, max(0.0, abs(rng.gauss(0, 0.12)) + 0.45 * t * abs(drift)))
        frames.append({
            "rate": round(max(0.35, rate), 3),
            "size": round(min(1.0, max(0.02, size)), 3),
            "irr": round(irr, 3),
        })
    return frames


# ── 조립 ────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-data", action="store_true",
                    help="모든 지역에 hasData=true (개발용)")
    ap.add_argument("--tol", type=float, default=0.7,
                    help="단순화 허용오차(픽셀)")
    ap.add_argument("--no-dissolve", action="store_true",
                    help="시군구 병합 없이 행정동 경계를 그대로 노출")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    if not GEO_SRC.exists():
        raise SystemExit(
            f"경계 파일이 없습니다: {GEO_SRC}\n"
            "모듈 docstring의 curl 명령으로 먼저 받으세요."
        )

    print(f"경계 읽기: {GEO_SRC.name}")
    fc = json.loads(GEO_SRC.read_text())

    # 시군구별로 행정동 링을 모은다. 별도의 기하 병합(dissolve) 없이
    # 서브패스로 이어붙이면 fill 렌더링 결과가 동일하다.
    grouped = {}
    for feat in fc["features"]:
        p = feat["properties"]
        if p["sidonm"] != SIDO:
            continue
        key = KEYS.get(p["sggnm"])
        if key is None:
            print(f"  ! 알 수 없는 시군구: {p['sggnm']}")
            continue
        grouped.setdefault(key, []).extend(rings_of(feat["geometry"]))

    print(f"시군구 {len(grouped)}개, 링 {sum(len(v) for v in grouped.values())}개")

    inset_key = INSET["key"]
    mainland = {k: v for k, v in grouped.items() if k != inset_key}

    # 본토만으로 투영을 잡는다. 울릉도를 포함하면 본토가 찌그러진다.
    project = make_projector(
        [r for rings in mainland.values() for r in rings], W, H, PAD
    )

    regions = {}
    dissolved_ok = 0

    for key, rings in mainland.items():
        outline = None if args.no_dissolve else dissolve(rings)
        if outline is not None:
            dissolved_ok += 1
            rings_use = outline
        else:
            rings_use = rings
            if not args.no_dissolve:
                print(f"  ! {LABELS[key]}: 병합 실패, 행정동 경계가 보일 수 있음")
        px = [[project(lon, lat) for lon, lat in ring] for ring in rings_use]
        cx, cy = centroid(px)
        regions[key] = {
            "name": LABELS[key],
            "path": to_path(px, args.tol),
            "cx": round(cx, 1),
            "cy": round(cy, 1),
            "inset": False,
        }

    if not args.no_dissolve:
        print(f"시군구 외곽선 병합: {dissolved_ok}/{len(mainland)}")

    # 울릉군: 자체 bbox 기준으로 인셋 박스에 맞춘다.
    if inset_key in grouped:
        ir = dominant_rings(grouped[inset_key])
        ir = (None if args.no_dissolve else dissolve(ir)) or ir
        ip = make_projector(ir, INSET["size"], INSET["size"], 8)
        px = [[(x + INSET["x"], y + INSET["y"]) for x, y in
               (ip(lon, lat) for lon, lat in ring)] for ring in ir]
        cx, cy = centroid(px)
        regions[inset_key] = {
            "name": LABELS[inset_key],
            "path": to_path(px, args.tol * 0.5, min_pts=3),
            "cx": round(cx, 1),
            "cy": round(cy, 1),
            "inset": True,
        }

    months = month_list(MONTH_START, MONTH_END)
    rng = random.Random(args.seed)

    for key in sorted(regions):
        has = args.all_data or key in SEEDED
        regions[key]["hasData"] = has
        regions[key]["frames"] = build_frames(key, months, rng) if has else []

    doc = {
        "meta": {
            "sido": SIDO,
            "viewBox": [0, 0, W, H],
            "inset": INSET,
            "geoSource": "vuski/admdongkor ver20260701",
            "dataStatus": "가짜 데이터 (난수). 한전 실데이터 미확보.",
        },
        "months": months,
        "regions": regions,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))

    n_data = sum(1 for r in regions.values() if r["hasData"])
    size_kb = OUT.stat().st_size / 1024
    print(f"\n{OUT.relative_to(ROOT)}  {size_kb:.0f}KB")
    print(f"  지역 {len(regions)}개 (실데이터 표시 {n_data}개)")
    print(f"  기간 {months[0]} ~ {months[-1]}  ({len(months)}개월)")


if __name__ == "__main__":
    main()
