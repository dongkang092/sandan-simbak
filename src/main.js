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
// 배경에 따뜻한 색이 남아 있으면 그 위의 붉은 발광이 갈색 얼룩으로 섞인다.
// rate 를 완전히 버리지는 않고(색조 힌트는 남는다) 거의 중성까지 뺀다.
const DESAT = 0.80;   // 1 이면 완전 회색
// 배경을 꽤 깊이 눌러야 한다. 지역이 중간 밝기로 남으면 그 위의 발광이
// 빛이 아니라 우윳빛 얼룩으로 보인다 — 어두운 바닥이 있어야 빛이 산다.
const SINK = 0.44;    // 1 이면 판 색과 같아져 지역이 사라진다

function recede(c) {
  const y = Math.round(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]);
  return lerp(lerp(c, [y, y, y], DESAT), SURFACE, SINK);
}

// health → 화면 상태. 0~1 단조 스케일 (낮을수록 위기).
// CRIT_AT/OK_AT 는 위기 판정 문턱이 아니라 **스케일의 양 끝**이다 — 이 밖은 값이
// 포화된다. health 를 계산하지 않고 받은 값을 색·후광 세기에 대응시키기만 한다.
// 색은 전부 적색 계열이고 밝기만 변한다 (theme.css 참고). 위기일수록 뜨겁게
// 밝아지고 후광이 세진다 — 두 채널이 같은 방향이라 작은 점으로도 읽힌다.
const H_CRIT = cssRGB("--health-crit");
const H_MID = cssRGB("--health-mid");
const H_OK = cssRGB("--health-ok");
const CRIT_AT = 0.30, OK_AT = 0.85;

// health → 0(위기) ~ 1(차분)
function norm(health) {
  return Math.max(0, Math.min(1, (health - CRIT_AT) / (OK_AT - CRIT_AT)));
}

// t → [r,g,b]
function healthRGB(t) {
  return t < 0.5 ? lerp(H_CRIT, H_MID, t / 0.5)
                 : lerp(H_MID, H_OK, (t - 0.5) / 0.5);
}

// 점 크기: 면적이 members 에 비례하도록 반지름은 sqrt. 900x700 좌표계 기준.
// 작게 유지한다 — 점이 커지면 발광이 아니라 원반으로 보이고, 여러 개가
// 규칙적으로 깔리면 지도가 아니라 무늬가 된다.
const R_K = 0.55, R_MIN = 1.2, R_MAX = 3.2;

function radius(members) {
  return Math.max(R_MIN, Math.min(R_MAX, R_K * Math.sqrt(members || 1)));
}

// ── 발광 ────────────────────────────────────────────────
// 흐림 필터로 원판을 뭉개면 테두리가 남아 "흐린 스티커"가 된다. 대신 중심에서
// 바깥으로 떨어지는 그라디언트를 알맹이보다 훨씬 크게 깔고, #clusters 의
// mix-blend-mode: screen 으로 배경에 더한다 — 빛의 감쇠처럼 읽힌다.
//
// 후광은 두 겹이다. 실제 광원이 그렇게 보인다 — 알맹이 바로 옆에 좁고 센 블룸이
// 있고, 그 밖으로 넓고 아주 옅은 베일이 깔린다. 한 겹으로 넓게 퍼뜨리면
// (반지름을 키우면) 점이 아니라 지역 전체가 물든 얼룩이 된다.
// 세 겹이다: 알맹이에 붙은 좁고 센 블룸 → 중간 → 넓고 아주 옅은 베일.
// 겹이 가산 합성으로 쌓이면서 중심이 저절로 밝아진다 — 중심을 흰색으로
// 칠해서 밝게 만드는 것과 결과가 다르다 (그건 물감처럼 탁해진다).
//   [반지름 배수, 세기 배수] — 배수의 기준은 radius(members)
const HALO_LAYERS = [[2.2, 1.0], [4.8, 0.45], [11.0, 0.12]];
// 알맹이는 기준 반지름보다 **작게** 잡는다. 알맹이가 블룸만큼 크면 빛나는
// 점이 아니라 털 난 공처럼 보인다 — 핀포인트 + 넓은 빛이 광원처럼 읽힌다.
const CORE_MUL = 0.5;
// 가우시안 감쇠 근사. 중심 근처를 빠르게 떨어뜨리고 꼬리를 길게 남긴다.
// 등간격으로 놓으면 원뿔처럼 각이 진 후광이 된다.
const HALO_STOPS = [[0, 1], [0.08, 0.58], [0.20, 0.25],
                    [0.40, 0.08], [0.66, 0.02], [1, 0]];
