// 1단계: 지도 + 슬라이더 골격
// frames.json 을 읽어 22개 지역 윤곽을 그리고, 슬라이더로 rate 에 따라 fill 을 바꾼다.

const SVG_NS = "http://www.w3.org/2000/svg";

// rate → 색. rate=1.0 중심 발산형(diverging). 레인보우 아님.
// rate<1(쇠퇴)=경고색(주황~빨강), rate=1=중립(어두운 회색), rate>1(성장)=차분한 청록~파랑.
// 두 색 사이 RGB 선형 보간 (hue 회전 아님).
const NEUTRAL = [74, 74, 82];    // rate = 1.0
const DECLINE = [201, 66, 36];   // rate <= 0.70 (경고)
const GROWTH  = [44, 116, 168];  // rate >= 1.30 (성장)

function lerp(a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

function rateToFill(rate) {
  const t = Math.max(-1, Math.min(1, (rate - 1.0) / 0.30)); // 0.70~1.30 대칭 클램프
  const [r, g, b] = t < 0 ? lerp(NEUTRAL, DECLINE, -t) : lerp(NEUTRAL, GROWTH, t);
  return `rgb(${r}, ${g}, ${b})`;
}

const res = await fetch("./data/processed/frames.json");
const data = await res.json();

const { months, regions, meta } = data;
const gRegions = document.getElementById("regions");
const slider = document.getElementById("slider");
const monthLabel = document.getElementById("month");

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
  gRegions.appendChild(p);
}

// 슬라이더 세팅
slider.max = months.length - 1;

function render(i) {
  monthLabel.textContent = months[i];
  for (const { el, region } of paths) {
    el.setAttribute("fill", rateToFill(region.frames[i].rate));
  }
}

slider.addEventListener("input", () => render(Number(slider.value)));
render(0);
