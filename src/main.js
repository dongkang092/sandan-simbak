// 전체 지도 + 슬라이더.
// 주인공은 산업 클러스터다 (CLAUDE.md "시각화 대상"). 클러스터 위기도(health)를
// 점으로 찍고, 시군구 fill(전력 rate)은 채도를 낮춰 배경으로 물러난다.
//
// ⚠ 클러스터는 data/processed/clusters.mock.json 의 **가상 데이터**다.
//   실제 산업단지도, 실제 위기도도 아니다. 팀메이트의 실제 산출식(clusters.json)이
//   오면 파일을 교체하고 #mock-badge 를 지운다.
//   health 산출식은 여기에 구현하지 않는다 — 계약대로 health 값만 읽는다.

import { cssRGB, lerp, rgb } from "./theme.js";

const SVG_NS = "http://www.w3.org/2000/svg";

// rate → 색. rate=1.0 중심 발산형(diverging). 레인보우 아님.
// rate<1(쇠퇴)=경고색, rate=1=중립, rate>1(성장)=차분한 청록~파랑.
// 실제 색값은 theme.css 의 --decline / --neutral / --growth 한 곳에만 있다.
// 두 색 사이 RGB 선형 보간 (hue 회전 아님).
const NEUTRAL = cssRGB("--neutral");  // rate = 1.0
const DECLINE = cssRGB("--decline");  // rate <= 0.70 (경고)
const GROWTH  = cssRGB("--growth");   // rate >= 1.30 (성장)

function rateToRGB(rate) {
  const t = Math.max(-1, Math.min(1, (rate - 1.0) / 0.30)); // 0.70~1.30 대칭 클램프
  return t < 0 ? lerp(NEUTRAL, DECLINE, -t) : lerp(NEUTRAL, GROWTH, t);
}

// 지역 fill 은 배경이다. rate 색을 그대로 쓰되 채도를 낮추고(자기 광도 쪽으로
// 섞기) 판 색으로 조금 눌러, 위에 찍히는 클러스터 점과 대비를 만든다.
// 색값을 새로 만들지 않는다 — rate 팔레트를 약하게 쓰는 것뿐이다.
const SURFACE = cssRGB("--surface");
const DESAT = 0.55;   // 1 이면 완전 회색
const SINK = 0.22;    // 1 이면 판 색과 같아져 지역이 사라진다

function recede(c) {
  const y = Math.round(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]);
  return lerp(lerp(c, [y, y, y], DESAT), SURFACE, SINK);
}

// health → 색. 0~1 단조 스케일 (낮을수록 위기). rate 색 함수와 공유하지 않는다.
// CRIT/OK 는 위기 판정 문턱이 아니라 **색 스케일의 양 끝**이다 — 이 밖은 색이
// 포화된다. health 를 계산하지 않고 받은 값을 색에 대응시키기만 한다.
const H_CRIT = cssRGB("--health-crit");
const H_MID = cssRGB("--health-mid");
const H_OK = cssRGB("--health-ok");
const CRIT_AT = 0.30, OK_AT = 0.85;

function healthToFill(health) {
  const t = Math.max(0, Math.min(1, (health - CRIT_AT) / (OK_AT - CRIT_AT)));
  return rgb(t < 0.5 ? lerp(H_CRIT, H_MID, t / 0.5)
                     : lerp(H_MID, H_OK, (t - 0.5) / 0.5));
}

// 점 크기: 면적이 members 에 비례하도록 반지름은 sqrt. 900x700 좌표계 기준.
const R_K = 1.35, R_MIN = 2.2, R_MAX = 9.0;

function radius(members) {
  return Math.max(R_MIN, Math.min(R_MAX, R_K * Math.sqrt(members || 1)));
}

const res = await fetch("./data/processed/frames.json");
const data = await res.json();

// ⚠ 가상 클러스터. 파일이 없으면(아직 없거나 삭제됐으면) 지역 지도만 그린다 —
// 오류로 취급하지 않는다.
const mock = await fetch("./data/processed/clusters.mock.json")
  .then((r) => (r.ok ? r.json() : null))
  .catch(() => null);

const { months, regions, meta } = data;
const gRegions = document.getElementById("regions");
const gClusters = document.getElementById("clusters");
const slider = document.getElementById("slider");
const monthLabel = document.getElementById("month");
const hoverName = document.getElementById("hover-name");

// inset 점선 박스 (울릉군)
if (meta.inset) {
  const box = document.createElementNS(SVG_NS, "rect");
  box.id = "inset-box";
  box.setAttribute("x", meta.inset.x);
  box.setAttribute("y", meta.inset.y);
  box.setAttribute("width", meta.inset.size);
  box.setAttribute("height", meta.inset.size);
  gRegions.appendChild(box);
}

// 호버 윤곽 — 지역 path 를 다 붙인 뒤 마지막에 append 해서 맨 위에 오게 한다.
const hoverOutline = document.createElementNS(SVG_NS, "path");
hoverOutline.id = "hover-outline";

// 지역 path 렌더
const paths = []; // { el, region } — hasData=true 만 담는다
for (const [key, region] of Object.entries(regions)) {
  const p = document.createElementNS(SVG_NS, "path");
  p.setAttribute("d", region.path);
  p.classList.add("region");
  p.dataset.key = key;
  if (region.hasData) {
    paths.push({ el: p, region });
  } else {
    p.classList.add("no-data"); // 회색 고정
  }

  // 호버: 이름 표시 + 윤곽 덧그리기 (hasData=false 지역도 동일하게 동작)
  p.addEventListener("mouseenter", () => {
    hoverName.textContent = region.name;
    hoverOutline.setAttribute("d", region.path);
  });
  p.addEventListener("mouseleave", () => {
    hoverName.textContent = "";
    hoverOutline.removeAttribute("d");
  });

  // 클릭: 상세로 이동. key 는 frames.json 의 regions 키 그대로.
  p.addEventListener("click", () => {
    location.href = `detail.html?region=${encodeURIComponent(key)}`;
  });

  gRegions.appendChild(p);
}

gRegions.appendChild(hoverOutline);

// ⚠ 가상 클러스터 점. months 축이 frames.json 과 다르면 슬라이더 인덱스가
// 어긋나므로 그리지 않는다 — 계약(frames 길이 = months 길이)이 깨진 경우다.
const dots = []; // { el, cluster }
if (mock && mock.months?.length === months.length) {
  for (const cluster of Object.values(mock.clusters)) {
    const c = document.createElementNS(SVG_NS, "circle");
    c.classList.add("cluster");
    c.setAttribute("cx", cluster.cx);
    c.setAttribute("cy", cluster.cy);
    c.setAttribute("r", radius(cluster.members));
    gClusters.appendChild(c);
    dots.push({ el: c, cluster });
  }
}
if (dots.length) {
  // 가상 데이터가 실제로 화면에 있을 때만 배지를 켠다
  document.getElementById("mock-badge").hidden = false;
}

// 슬라이더 세팅
slider.max = months.length - 1;

function render(i) {
  monthLabel.textContent = months[i];
  for (const { el, region } of paths) {
    el.setAttribute("fill", rgb(recede(rateToRGB(region.frames[i].rate))));
  }
  // 계약: health 외의 값으로 시각적 상태를 정하지 않는다.
  for (const { el, cluster } of dots) {
    el.setAttribute("fill", healthToFill(cluster.frames[i].health));
  }
}

slider.addEventListener("input", () => render(Number(slider.value)));
render(0);
