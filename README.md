# 산단 심박

경상북도 산업도시의 월별 전력 사용량을 심박으로 시각화하는 정적 웹.

## 실행

```bash
python3 -m http.server 8000
```

http://localhost:8000

빌드 단계 없음. node/npm 불필요.

## 구조

- `data/raw/` — 한전 원본 (읽기 전용)
- `data/processed/` — 스크립트 생성 JSON
- `data/geo/` — 행정구역 경계 원본 (git 제외, 아래 명령으로 재다운로드)
- `scripts/` — 데이터 변환 (python, 표준 라이브러리만)
- `src/` — 프론트엔드

프로젝트 규칙과 데이터 스키마는 [CLAUDE.md](CLAUDE.md) 참고.

## 데이터 준비

경계 원본은 33MB라 저장소에 포함하지 않는다.

```bash
curl -sL -o data/geo/hangjeongdong_20260701.geojson \
  https://raw.githubusercontent.com/vuski/admdongkor/master/ver20260701/HangJeongDong_ver20260701.geojson

python3 scripts/build_data.py
```

## 데이터 출처

### 행정구역 경계

- **원천**: 통계청 통계지리정보서비스(SGIS, sgis.kostat.go.kr) 개방 행정동 경계
  — [공공누리 제1유형(출처표시)](https://www.kogl.or.kr/info/licenseType1.do)
- **가공**: [vuski/admdongkor](https://github.com/vuski/admdongkor) `ver20260701`
  — SGIS 경계를 보정하고 시계열(1975~) 확장. CC BY 4.0
- 좌표계 WGS84(EPSG:4326), 2026-07-01 기준 (군위군 대구 편입 반영)

이 저장소에서 추가로 가공한 내용:

1. 경상북도만 필터 (전국 행정동 3,558개 → 321개)
2. 시군구로 병합 (행정동 링 326개 → 22개 외곽선, 포항 남/북구 합침)
3. 픽셀 투영 — 정거원통도법 + 위도 보정, 900×700 좌표계
4. Douglas-Peucker 단순화 — 허용오차 0.7px
5. 울릉군은 인셋 분리 (독도는 축척상 1px 미만이라 제외)

**정확도**: 투영 스케일은 1px ≈ 278m 이므로 단순화 허용오차 0.7px는
**실제 약 195m**에 해당한다. 정점은 41,007개 → 3,346개(-91.8%)로 줄었다.
도 단위 지도에서 시군구 형태를 식별하는 용도에는 충분하지만(화면상 1px 미만),
필지·건물 단위 판정에는 적합하지 않다.

더 정확한 경계가 필요하면:

- [도로명주소지도](https://business.juso.go.kr/jst/jstAddressDetailsSearch)
  — 월 1회 갱신, 가장 세밀. '구역의 도형' 신청 후 `TL_SCCO_GEMD`
- [브이월드 디지털트윈국토](https://www.vworld.kr/dtmk/dtmk_ntads_s001.do)
- [SGIS 행정구역 경계 (공공데이터포털)](https://www.data.go.kr/data/15129688/fileData.do)

### 전력 사용량

한국전력공사 전력데이터 개방포털 — **업종별 전력사용량**
(시·군·구 × 업종 × 월별, 2007.01~2025.06). 조회 경로와 사용할 업종은
[CLAUDE.md](CLAUDE.md) 참고.

> ⚠️ 현재 `data/processed/frames.json`의 심박 값(`rate`/`size`/`irr`)은
> **난수**다. 한전 실데이터는 아직 확보하지 않았다.
