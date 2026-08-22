// detail.html — 시군구 한 곳의 땅 + 건물을 2.5D 로 본다.
// 지역은 URL 파라미터로만 받는다: detail.html?region=gumi
// 전력 데이터 / 심박은 여기서 다루지 않는다.
//
// ⚠ 건물은 data/processed/buildings.mock.json 의 **가상 데이터**다.
//   실제 공장 위치가 아니다. 팩토리온 실데이터 확보 후 파일과 함께
//   아래 renderBuildings() / #mock-badge 를 정리한다.
//
// 건물은 흩어진 상자가 아니라 **클러스터 = 업종 하나**의 구성으로 온다.
// 상자(box)와 원통(cyl) 두 형태, 앵커(중심 대기업)/부속/위성(협력 중소) 세 역할.
// 앵커와 위성의 차이는 크기·높이·명도로만 나타낸다 — **둘을 잇는 선은 그리지
// 않는다.** 기업 간 협력 관계는 공개 데이터에 없다 (CLAUDE.md "연쇄 층").

import { cssRGB, lerp, rgb } from "./theme.js";

const SVG_NS = "http://www.w3.org/2000/svg";

const LAYERS = 5;   // 땅 두께 겹 수. 맨 위층(i=0)이 윗면. 나중에 전력량에 연동한다.
const STEP = 2;     // 겹 간격 (SVG 유저 단위, y 축으로 아래로)
const DEPTH = (LAYERS - 1) * STEP;  // 8 — 땅 폭(구미 139)의 6% 정도. 얇은 판.

// ⚠ 가상 건물의 높이는 buildings.mock.json 의 b.h 가 그대로 SVG 유저 단위다
// (예전처럼 겹 수가 아니다). #tilt 의 rotateX(64°) 때문에 화면에서는 cos(64°)≈0.44
// 배로 눌려 보인다 — 실루엣 비율은 (h × 0.44) / w 로 읽힌다. 각도를 더 눕히면
// 건물이 더 납작해 보인다 (데이터의 h 는 그대로다).
// 값의 분포는 scripts/build_mock_buildings.py --stats 로 확인한다.

// viewBox 를 (땅 + 두께) bbox 보다 넉넉하게 잡는다. 1 보다 클수록 축소.
// 전체 윤곽이 프레임 안에 들어와야 어느 지역인지 읽힌다.
const PAD = 1.15;

// 아래층 어둡게 → 위층 밝게. 맨 위층은 윗면 색. 색값은 theme.css 에만 있다.
const SIDE_DARK = cssRGB("--land-side");
const SIDE_LIGHT = cssRGB("--land-side-lit");
const TOP = cssRGB("--land-top");

// 건물 (가상 데이터) — 땅과 구분되는 밝은 회청색. 면 2개니까 색도 2개다.
// 벽은 단색으로 칠한다 — 그라디언트를 걸면 상자가 아니라 유리처럼 보인다.
// --bldg-high 그대로면 땅 윗면(--land-top)과 명도가 비슷해 경계가 안 보이므로
// --bldg-low 쪽으로 35% 섞어 한 단 낮춘다. 색값은 theme.css 에만 있다.
const BLDG_TOP = cssRGB("--bldg-top");
const BLDG_ANCHOR_TOP = cssRGB("--bldg-anchor-top");
const BLDG_WALL = lerp(cssRGB("--bldg-low"), cssRGB("--bldg-high"), 0.65);
// 단지 바닥. 건물 바닥면을 APRON 만큼 부풀린 앞치마 + 건물끼리 잇는 목(NECK).
// 목은 **최소신장나무(MST)** 의 간선에만 그린다:
//   · 나무는 모든 건물을 잇는다  → 고립된 건물이 없다
//   · 나무에는 순환이 없다       → 고리 안쪽에 구멍이 생길 수 없다
// 예전의 모폴로지 닫기는 이 두 가지를 보장할 수 없었다 (빈틈을 넓게 메우면
// 답답하고, 좁게 메우면 구멍과 고립이 생긴다).
const APRON = 3.5;   // 건물 밖으로 나오는 여유(px)
const NECK = 2.0;    // 잇는 목의 반폭. APRON 보다 좁아야 "목"으로 읽힌다
const PAD_FILL = cssRGB("--cluster-pad");
const PAD_ALPHA = 0.72;  // 1 이면 깔개가 땅을 덮어 회색 판처럼 보인다