// 알맹이: 중심은 흰빛에 가깝게 태우고 테두리로 갈수록 제 색. 발광하는 물체의
// 중심이 흰 것은 노출이 날아가는 것과 같은 원리다.
const CORE_STOPS = [[0, 1], [0.45, 1], [1, 0.85]];
const WHITE = [255, 255, 255];

// 위기(t=0) 일수록 후광이 세고 중심이 더 하얗게 탄다. 두 채널이 같은 방향이라
// 반지름 2px 짜리 점으로도 상태가 읽힌다.
// 가산 합성은 화면에 값을 그대로 더하므로 screen 보다 훨씬 세다. 낮게 잡는다.
const HALO_LO = 0.10, HALO_HI = 0.52;   // 차분 → 위기
// 알맹이 중심만 살짝 태운다. 많이 태우면 붉은 점이 아니라 흰 점이 된다 —
// 밝기는 후광이 쌓여서 나오는 게 맞다.
const BURN_LO = 0.10, BURN_HI = 0.55;

function makeGradient(id, stops) {
  const g = document.createElementNS(SVG_NS, "radialGradient");
  g.id = id;
  for (const [offset, opacity] of stops) {
    const st = document.createElementNS(SVG_NS, "stop");
    st.setAttribute("offset", offset);
    st.setAttribute("stop-opacity", opacity);
    g.appendChild(st);
  }
  document.getElementById("map-defs").appendChild(g);
  return g;
}

// 모든 stop 을 같은 색으로 (후광) / 첫 stop 만 다른 색으로 (알맹이) 칠한다.
function paintStops(grad, colors) {
  const stops = grad.children;
  for (let i = 0; i < stops.length; i++) {
    stops[i].setAttribute("stop-color", colors[Math.min(i, colors.length - 1)]);
  }
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
// 점 하나 = 후광 + 알맹이. 좌표·크기는 고정이고 매 월 색과 세기만 바뀐다.
// 그라디언트는 점마다 하나씩 만든다 — 색이 서로 다르니 공유할 수 없다.
const dots = []; // { halos: [{ el, grad, k }], coreGrad, cluster }
if (mock && mock.months?.length === months.length) {
  let n = 0;
  for (const cluster of Object.values(mock.clusters)) {
    const r = radius(cluster.members);
    const id = `dot${n++}`;
    const halos = HALO_LAYERS.map(([mul, k], j) => {
      const grad = makeGradient(`${id}-halo${j}`, HALO_STOPS);
      const el = document.createElementNS(SVG_NS, "circle");
      el.setAttribute("cx", cluster.cx);
      el.setAttribute("cy", cluster.cy);
      el.setAttribute("r", r * mul);
      el.setAttribute("fill", `url(#${id}-halo${j})`);
      return { el, grad, k };
    });
    const coreGrad = makeGradient(`${id}-core`, CORE_STOPS);

    const core = document.createElementNS(SVG_NS, "circle");
    core.classList.add("dot-core");
    core.setAttribute("cx", cluster.cx);
    core.setAttribute("cy", cluster.cy);
    core.setAttribute("r", r * CORE_MUL);
    core.setAttribute("fill", `url(#${id}-core)`);

    // 넓은 베일 → 좁은 블룸 → 알맹이 순으로 쌓는다.
    for (const h of halos.slice().reverse()) gClusters.append(h.el);
    gClusters.append(core);
    dots.push({ halos, coreGrad, cluster });
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
  for (const { halos, coreGrad, cluster } of dots) {
    const t = norm(cluster.frames[i].health);
    const crisis = 1 - t;
    const c = healthRGB(t);
    const hot = lerp(c, WHITE, BURN_LO + (BURN_HI - BURN_LO) * crisis);
    const strength = HALO_LO + (HALO_HI - HALO_LO) * crisis;
    for (const { el, grad, k } of halos) {
      paintStops(grad, [rgb(c)]);
      el.setAttribute("opacity", (strength * k).toFixed(3));
    }
    paintStops(coreGrad, [rgb(hot), rgb(hot), rgb(c)]);
  }
}

slider.addEventListener("input", () => render(Number(slider.value)));
render(0);
