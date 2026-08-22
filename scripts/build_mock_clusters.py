#!/usr/bin/env python3
"""⚠ 가상(mock) 클러스터 위기도 생성. 실제 산업단지도, 실제 위기도도 아니다.

**실제 health 산출식은 팀메이트가 별도로 설계 중이다.** 이 스크립트는 그 산출물이
오기 전까지 화면을 붙여 보기 위한 임시 파일이고, 산출식과 아무 관계가 없다.
실데이터 파일(data/processed/clusters.json)이 들어오면 이 스크립트와 출력
파일(clusters.mock.json)을 **삭제**한다.

입력  : data/processed/buildings.mock.json  (클러스터 위치·규모)
        data/processed/frames.json          (months 축 — 길이를 맞춰야 한다)
출력  : data/processed/clusters.mock.json

스키마는 CLAUDE.md 의 계약을 따른다: months + clusters{name, region, cx, cy,
members, frames[{health, inputs}]}. health 는 0~1, **낮을수록 위기**.

health 의 모양 (전부 난수):
  · 완만한 하락 추세   — 장기 침체
  · 12개월 계절성      — 진폭은 클러스터마다 다르다
  · AR(1) 잡음         — 인접 월이 튀지 않게 이어 붙인다
  · 일부는 급락        — EVENTS 의 실제 사건 월에 떨어뜨린다. 실데이터가 오면
                         같은 자리에서 신호가 보이는지 대조할 자리다.

inputs 는 툴팁·분해 표시용 **장식**이다. 여기서는 health 를 먼저 만들고 거기에
잡음을 흔들어 붙인다 — 실데이터에서는 순서가 반대다(입력 → health). 그래서
이 파일의 inputs 로 산출식을 역추정하면 안 된다. 프론트엔드는 계약대로
health 만 읽는다.

표준 라이브러리만 사용한다.
"""

import argparse
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_B = ROOT / "data" / "processed" / "buildings.mock.json"
SRC_F = ROOT / "data" / "processed" / "frames.json"
OUT = ROOT / "data" / "processed" / "clusters.mock.json"

WARNING = (
    "가상 데이터. health 는 난수이며 실제 위기도가 아니다. "
    "팀메이트의 실제 산출식(clusters.json)으로 교체 후 이 파일을 삭제할 것."
)

# 급락을 걸 후보 시점. 나중에 실데이터에서 같은 달을 확인하기 위한 표식이다.
# (힌남노는 CLAUDE.md 의 '미해결' 항목 — 포항 1차금속에서 실제로 보이는지 미확인)
EVENTS = ["2008-09", "2011-03", "2016-01", "2020-03", "2022-09"]
SHOCK_P = 0.32          # 이 확률로 클러스터 하나에 급락 1회

DRIFT_LO, DRIFT_HI = 0.06, 0.34   # 전 구간 누적 하락폭
START_LO, START_HI = 0.62, 0.95   # 첫 달 수준
SEASON_LO, SEASON_HI = 0.010, 0.045
NOISE_LO, NOISE_HI = 0.008, 0.022
AR = 0.82               # 잡음 지속성. 0 이면 월마다 튄다.
H_LO, H_HI = 0.03, 0.99  # 0/1 에 붙으면 색이 양 끝에서 뭉친다


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def base_name(region_name):
    """'포항시' → '포항'. 시·군 접미사를 떼고 산단 이름을 붙인다."""
    return region_name[:-1] if region_name[-1] in "시군구" else region_name


