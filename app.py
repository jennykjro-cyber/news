import requests  #
import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO
import json
import os
from difflib import SequenceMatcher

# =================================================
# 1. 시스템 초기 설정 및 데이터 로드
# =================================================
DB_FILE = "keywords_db.json"

def load_keywords():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "유통업계": ["홈플러스", "이마트", "롯데마트","GS25","CU","이마트24","세븐일레븐","식품"],
        "이커머스": ["쿠팡","마켓컬리","오아시스마켓","이커머스","식품"],
        "육가공": ["육가공", "햄", "소시지", "비엔나","돼지고기","돈육","돈육시세"],
        "경쟁사": ["롯데웰푸드", "에쓰푸드","목우촌","오뗄","선진햄","사조대림","식품"],
        "대체육": ["대체육", "식물성"],
        "식품업계": ["가격인상", "원가", "물가", "소비","식품","식품업계","영양성분"],
        "수출": ["K푸드","K-푸드","수출"],
        "트렌드": ["식품","신제품","인기","트렌드","열풍","브랜드"]
    }

def save_keywords(mapping):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)

if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "news_results" not in st.session_state:
    st.session_state.news_results = []

# =================================================
# 2. 핵심 로직 (검색 및 엑셀 생성)
# =================================================
def get_fixed_date_range():
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    last_friday = today - timedelta(days=days_since_friday)
    return last_friday.date(), today.date()

def parse_news_date(date_str):
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
    except:
        return None
def get_realtime_issue_pool():
    """구글 뉴스 트렌드에서 현재 이슈가 되는 명사들을 추출하여 Pool 생성"""
    import requests
    from collections import Counter
    import re
    
    # 1. 구글 뉴스의 '주요 뉴스' 섹션에서 현재 트렌드 제목들을 가져옴
    issue_news = GNews(language="ko", country="KR", max_results=20)
    top_news = issue_news.get_top_news()
    
    combined_titles = " ".join([n.get('title', '') for n in top_news])
    
    # 2. 간단한 명사 추출 (2글자 이상, 한글 위주)
    words = re.findall(r'[가-힣]{2,}', combined_titles)
    
    # 3. 가장 많이 등장한 단어 상위 15개를 이슈 풀(Pool)로 반환
    issue_counts = Counter(words)
    issue_pool = [word for word, count in issue_counts.most_common(15)]
    
    return issue_pool

def get_relevance_score(title, desc, all_keywords):
    score = 0
    text = f"{title} {desc}".replace(" ", "").lower()
    title_only = title.replace(" ", "").lower()
    for kw in all_keywords:
        target = kw.replace(" ", "").lower()
        if target in title_only: score += 2
        elif target in text: score += 1
    return score

def collect_news_final(mapping, start_date, end_date):
    google_news = GNews(language="ko", country="KR", max_results=25)
    all_rows = []
    all_search_kws = [kw for sublist in mapping.values() for kw in sublist]
    exclude_keywords = ["출시", "런칭", "신제품", "이벤트", "증정", "할인행사", "포토존", "증시", "주가", "상한가"]

    issue_pool = get_realtime_issue_pool()
    st.info(f"🔍 오늘의 외부 이슈 트렌드 분석 완료: {', '.join(issue_pool[:5])}...")

    progress_bar = st.progress(0) [cite: 5]
    groups = list(mapping.items()) [cite: 5]
    
    for i, (group, sub_kws) in enumerate(groups): [cite: 5]
        if not sub_kws: continue [cite: 5]
        search_query = f"{group} ({' OR '.join(sub_kws)})" [cite: 5]
        articles = google_news.get_news(search_query) [cite: 5]
        
        for a in articles:
            title = a.get("title", "제목 없음") [cite: 6]
            if any(ex in title for ex in exclude_keywords): continue [cite: 6]
            article_date = parse_news_date(a.get("published date", "")) [cite: 6]
            if not article_date or not (start_date <= article_date <= end_date): continue [cite: 6]
            
            desc = a.get("description", "") [cite: 7]
            # (1) 기존 방식의 연관도 점수를 계산합니다.
            base_score = get_relevance_score(title, desc, all_search_kws) [cite: 7]
            
            # (2) [수정된 부분] 외부 이슈 풀 단어가 포함되면 가중치(+2.0)를 더합니다.
            issue_weight = 0
            for issue_word in issue_pool:
                if issue_word in title:
                    issue_weight += 2.0
            
            total_score = base_score + issue_weight # 최종 합산 점수
            
            all_rows.append({
                "키워드": group,
                "출처": a.get("publisher", {}).get("title", "출처 미상"), [cite: 7]
                "기사일자": article_date.strftime("%Y-%m-%d"), [cite: 8]
                "제목": title, [cite: 8]
                "링크": a.get("url", ""), [cite: 8]
                "연관도점수": total_score # 가중치가 반영된 점수 저장
            })
        progress_bar.progress((i + 1) / len(groups)) [cite: 8]
        
    # 1. 링크(URL) 기준 1차 중복 제거
    unique_dict = {r['링크']: r for r in all_rows}
    # 2. 연관도 점수가 높은 순으로 먼저 정렬 (가장 중요한 기사를 필터링 기준으로 삼기 위함)
    sorted_rows = sorted(list(unique_dict.values()), key=lambda x: x['연관도점수'], reverse=True)
    
    # 3. 제목 유사도 50% 이상 기사 필터링
    final_filtered = []
    for current in sorted_rows:
        is_duplicate = False
        for existing in final_filtered:
            # 제목 간의 유사도 계산 (0.0 ~ 1.0)
            similarity = SequenceMatcher(None, current['제목'], existing['제목']).ratio()
            if similarity >= 0.5:  # 50% 이상 유사하면 중복으로 판단
                is_duplicate = True
                break
        if not is_duplicate:
            final_filtered.append(current)
            
    return final_filtered
    

