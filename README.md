# 영주랑 (YoungJuRang)
**관광에서 귀촌까지, 데이터로 잇다**

공공데이터 기반 귀촌 의사결정 지원 플랫폼

## 서비스 구성
| 화면 | 설명 |
|------|------|
| 인구위기 대시보드 | 영주시 읍면동별 인구감소·고령화 시각화 |
| 귀촌 조건 매칭 | 의료·빈집·자연환경 조건 → 최적 읍면 추천 |
| 관광지 정보 | 영주시 153개 관광명소 탐색 |
| AI 귀촌 상담 | Claude API 기반 실시간 귀촌 상담 |

## 로컬 실행

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_api_key_here
python app.py
```

## 데이터 준비
`data/analysis/` 폴더에 분석 결과 CSV 및 JSON 파일 위치
`static/data/` 폴더에 JSON 파일 위치 (pop_trend, aging, score, crisis)

## 배포 (Render.com)
1. GitHub에 프로젝트 업로드
2. Render.com → New Web Service → GitHub 연결
3. 환경변수 `ANTHROPIC_API_KEY` 설정
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app`

## 활용 데이터
- 행정안전부 주민등록 인구현황
- 농림축산식품부 귀농귀촌 실태조사
- 보건복지부 전국의료기관
- 문화체육관광부 전국관광지정보
- 영주시 빈집 실태조사
- 영주시 농어촌민박 현황
- 국토교통부 도시공원정보

## 개발환경
- Python 3.11 / Flask 3.0
- Chart.js 4.4
- Claude API (claude-sonnet-4)
- Render.com 배포