def health_series(cid, months, rng):
    """클러스터 하나의 health 시계열. 길이 = len(months)."""
    T = len(months)
    start = rng.uniform(START_LO, START_HI)
    drift = rng.uniform(DRIFT_LO, DRIFT_HI)
    amp = rng.uniform(SEASON_LO, SEASON_HI)
    phase = rng.uniform(0, 2 * math.pi)
    sd = rng.uniform(NOISE_LO, NOISE_HI)

    # 급락: 한 달 만에 떨어지고 tau 개월에 걸쳐 일부만 회복한다.
    # tau 가 크면 사실상 회복하지 못한 것으로 보인다.
    shock_t, depth, tau, floor = -1, 0.0, 1.0, 0.0
    if rng.random() < SHOCK_P:
        ev = rng.choice(EVENTS)
        if ev in months:
            shock_t = months.index(ev)
            depth = rng.uniform(0.14, 0.38)
            tau = rng.uniform(8, 40)
            floor = rng.uniform(0.0, 0.5)   # 영구히 남는 비율

    out = []
    e = 0.0
    for t in range(T):
        e = AR * e + rng.gauss(0, sd)
        # 하락은 뒤로 갈수록 조금 빨라진다 (지수 1.3)
        trend = start - drift * (t / (T - 1)) ** 1.3
        season = amp * math.sin(2 * math.pi * t / 12 + phase)
        hit = 0.0
        if shock_t >= 0 and t >= shock_t:
            k = math.exp(-(t - shock_t) / tau)
            hit = depth * (floor + (1 - floor) * k)
        out.append(clamp(trend + season + e - hit, H_LO, H_HI))
    return out, (months[shock_t] if shock_t >= 0 else None)


def mock_inputs(h, rng):
    """장식용 입력값. health 에 잡음을 흔들어 붙인 것뿐이다 (위 docstring 참고).
    프론트엔드는 이 값으로 시각적 상태를 정하지 않는다 — 키 구성이 바뀔 수 있다."""
    return {
        "power":   round(clamp(h + rng.gauss(0, 0.06), 0.0, 1.0), 2),
        "stack":   round(clamp(1.0 - h + rng.gauss(0, 0.07), 0.0, 1.0), 2),
        "revenue": round(clamp(h + rng.gauss(0, 0.05), 0.0, 1.0), 2),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=20260822,
                    help="난수 시드. 같은 시드면 같은 시계열이 나온다.")
    args = ap.parse_args()

    frames = json.loads(SRC_F.read_text(encoding="utf-8"))
    mock = json.loads(SRC_B.read_text(encoding="utf-8"))
    months = frames["months"]
    regions = frames["regions"]
    src = mock.get("clusters")
    if not src:
        raise SystemExit(
            "buildings.mock.json 에 clusters 가 없다. "
            "scripts/build_mock_buildings.py 를 먼저 다시 돌려라.")

    clusters = {}
    shocked = []
    # id 순서를 고정한다 — dict 순서가 화면의 그리기 순서가 된다.
    for cid in sorted(src, key=lambda c: (c.rsplit("-", 1)[0],
                                          int(c.rsplit("-", 1)[1]))):
        c = src[cid]
        # 클러스터마다 독립 시드. 하나를 손봐도 나머지 시계열이 흔들리지 않는다.
        rng = random.Random(f"{args.seed}:{cid}")
        series, ev = health_series(cid, months, rng)
        if ev:
            shocked.append((cid, ev))
        n = int(cid.rsplit("-", 1)[1])
        clusters[cid] = {
            "name": f"{base_name(regions[c['region']]['name'])}{n}산단",
            # 업종은 buildings.mock.json 에서 그대로 통과시킨다. 화면의 시각적
            # 상태는 여전히 health 만 쓴다 (계약) — 이건 툴팁·범례용이다.
            "industry": c.get("industry"),
            "industryName": c.get("industryName"),
            "region": c["region"],
            "cx": c["cx"],
            "cy": c["cy"],
            "members": c["count"],
            "frames": [{"health": round(h, 3), "inputs": mock_inputs(h, rng)}
                       for h in series],
        }

    OUT.write_text(
        json.dumps({"_WARNING": WARNING, "months": months,
                    "clusters": clusters},
                   ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")

    lo = min(f["health"] for c in clusters.values() for f in c["frames"])
    hi = max(f["health"] for c in clusters.values() for f in c["frames"])
    print(f"{OUT.relative_to(ROOT)}  ⚠ 가상 데이터")
    print(f"  클러스터 {len(clusters)}개 / 월 {len(months)}개 / seed {args.seed}")
    print(f"  health 범위 {lo:.2f} ~ {hi:.2f}")
    print(f"  급락 {len(shocked)}개: " +
          ", ".join(f"{cid}({ev})" for cid, ev in shocked[:8]) +
          (" …" if len(shocked) > 8 else ""))


if __name__ == "__main__":
    main()
