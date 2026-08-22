// detail.html — 시군구 한 곳의 땅 모양만 2.5D 로 본다.
// 지역은 URL 파라미터로만 받는다: detail.html?region=gumi
// 전력 데이터 / 심박 / 건물은 여기서 다루지 않는다.

const SVG_NS = "http://www.w3.org/2000/svg";

const LAYERS = 22;  // 땅 두께 겹 수. 맨 위층(i=0)이 윗면. 나중에 전력량에 연동한다.
const STEP = 2;     // 겹 간격 (SVG 유저 단위, y 축으로 아래로)
const DEPTH = (LAYERS - 1) * STEP;

// viewBox 를 (땅 + 두께) 보다 좁게 잡아 지역이 프레임을 넘치게 한다.
// 1 보다 작을수록 확대. 외곽선이 잘려나가는 건 의도다.
const ZOOM = 0.82;
// 프레임 아래쪽에 남기는 여유 (vbH 비율). perspective 가 가까운(아래) 쪽을 확대해서
// 평면의 아래 약 11% 는 #stage 밖으로 밀려난다 — 그 값이 평면 높이에 비례하므로
// DEPTH 배수가 아니라 프레임 비율로 잡아야 세로로 긴 화면에서도 두께가 안 잘린다.
const NEAR_PAD = 0.17;

// 아래층 어둡게 → 위층 밝게. 맨 위층은 윗면 색.
const SIDE_DARK = [22, 34, 44];
const SIDE_LIGHT = [58, 84, 100];
const TOP = [110, 146, 166];

function lerp(a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

const rgb = ([r, g, b]) => `rgb(${r}, ${g}, ${b})`;

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

const res = await fetch("./data/processed/frames.json");
const data = await res.json();
const region = data.regions[key];

if (!region) {
  nameEl.textContent = "?";
  errEl.textContent = `'${key}' 지역이 frames.json 에 없다. 가능한 키: ` +
    Object.keys(data.regions).join(", ");
  throw new Error(`unknown region: ${key}`);
}

nameEl.textContent = region.name;
document.title = `${region.name} — 산단 심박`;

const { minX, minY, maxX, maxY } = pathBBox(region.path);
const bw = maxX - minX;
// 땅 윗면 아래로 두께가 쌓인다. 이게 실제 도형의 맨 아랫단.
const contentBot = maxY + DEPTH;
const contentH = contentBot - minY;

const svg = document.getElementById("land");
const tilt = document.getElementById("tilt");

// #land 는 #tilt 를 그대로 채운다. aspect-ratio 를 주면 #stage 보다 높아져
// overflow 에 걸리므로 JS 에서도 건드리지 않는다 — 액자는 viewBox 로만 잡는다.
function layout() {
  // getBoundingClientRect 는 rotateX 가 적용된 투영 사각형을 준다 (aspect 가 2.6배 부풀어
  // viewBox 가 통째로 줌아웃됐다). 레이아웃 박스를 봐야 한다 → clientWidth/Height.
  const cw = tilt.clientWidth, ch = tilt.clientHeight;
  if (!cw || !ch) return;

  // #tilt 가 foreshortening 만큼 미리 늘어나 있으므로, 여기서 (땅 + 두께) 기준으로
  // 프레임을 잡으면 preserveAspectRatio 의 meet 이 화면 기준으로 맞아떨어진다.
  let vbW = bw * ZOOM;
  let vbH = (contentH / (1 - NEAR_PAD)) * ZOOM;
  // 프레임이 평면보다 납작하면 meet 이 가로를 기준으로 맞춘다 → 세로를 평면 비율까지 늘린다.
  if (vbW / vbH > cw / ch) vbH = vbW * ch / cw;

  // 가로는 cx 중심. 세로는 가까운 쪽(아래) 끝에 NEAR_PAD 만큼 여유를 두고 아래 정렬하고,
  // 먼 쪽(위)을 잘라낸다 — 두께가 안 보이면 의미가 없고, 위쪽이 잘리는 건 땅이
  // 화면 밖으로 이어지는 것으로 읽힌다.
  svg.setAttribute("viewBox",
    `${region.cx - vbW / 2} ${contentBot - vbH * (1 - NEAR_PAD)} ${vbW} ${vbH}`);
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

layout();
new ResizeObserver(layout).observe(tilt);
