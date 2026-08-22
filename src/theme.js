// theme.css 의 CSS 변수를 JS 에서 읽는다. 색값을 JS 에 다시 적지 않기 위한 것.
// 모듈 스크립트는 <link rel=stylesheet> 파싱 뒤에 실행되므로 변수는 이미 붙어 있다.

const root = document.documentElement;

// --foo → [r, g, b]. #rgb / #rrggbb / rgb(...) 를 받는다.
export function cssRGB(name) {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  if (v.startsWith("#")) {
    const h = v.slice(1);
    const full = h.length === 3 ? h.replace(/./g, (c) => c + c) : h;
    return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
  }
  const nums = (v.match(/-?\d*\.?\d+/g) || []).slice(0, 3).map(Number);
  if (nums.length < 3) throw new Error(`색 변수 ${name} 를 읽지 못했다: "${v}"`);
  return nums;
}

// 두 색 사이 RGB 선형 보간 (hue 회전 아님)
export function lerp(a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

export const rgb = ([r, g, b]) => `rgb(${r}, ${g}, ${b})`;
