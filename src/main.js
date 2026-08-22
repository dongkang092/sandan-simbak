// 1단계: 지도 + 슬라이더 골격
// frames.json 을 읽어 22개 지역 윤곽을 그리고, 슬라이더로 rate 에 따라 fill 을 바꾼다.

const SVG_NS = "http://www.w3.org/2000/svg";

// rate → 색. rate<1 파랑(감소), rate>1 빨강(증가). 색은 대충 (스타일은 나중).
function rateToFill(rate) {
  const t = Math.max(0, Math.min(1, (rate - 0.65) / (1.17 - 0.65))); // 0..1
  const hue = (1 - t) * 220; // 220(파랑) → 0(빨강)
  return `hsl(${hue}, 70%, 50%)`;
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
