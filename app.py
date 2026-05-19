import os
import json
import pandas as pd
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, 'data', 'analysis')
STATIC_DATA = os.path.join(BASE_DIR, 'static', 'data')

def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            print(f'JSON 로드 성공: {os.path.basename(path)}')
            return json.load(f)
    except Exception as e:
        print(f'JSON 로드 실패: {path} / {e}')
        return default if default is not None else {}

def load_csv(path):
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
        print(f'CSV 로드 성공: {os.path.basename(path)} / {len(df)}건')
        return df
    except Exception as e:
        print(f'CSV 로드 실패: {path} / {e}')
        return pd.DataFrame()

pop_trend = load_json(os.path.join(STATIC_DATA, 'pop_trend.json'), {
    "labels": ["2020","2021","2022","2023","2024","2025"],
    "total_pop": [103119,101616,100749,100199,98610,97162],
    "yoy_rate": [0,-1.5,-0.9,-0.5,-1.6,-1.5]
})
aging  = load_json(os.path.join(STATIC_DATA, 'aging.json'),  {"regions":[],"aging_rate":[]})
score  = load_json(os.path.join(STATIC_DATA, 'score.json'),  [])
crisis = load_json(os.path.join(STATIC_DATA, 'crisis.json'), [])

score_df = load_csv(os.path.join(DATA_DIR, '05_귀촌적합도_종합점수.csv'))
tour_df  = load_csv(os.path.join(DATA_DIR, '영주시_관광지정보_전처리.csv'))
print(f'전체 데이터 로드 완료 | 관광지: {len(tour_df)}건')


def get_claude_client():
    """Claude 클라이언트 반환 (ANTHROPIC_API_KEY 환경변수 사용)"""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f'Claude 클라이언트 초기화 실패: {e}')
        return None


# ── 라우트 ──────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html',
        pop_data=json.dumps(pop_trend, ensure_ascii=False),
        aging_data=json.dumps(aging, ensure_ascii=False),
        crisis_data=json.dumps(crisis, ensure_ascii=False))

@app.route('/matching')
def matching():
    score_data = score_df.fillna(0).to_dict('records') if not score_df.empty else []
    return render_template('matching.html',
        score_data=json.dumps(score_data, ensure_ascii=False))

@app.route('/tour')
def tour():
    return render_template('tour.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/insight')
def insight():
    return render_template('insight.html')


# ── API ──────────────────────────────────────────

@app.route('/api/match', methods=['POST'])
def api_match():
    if score_df.empty:
        return jsonify([])
    weights = request.get_json() or {}
    w_의료 = float(weights.get('의료', 30)) / 100
    w_빈집 = float(weights.get('빈집', 25)) / 100
    w_공원 = float(weights.get('공원', 15)) / 100
    w_관광 = float(weights.get('관광', 15)) / 100
    w_민박 = float(weights.get('민박', 15)) / 100
    df = score_df.copy()
    for col in ['의료_score','빈집_score','공원_score','관광_score','민박_score']:
        if col not in df.columns:
            df[col] = 0
    df['사용자점수'] = (
        df['의료_score'] * w_의료 +
        df['빈집_score'] * w_빈집 +
        df['공원_score'] * w_공원 +
        df['관광_score'] * w_관광 +
        df['민박_score'] * w_민박
    ).round(1)
    return_cols = ['읍면동','사용자점수','의료기관수','활용가능수','관광지수','민박수']
    for col in return_cols:
        if col not in df.columns:
            df[col] = 0
    result = df.sort_values('사용자점수', ascending=False).head(5)
    return jsonify(result[return_cols].fillna(0).to_dict('records'))


@app.route('/api/comment', methods=['POST'])
def api_comment():
    """귀촌매칭 결과 카드 AI 코멘트 — Claude Haiku 사용"""
    data    = request.get_json() or {}
    region  = data.get('region', '')
    weights = data.get('weights', {})
    stats   = data.get('stats', {})
    rank    = int(data.get('rank', 1))  # 순위 (1~5)

    w_items    = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    top_factor = w_items[0][0] if w_items else '의료'
    factor_label = {
        '의료':'의료 접근성', '빈집':'주거 여건',
        '공원':'자연환경',   '관광':'문화 인프라', '민박':'숙박 여건',
    }.get(top_factor, top_factor)

    의료수 = int(stats.get('의료기관수', 0))
    빈집수 = int(stats.get('활용가능수', 0))
    관광수 = int(stats.get('관광지수', 0))
    민박수 = int(stats.get('민박수', 0))
    점수   = int(stats.get('점수', 0))

    # 순위별 관점 지시
    rank_guide = {
        1: f"이 지역이 1위인 이유를 {factor_label} 중심으로 설명하세요. 자신감 있고 확신에 찬 어조로.",
        2: f"1위와 비교해 이 지역만의 차별점을 설명하세요. '{factor_label} 면에서 고려할 만한 대안'이라는 관점으로.",
        3: f"어떤 유형의 귀촌 희망자에게 이 지역이 잘 맞는지 설명하세요. '이런 분께 추천'이라는 관점으로.",
        4: f"이 지역의 숨은 강점 한 가지를 부각하세요. 수치 중심보다 생활감 있는 표현으로.",
        5: f"이 지역이 5위이지만 특정 조건에서는 최선일 수 있음을 설명하세요. 솔직하되 희망적인 어조로.",
    }.get(rank, f"{factor_label} 중심으로 이 지역을 추천하세요.")

    prompt = (
        f"당신은 영주시 귀촌 전문 데이터 분석가입니다.\n"
        f"아래 데이터를 바탕으로 귀촌 희망자에게 2문장으로 설명하세요.\n"
        f"조건: 100자 이내, 구체적 숫자 1개 이상 포함, 이모지 1개\n"
        f"※ 의료기관 5개 미만이면 '의료 접근성이 다소 제한적'이라고 솔직하게 표현하세요.\n\n"
        f"추천 순위: {rank}위\n"
        f"관점: {rank_guide}\n"
        f"추천 지역: 경북 영주시 {region}\n"
        f"최우선 관심사: {factor_label}\n"
        f"의료기관: {의료수}개 / 활용가능 빈집: {빈집수}개 / 관광지: {관광수}개 / 민박: {민박수}개\n"
        f"귀촌 적합도: {점수}점"
    )

    client = get_claude_client()
    if client:
        try:
            result = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=200,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return jsonify({'comment': result.content[0].text.strip()})
        except Exception as e:
            print(f'Claude comment 오류: {e}')

    # Fallback
    rank_fallback = {
        1: f'✦ {region}은 {factor_label} 기준 최고 점수 {점수}점으로 가장 균형 잡힌 귀촌지입니다.',
        2: f'🏡 {region}은 {factor_label} 면에서 1위와 견줄 만한 탄탄한 대안입니다.',
        3: f'🌿 {factor_label}을 중시하는 분께 {region}이 잘 맞습니다.',
        4: f'📍 {region}은 수치 이상의 생활감 있는 귀촌지로 주목할 만합니다.',
        5: f'💡 {region}은 {factor_label}보다 자연환경을 우선한다면 좋은 선택이 될 수 있습니다.',
    }
    return jsonify({'comment': rank_fallback.get(rank, f'{region} 귀촌을 검토해보세요.')})