// path 문자열에서 숫자만 순서대로 뽑아 x, y 번갈아 읽는다.
// frames.json 의 path 는 M/L/Z 절대좌표만 쓴다.
function pathBBox(d) {
  const nums = (d.match(/-?\d*\.?\d+/g) || []).map(Number);
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (let i = 0; i + 1 < nums.length; i += 2) {
    const x = nums[i], y = nums[i + 1];
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  return { minX, minY, maxX, maxY };
}

const nameEl = document.getElementById("region-name");
const errEl = document.getElementById("err");

const key = new URLSearchParams(location.search).get("region") || "gumi";

const data = await (await fetch("./data/processed/frames.json")).json();

// ⚠ 가상 건물. 파일이 없으면(삭제됐으면) 땅만 그린다 — 오류로 취급하지 않는다.
const mock = await fetch("./data/processed/buildings.mock.json")
  .then((r) => (r.ok ? r.json() : null))
  .catch(() => null);

const region = data.regions[key];

if (!region) {
  nameEl.textContent = "?";
  errEl.textContent = `'${key}' 지역이 frames.json 에 없다. 가능한 키: ` +
    Object.keys(data.regions).join(", ");
  throw new Error(`unknown region: ${key}`);
}

nameEl.textContent = region.name;
document.title = `${region.name} — 산단 심박`;

// ⚠ 가상 건물. 먼 쪽(y 작은 쪽) 먼저 그려야 가까운 건물이 위에 덮인다.
const mockBuildings = (mock?.buildings?.[key] ?? [])
  .slice()
  .sort((a, b) => a.y - b.y);

const { minX, minY, maxX, maxY } = pathBBox(region.path);
const bw = maxX - minX;
// 땅 윗면 아래로 두께가 쌓인다. 이게 실제 도형의 맨 아랫단.
const contentBot = maxY + DEPTH;
// 건물은 위(-y)로 자라므로 땅 bbox 위로 삐져나온다. 액자에 같이 넣어야 안 잘린다.
const contentTop = mockBuildings.reduce(
  (t, b) => Math.min(t, b.y - b.d - b.h), minY);
const contentH = contentBot - contentTop;

const svg = document.getElementById("land");
const tilt = document.getElementById("tilt");

// #land 는 #tilt 를 그대로 채운다. aspect-ratio 를 주면 #stage 보다 높아져
// overflow 에 걸리므로 JS 에서도 건드리지 않는다 — 액자는 viewBox 로만 잡는다.
function layout() {
  // getBoundingClientRect 는 rotateX 가 적용된 투영 사각형을 준다.
  // 레이아웃 박스를 봐야 한다 → clientWidth/Height.
  const cw = tilt.clientWidth, ch = tilt.clientHeight;
  if (!cw || !ch) return;

  // (땅 + 두께) bbox 에 PAD 만큼 여유를 두고, 짧은 축을 #tilt 비율까지 넓혀
  // preserveAspectRatio 의 meet 이 letterbox 를 만들지 않게 한다.
  // #tilt 가 foreshortening 만큼 미리 늘어나 있으므로 이 비율이 화면 기준으로 맞는다.
  let vbW = bw * PAD;
  let vbH = contentH * PAD;
  if (vbW / vbH > cw / ch) vbH = vbW * ch / cw;
  else                     vbW = vbH * cw / ch;

  // 잘라내지 않으므로 그냥 bbox 중심에 맞춘다.
  const midX = (minX + maxX) / 2;
  const midY = (contentTop + contentBot) / 2;
  svg.setAttribute("viewBox",
    `${midX - vbW / 2} ${midY - vbH / 2} ${vbW} ${vbH}`);
}

// 같은 path 를 LAYERS 겹 복제. 깊은 층부터 붙여 맨 위층이 마지막에 그려지게 한다.
const layers = document.getElementById("layers");
for (let i = LAYERS - 1; i >= 0; i--) {
  const p = document.createElementNS(SVG_NS, "path");
  p.setAttribute("d", region.path);
  p.setAttribute("transform", `translate(0, ${i * STEP})`);
  if (i === 0) {
    p.setAttribute("fill", rgb(TOP));      // 맨 위층 = 땅 윗면
    p.setAttribute("stroke", rgb(SIDE_DARK));
    p.setAttribute("stroke-width", "0.5");
  } else {
    // i 가 클수록 아래층 → 어둡게
    const t = (LAYERS - 1 - i) / (LAYERS - 2);
    p.setAttribute("fill", rgb(lerp(SIDE_DARK, SIDE_LIGHT, t)));
    if (i === LAYERS - 1) p.setAttribute("filter", "url(#ground-shadow)");
  }
  layers.appendChild(p);
}

// ⚠ 가상 건물 렌더링. 상자 하나 = 면 2개.
// rotateZ 가 없어 축이 정렬돼 있으므로 상자에서 보이는 면은 윗면과 앞면 둘뿐이다
// (옆면·뒷면은 정확히 가려진다). 그래서 겹을 쌓을 필요가 없다 — 겹 쌓기는
// 계단·띠를 만들고 요소 수를 h 배로 불린다.
//   바닥 = (x, y-d) 에서 w×d, y 는 아래로 증가 → 앞쪽 변이 y.
//   윗면 = 바닥을 h 만큼 위(-y)로 옮긴 사각형.        밝게 (BLDG_TOP)
//   앞면 = 바닥 앞변(y) ~ 윗면 앞변(y-h) 사이.        어둡게 (BLDG_WALL)
// 두 면 다 축 정렬 사각형이라 rect 로 그린다. 서로 겹치지 않아 순서는 상관없다.
// buildings.mock.json 을 삭제하면 mockBuildings 가 빈 배열이 되어 아무것도 안 그린다.
function rect(g, x, y, w, h, fill) {
  const el = document.createElementNS(SVG_NS, "rect");
  el.setAttribute("x", x);
  el.setAttribute("y", y);
  el.setAttribute("width", w);
  el.setAttribute("height", h);
  el.setAttribute("fill", fill);
  g.appendChild(el);
  return el;
}

function circle(g, cx, cy, r, fill) {
  const el = document.createElementNS(SVG_NS, "circle");
  el.setAttribute("cx", cx);
  el.setAttribute("cy", cy);
  el.setAttribute("r", r);
  el.setAttribute("fill", fill);
  g.appendChild(el);
  return el;
}

// ⚠ 가상 단지 바닥. 건물이 맨땅에 흩어져 있으면 "묶여 있다"가 안 읽힌다 —
// 깔개가 그 일을 한다. 다만 **모양을 건물 분포에서 얻는다**: 바닥면을 그대로
// 깔고 #site-blob 필터(dilate + blur + 문턱 = 모폴로지 닫기)로 부풀려 붙인다.
// bbox 사각형은 분포와 모양이 달라 빈 구석이 남고 클러스터끼리 겹쳤다.
// 클러스터별로 나누지 않아도 된다 — 멀리 떨어진 무리는 부풀려도 붙지 않는다.
// 건물 바닥면의 중심. 상자는 (x, y-d)~(x+w, y) 사각형, 원통은 지름 w 의 원.
function footCenter(b) {
  return b.shape === "cyl"
    ? { x: b.x + b.w / 2, y: b.y - b.w / 2 }
    : { x: b.x + b.w / 2, y: b.y - b.d / 2 };
}

// 최소신장나무 (Prim). 클러스터당 건물이 10여 채라 O(n²) 로 충분하다.
function mstEdges(pts) {
  const inTree = [0];
  const out = pts.map((_, i) => i).slice(1);
  const edges = [];
  while (out.length) {
    let best = null;
    for (const i of inTree) {
      for (const j of out) {
        const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
        if (!best || d < best.d) best = { i, j, d };
      }
    }
    edges.push([pts[best.i], pts[best.j]]);
    inTree.push(best.j);
    out.splice(out.indexOf(best.j), 1);
  }
  return edges;
}

function renderPads() {
  const g = document.getElementById("pads");
  if (!mockBuildings.length) return;

  // 부풀린 외곽이 땅 경계를 조금 물 수 있다. 땅 모양으로 잘라낸다.
  const clip = document.createElementNS(SVG_NS, "clipPath");
  clip.id = "land-clip";
  const cp = document.createElementNS(SVG_NS, "path");
  cp.setAttribute("d", region.path);
  clip.appendChild(cp);
  svg.querySelector("defs").appendChild(clip);
  g.setAttribute("clip-path", "url(#land-clip)");

  // 필터는 그룹 하나에 건다. 안쪽 도형은 전부 같은 색·불투명 — 필터가 보는 건
  // 알파뿐이고, 색과 투명도는 그룹에서 정한다.
  const inner = document.createElementNS(SVG_NS, "g");
  inner.setAttribute("filter", "url(#site-smooth)");
  inner.setAttribute("fill", rgb(PAD_FILL));

  const byCluster = {};
  for (const b of mockBuildings) (byCluster[b.clusterId] ??= []).push(b);

  for (const group of Object.values(byCluster)) {
    // 앞치마: 바닥면을 APRON 만큼 키운다. 원통은 반지름만 늘리면 된다.
    for (const b of group) {
      if (b.shape === "cyl") {
        const c = footCenter(b);
        circle(inner, c.x, c.y, b.w / 2 + APRON, rgb(PAD_FILL));
      } else {
        const el = rect(inner, b.x - APRON, b.y - b.d - APRON,
                        b.w + APRON * 2, b.d + APRON * 2, rgb(PAD_FILL));
        el.setAttribute("rx", APRON);
      }
    }
    // 목: MST 간선마다 굵은 선 하나. 건물 밑을 지나가지만 깔개는 건물보다
    // 아래에 그려지므로 보이지 않는다.
    if (group.length < 2) continue;
    for (const [a, b] of mstEdges(group.map(footCenter))) {
      const ln = document.createElementNS(SVG_NS, "line");
      ln.setAttribute("x1", a.x);
      ln.setAttribute("y1", a.y);
      ln.setAttribute("x2", b.x);
      ln.setAttribute("y2", b.y);
      ln.setAttribute("stroke", rgb(PAD_FILL));
      ln.setAttribute("stroke-width", NECK * 2);
      ln.setAttribute("stroke-linecap", "round");
      inner.appendChild(ln);
    }
  }

  inner.setAttribute("opacity", PAD_ALPHA);
  g.appendChild(inner);
}

// ⚠ 가상 건물 렌더링. 축이 정렬돼 있어(rotateZ 없음) 보이는 면은 윗면과 앞면
// 둘뿐이다. 그래서 상자는 rect 2개, 원통은 원 2개 + rect 1개로 끝난다.
//   상자  윗면 = 바닥을 h 만큼 위(-y)로 옮긴 사각형 / 앞면 = 그 사이
//   원통  바닥 원(둥근 밑동) → 앞면 rect → 윗면 원. 이 순서로 겹쳐야
//         밑동이 둥글게 보인다. 원통은 w == d (지름) 로 들어온다.
// 앵커는 옥상만 한 단 밝게 칠한다 (--bldg-anchor-top).
function renderBuildings() {
  const g = document.getElementById("buildings");
  const badge = document.getElementById("mock-badge");
  if (!mockBuildings.length) return;
  badge.hidden = false;   // 가상 데이터가 실제로 화면에 있을 때만 배지를 켠다

  // mockBuildings 는 y 오름차순(먼 쪽 먼저)이다. 뒤 건물을 먼저 그려야
  // 앞 건물의 벽·옥상이 그 위를 덮어 가려진다.
  for (const b of mockBuildings) {
    const wall = rgb(BLDG_WALL);
    const top = rgb(b.role === "anchor" ? BLDG_ANCHOR_TOP : BLDG_TOP);
    if (b.shape === "cyl") {
      const r = b.w / 2;
      const cx = b.x + r;
      circle(g, cx, b.y - r, r, wall);            // 둥근 밑동
      rect(g, b.x, b.y - r - b.h, b.w, b.h, wall); // 몸통
      circle(g, cx, b.y - r - b.h, r, top);        // 윗면
    } else {
      rect(g, b.x, b.y - b.h, b.w, b.h, wall);              // 앞면
      rect(g, b.x, b.y - b.d - b.h, b.w, b.d, top);         // 윗면
    }
  }
}

// ⚠ 가상 범례. 어느 덩어리가 어느 업종인지 확인하는 용도 — 실데이터가 오면
// 업종은 단지별 입주기업 업종명에서 온다.
function renderLegend() {
  const ul = document.getElementById("cluster-legend");
  const mine = Object.entries(mock?.clusters ?? {})
    .filter(([, c]) => c.region === key);
  for (const [cid, c] of mine) {
    const li = document.createElement("li");
    const n = mockBuildings.filter((b) => b.clusterId === cid).length;
    li.innerHTML = `${c.industryName ?? cid} ` +
      `<span class="n">· 요소 ${n}</span>`;
    ul.appendChild(li);
  }
}

renderPads();
renderBuildings();
renderLegend();
layout();
new ResizeObserver(layout).observe(tilt);