def to_excel(data_list):
    valid_data = []
    
    # (1) 링크 유효성 체크 및 제목 정제
    for item in data_list:
        try:
            # 링크가 살아있는지 2초 동안 확인 [cite: 12]
            res = requests.head(item['링크'], timeout=2)
            if res.status_code != 200: 
                continue # 접속 안 되면 제외
        except:
            continue # 에러 나면 제외
        
        # 제목에서 ' - 언론사명' 제거 [cite: 12]
        clean_title = item['제목']
        if " - " in clean_title:
            clean_title = clean_title.rsplit(" - ", 1)[0]
            
        valid_data.append({
            "키워드": item['키워드'],
            "출처": item['출처'],
            "기사일자": item['기사일자'],
            "제목": clean_title,
            "링크": item['링크']
        })

    # (2) 엑셀 파일 생성 (기존 로직 기반) [cite: 11]
    df = pd.DataFrame(valid_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        export_df = df[["키워드", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        
        workbook = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
        
        for row_num, link in enumerate(df['링크']):
            # 정제된 제목에 하이퍼링크 입히기 [cite: 12]
            worksheet.write_url(row_num + 1, 3, link, link_format, df.iloc[row_num]['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI/UX 구성
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", page_icon="🐷", layout="wide")

# --- [여기서부터 삽입 시작] 기기별 자동 레이아웃 최적화 ---
st.markdown("""
    <style>
    /* 1. 모바일 및 태블릿 대응 (화면 너비 1024px 이하일 때) */
    @media screen and (max-width: 1024px) {
        /* 가로로 배치된 메인 컬럼들을 강제로 세로로 쌓음 */
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
        /* 각 컬럼 너비를 100%로 확장하여 꽉 차게 만듦 */
        div[data-testid="column"] {
            width: 100% !important;
            margin-left: 0 !important;
        }
        /* 모바일에서 뉴스 목록 컨테이너 높이가 너무 답답하지 않게 조절 */
        .stElementContainer div[data-testid="stVerticalBlock"] > div[style*="height: 550px"] {
            height: 450px !important; 
        }
    }
    
    /* 2. PC 환경 (1025px 이상) */
    @media screen and (min-width: 1025px) {
        /* 기존의 가로 배치를 그대로 유지 */
        div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
        }
    }
    </style>
""", unsafe_allow_html=True)
# --- [여기까지 삽입 끝] ---


def add_group():
    new_g = st.session_state.new_group_input.strip()
    if new_g and new_g not in st.session_state.keyword_mapping:
        st.session_state.keyword_mapping[new_g] = []
        save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_group_input = ""

def add_sub(group_name):
    new_s = st.session_state.new_sub_input.strip()
    if new_s and new_s not in st.session_state.keyword_mapping[group_name]:
        st.session_state.keyword_mapping[group_name].append(new_s)
        save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_sub_input = ""

# 사이드바 설정
with st.sidebar:
    st.title("🥓 진주햄 뉴스봇")
    st.markdown("일은 줄어들지 않으니,<br>시간이라도 줄여보려고 만든 자동화 시스템⭐<br><span style='font-size:0.8em; color:#999;'>by 로로 🦝</span>", unsafe_allow_html=True)

    st.subheader("⚙️ 검색 설정")
    start_d, end_d = get_fixed_date_range()
    st.info(f"📅 **지난주 금요일부터 오늘까지 검색**\n\n{start_d.strftime('%m.%d')} (금) ~ {end_d.strftime('%m.%d')} (오늘)")
    
    min_score = st.slider("🎯 **연관도 필터** (2추천)", 0, 5, 2)
    
    if st.button("🗂 이번주 뉴스 수집", type="primary", use_container_width=True):
        with st.spinner('🕵️‍♀️ 불가피하게 뉴스를 수집 중입니다'):
            st.session_state.news_results = collect_news_final(st.session_state.keyword_mapping, start_d, end_d)
            st.rerun()

    st.divider()
    with st.expander("📝 분류 관리", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("대분류", key="new_group_input", on_change=add_group, placeholder="분류명")
        with col2:
            keys = list(st.session_state.keyword_mapping.keys())
            sel_g = st.selectbox("선택", options=keys) if keys else st.selectbox("없음", ["-"])
        if keys:
            st.text_input(f"➕ '{sel_g}'에 키워드 추가", key="new_sub_input", on_change=add_sub, args=(sel_g,), placeholder="엔터!")

    with st.expander("📋 키워드 리스트", expanded=False):
        with st.container(height=350, border=False):
            for g, subs in list(st.session_state.keyword_mapping.items()):
                c_title, c_del = st.columns([0.8, 0.2])
                c_title.markdown(f"**{g}**")
                if c_del.button("삭제", key=f"del_g_{g}"):
                    del st.session_state.keyword_mapping[g]
                    save_keywords(st.session_state.keyword_mapping)
                    st.rerun()
                kw_cols = st.columns(2)
                for idx, s in enumerate(subs):
                    with kw_cols[idx % 2]:
                        # g와 s를 명확히 인자로 고정하여 에러 방지
                        if st.button(f"{s} ×", key=f"del_kw_{g}_{s}_{idx}", use_container_width=True):
                            # 정확한 그룹(g)에서 키워드(s)를 제거
                            st.session_state.keyword_mapping[g].remove(s)
                            save_keywords(st.session_state.keyword_mapping)
                            st.rerun()
                st.markdown("---")

# --- 사이드바 최하단에 추가할 점수 매커니즘 설명 ---
    st.divider()
    with st.expander("💡 연관도 점수 산출 방식", expanded=False):
        st.markdown("""
        <div style="font-size: 0.85em; line-height: 1.6; color: #666;">
            <b>1. 연관도 점수 </b><br>
            • 제목에 키워드가 있으면 <b>+2점</b><br>
            • 요약문에 키워드가 있으면 <b>+1점</b><br>
            👉 즉, 제목에 있으면 더 중요</b><br><br>
            <b>2. 필터링 </b><br>
            • 점수 설정시 기준 점수를 넘는 기사만 나옴<br>
            • 점수가 높은 기사일수록 상단에 정렬<br><br>
            ※ 검색 시 공백을 제거로 오차를 최소화<br>
            ※ 불필요한 키워드는 자동으로 제외<br>
        </div>
        """, unsafe_allow_html=True)


# 메인 영역
st.title("📰 Weekly News Clipping")
st.caption("회사 때문에 읽는 뉴스, 대신 모아드립니다")

col_main, col_down = st.columns([1.2, 0.8])

# 1. 왼쪽: 검색 결과 노출 (체크박스 제거 버전)
with col_main:
    st.subheader("🔍 검색 결과")
    all_categories = ["전체"] + list(st.session_state.keyword_mapping.keys())
    tabs = st.tabs([f"  {cat}  " for cat in all_categories])
    
    for i, tab in enumerate(tabs):
        with tab:
            current_cat = all_categories[i]
            filtered_res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
            if current_cat != "전체":
                filtered_res = [r for r in filtered_res if r['키워드'] == current_cat]
            
            if filtered_res:
                st.success(f"총 {len(filtered_res)}건 발견했습니다.")
                with st.container(height=550):
                    for item in filtered_res:
                        with st.container(border=True):
                            st.markdown(f"**[{item['키워드']}] {item['제목']}**")
                            st.caption(f"🗞 {item['출처']} | 🗓 {item['기사일자']} | ⭐ {item['연관도점수']}점")
                            st.markdown(f"[🔗 기사 원문 보러가기]({item['링크']})")
            else:
                st.info("조건에 맞는 뉴스가 없습니다.")

# 2. 오른쪽: 전체 결과 엑셀 추출
with col_down:
    st.subheader("📥 엑셀 추출")
    
    # 전체 뉴스 결과 중 연관도 필터를 통과한 모든 데이터 준비
    final_download_list = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
    
    if final_download_list:
        with st.container(border=True):
            st.markdown(f"### 📊 추출 대기 중\n현재 필터링된 기사는 **총 {len(final_download_list)}건**입니다.")
            st.write("아래 버튼을 누르면 현재 화면에 보이는 모든 뉴스가 엑셀로 저장됩니다.")
            
            file_name = f"진주햄_뉴스클리핑_{end_d.strftime('%Y%m%d')}.xlsx"
            
            st.download_button(
                label="🚀 전체 결과 엑셀 다운로드",
                data=to_excel(final_download_list),
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
    else:
        st.warning("추출할 뉴스 데이터가 없습니다. 먼저 뉴스를 수집하거나 필터를 조정해 주세요.")