@app.route('/api/tour')
def api_tour():
    region = request.args.get('region', '')
    type_  = request.args.get('type', '')
    if tour_df.empty:
        return jsonify([])
    df = tour_df.copy()
    if region and '읍면동' in df.columns:
        df = df[df['읍면동'] == region]
    if type_ and '관광유형명' in df.columns:
        df = df[df['관광유형명'] == type_]
    cols = ['관광지명','주소','관광유형명','읍면동','위도','경도','대표이미지','이미지여부','전화번호']
    for col in cols:
        if col not in df.columns:
            df[col] = ''
    return jsonify(df[cols].fillna('').to_dict('records'))


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """AI 귀촌 상담 챗봇 — Claude Haiku 사용"""
    data     = request.get_json() or {}
    messages = data.get('messages', [])

    system_prompt = (
        "당신은 경북 영주시 귀촌 전문 AI 상담사 '영주랑'입니다. "
        "영주시의 귀촌 지원정책, 빈집 정보, 읍면동별 생활 인프라(의료·교통·복지·일자리), "
        "관광자원(소백산, 부석사, 소수서원, 무섬마을)에 대해 친절하고 구체적으로 안내합니다. "
        "모르는 정보는 솔직히 모른다고 하되 영주시청 공식 홈페이지나 담당부서에 문의를 권유합니다. "
        "답변은 300자 이내로 간결하게, 이모지를 적절히 활용해 읽기 쉽게 작성합니다."
    )

    client = get_claude_client()
    if client:
        try:
            result = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=600,
                system=system_prompt,
                messages=messages
            )
            return jsonify({'response': result.content[0].text})
        except Exception as e:
            print(f'Claude chat 오류: {e}')

    # Fallback
    user_text = messages[-1].get('content', '') if messages else ''
    if '지원금' in user_text or '지원' in user_text:
        resp = '🏡 귀촌 지원정책은 전입 여부·주택 마련 여부 등 요건에 따라 다릅니다. 영주시청 공식 홈페이지에서 확인하거나 담당부서에 문의해보세요.'
    elif '빈집' in user_text:
        resp = '🏠 귀촌 매칭에서 빈집 가중치를 높이면 빈집 풍부 지역을 우선 추천받을 수 있어요. 자세한 매물은 농촌에살어리랏다 서비스를 이용하세요.'
    elif '의료' in user_text or '병원' in user_text:
        resp = '🏥 의료 접근성이 중요하다면 매칭에서 의료 가중치를 높여보세요. 풍기읍·영주동 지역이 의료 접근성이 좋습니다.'
    elif '풍기' in user_text:
        resp = '🌿 풍기읍은 소백산 자락으로 자연환경이 뛰어나고 의료·인프라·관광이 균형잡혀 귀촌 인기 후보지예요.'
    elif '소백산' in user_text or '부석사' in user_text or '관광' in user_text:
        resp = '🗺️ 영주는 소백산, 부석사(유네스코 세계문화유산), 소수서원, 무섬마을 등 풍부한 관광자원이 있습니다!'
    else:
        resp = '안녕하세요! 영주랑 AI 상담사입니다 🌿 귀촌 지원금, 빈집, 읍면동 생활 인프라 등 궁금한 점을 질문해주세요.'
    return jsonify({'response': resp})


@app.route('/api/status')
def api_status():
    claude_ok = bool(os.environ.get('ANTHROPIC_API_KEY', ''))
    return jsonify({
        'status': 'ok',
        'score_rows': len(score_df),
        'tour_rows': len(tour_df),
        'claude': 'ok' if claude_ok else 'unavailable — ANTHROPIC_API_KEY 환경변수를 설정하세요'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
