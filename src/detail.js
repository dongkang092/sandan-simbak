// detail.html — 시군구 한 곳의 땅 모양만 2.5D 로 본다.
// 지역은 URL 파라미터로만 받는다: detail.html?region=gumi
// 전력 데이터 / 심박 / 건물은 여기서 다루지 않는다.

const SVG_NS = "http://www.w3.org/2000/svg";

const LAYERS = 8;   // 땅 두께 겹 수. 맨 위층(i=0)이 윗면.
const STEP = 2;     // 겹 간격 (SVG 유저 단위, y 축으로 아래로)
const DEPTH = (LAYERS - 1) * STEP;

// 아래층 어둡게 → 위층 밝게. 맨 위층은 윗면 색.
const SIDE_DARK = [26, 40, 50];
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

// 그 지역만 화면에 꽉 차게: 해당 path 의 bbox + 여유로 viewBox 를 맞춘다.
const { minX, minY, maxX, maxY } = pathBBox(region.path);
const bw = maxX - minX;
const bh = maxY - minY;
const pad = Math.max(bw, bh) * 0.06;

const vbX = minX - pad;
const vbY = minY - pad;
const vbW = bw + pad * 2;
const vbH = bh + pad * 2 + DEPTH; // 아래로 쌓이는 두께만큼 더 확보

const svg = document.getElementById("land");
svg.setAttribute("viewBox", `${vbX} ${vbY} ${vbW} ${vbH}`);
svg.style.aspectRatio = `${vbW} / ${vbH}`; // 0x0 방지 + 비율 유지

// 같은 path 를 8겹 복제. 깊은 층부터 붙여 맨 위층이 마지막에 그려지게 한다.
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
  }
  layers.appendChild(p);
}
