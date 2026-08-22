// detail.html — 시군구 한 곳의 땅 + 건물을 2.5D 로 본다.
// 지역은 URL 파라미터로만 받는다: detail.html?region=gumi
// 전력 데이터 / 심박은 여기서 다루지 않는다.
//
// ⚠ 건물은 data/processed/buildings.mock.json 의 **가상 데이터**다.
//   실제 공장 위치가 아니다. 팩토리온 실데이터 확보 후 파일과 함께
//   아래 renderBuildings() / #mock-badge 를 정리한다.

import { cssRGB, lerp, rgb } from "./theme.js";

const SVG_NS = "http://www.w3.org/2000/svg";

const LAYERS = 5;   // 땅 두께 겹 수. 맨 위층(i=0)이 윗면. 나중에 전력량에 연동한다.
const STEP = 2;     // 겹 간격 (SVG 유저 단위, y 축으로 아래로)
const DEPTH = (LAYERS - 1) * STEP;  // 8 — 땅 폭(구미 139)의 6% 정도. 얇은 판.

// ⚠ 가상 건물의 겹 간격. 땅(STEP=2)보다 촘촘하다 — rotateX 로 세로가 0.47배
// 눌리는 걸 감안해도 STEP 이면 h=13 이 바닥 폭의 3배가 되어 성냥개비로 보인다.
const BSTEP = 0.95;

// viewBox 를 (땅 + 두께) bbox 보다 넉넉하게 잡는다. 1 보다 클수록 축소.
// 전체 윤곽이 프레임 안에 들어와야 어느 지역인지 읽힌다.
const PAD = 1.15;

// 아래층 어둡게 → 위층 밝게. 맨 위층은 윗면 색. 색값은 theme.css 에만 있다.
const SIDE_DARK = cssRGB("--land-side");
const SIDE_LIGHT = cssRGB("--land-side-lit");
const TOP = cssRGB("--land-top");

// 건물 (가상 데이터) — 땅과 구분되는 밝은 회청색
const BLDG_LOW = cssRGB("--bldg-low");
const BLDG_HIGH = cssRGB("--bldg-high");
const BLDG_TOP = cssRGB("--bldg-top");

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
  (t, b) => Math.min(t, b.y - b.d - b.h * BSTEP), minY);
const contentH = contentBot - contentTop;

const svg = document.getElementById("land");
const tilt = document.getElementById("tilt");

// #land 는 #tilt 를 그대로 채운다. aspect-ratio 를 주면 #stage 보다 높아져
// overflow 에 걸리므로 JS 에서도 건드리지 않는다 — 액자는 viewBox 로만 잡는다.
function layout() {
  // getBoundingClientRect 는 rotateX/rotateZ 가 적용된 투영 사각형을 준다.
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

// ⚠ 가상 건물 렌더링. 땅과 같은 겹 쌓기지만 방향이 반대다 —
// 땅은 아래로(+y), 건물은 위로(-y) 쌓는다. 위층이 밝고 아래층이 어둡다.
// buildings.mock.json 을 삭제하면 mockBuildings 가 빈 배열이 되어 아무것도 안 그린다.
function renderBuildings() {
  const g = document.getElementById("buildings");
  const badge = document.getElementById("mock-badge");
  if (!mockBuildings.length) return;
  badge.hidden = false;   // 가상 데이터가 실제로 화면에 있을 때만 배지를 켠다

  for (const b of mockBuildings) {
    // x,y 는 좌하단. 바닥은 (x, y-d) 에서 w×d.
    for (let i = 0; i < b.h; i++) {
      const r = document.createElementNS(SVG_NS, "rect");
      r.setAttribute("x", b.x);
      r.setAttribute("y", b.y - b.d - i * BSTEP);
      r.setAttribute("width", b.w);
      // 바닥 깊이(d)가 겹 간격보다 얕으면 겹 사이가 벌어져 벽이 줄무늬로
      // 끊긴다 → 아래층은 BSTEP 만큼 위로 더 늘려 다음 층이 덮게 한다.
      r.setAttribute("height", i === b.h - 1 ? b.d : b.d + BSTEP);
      if (i === b.h - 1) {
        r.setAttribute("fill", rgb(BLDG_TOP));   // 옥상
      } else {
        const t = b.h > 2 ? i / (b.h - 2) : 1;   // 0 = 바닥, 1 = 옥상 바로 아래
        r.setAttribute("fill", rgb(lerp(BLDG_LOW, BLDG_HIGH, t)));
      }
      g.appendChild(r);
    }
  }
}

renderBuildings();
layout();
new ResizeObserver(layout).observe(tilt);
