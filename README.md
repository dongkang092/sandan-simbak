# 산단 심박

경상북도 산업도시의 월별 전력 사용량을 심박으로 시각화하는 정적 웹.

## 실행

```bash
python3 -m http.server 8000
```

http://localhost:8000

## 구조

- `data/raw/` — 한전 원본 (읽기 전용)
- `data/processed/` — 스크립트 생성 JSON
- `data/geo/` — 행정구역 경계
- `scripts/` — 데이터 변환 (python)
- `src/` — 프론트엔드

프로젝트 규칙과 데이터 스키마는 [CLAUDE.md](CLAUDE.md) 참고.
