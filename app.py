import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO
import json
import os

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
        "유통": ["홈플러스", "이마트", "롯데마트"],
        "편의점": ["GS25", "CU"],
        "육가공": ["육가공", "햄", "소시지", "비엔나"],
        "HMR": ["HMR", "밀키트"],
        "대체육": ["대체육", "식물성"],
        "시장동향": ["가격인상", "원가", "물가", "식품 매출"]
    }

def save_keywords(mapping):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)

# 세션 상태 초기화
if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart_list" not in st.session_state:
    st.session_state.cart_list = []
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

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
    
    progress_bar = st.progress(0)
    groups = list(mapping.items())
    
    for i, (group, sub_kws) in enumerate(groups):
        if not sub_kws: continue
        search_query = f"{group} ({' OR '.join(sub_kws)})"
        articles = google_news.get_news(search_query)
        
        for a in articles:
            title = a.get("title", "제목 없음")
            if any(ex in title for ex in exclude_keywords): continue
            
            article_date = parse_news_date(a.get("published date", ""))
            if not article_date or not (start_date <= article_date <= end_date): continue
            
            desc = a.get("description", "")
            score = get_relevance_score(title, desc, all_search_kws)
            
            all_rows.append({
                "키워드": group,
                "출처": a.get("publisher", {}).get("title", "출처 미상"),
                "기사일자": article_date.strftime("%Y-%m-%d"),
                "제목": title,
                "링크": a.get("url", ""),
                "연관도점수": score
            })
        progress_bar.progress((i + 1) / len(groups))
    
    unique_rows = {r['링크']: r for r in all_rows}.values()
    return sorted(list(unique_rows), key=lambda x: x['연관도점수'], reverse=True)

def to_excel(data_list):
    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        export_df = df[["키워드", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        
        workbook = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
        
        for row_num, link in enumerate(df['링크']):
            worksheet.write_url(row_num + 1, 3, link, link_format, df.iloc[row_num]['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI/UX 구성 및 바구니 동기화 로직
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", page_icon="🐷", layout="wide")

# [핵심 수정] key를 사용하여 체크박스 상태를 제어하는 함수
def toggle_cart_item(item, key):
    # 현재 체크박스의 상태(True/False)를 가져옴
    is_checked = st.session_state[key]
    current_links = [c['링크'] for c in st.session_state.cart_list]
    
    if is_checked:
        if item['링크'] not in current_links:
            st.session_state.cart_list.append(item)
    else:
        # 링크가 일치하는 항목을 제거 (리스트 재구성)
        st.session_state.cart_list = [c for c in st.session_state.cart_list if c['링크'] != item['링크']]

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
    st.markdown(
    "일은 줄어들지 않으니,<br>시간이라도 줄여보려고 만든 자동화 시스템⭐ <br>
    <span style="font-size:0.8em; color:#999;">by 로로 🦝</span>
    """,
    unsafe_allow_html=True
)

    st.subheader("⚙️ 검색 설정")
    start_d, end_d = get_fixed_date_range()
    
    # 날짜 표시를 좀 더 예쁘게
    st.info(f"📅 **어차피 이번 주 얘기만 합니다**\n\n{start_d.strftime('%m.%d')} (금) ~ {end_d.strftime('%m.%d')} (오늘)")
    
    min_score = st.slider("🎯 **연관도 필터** (2추천)", 0, 5, 2)
    
    st.write("") # 여백
    # [요청사항 반영] 위트 있는 문구와 이모티콘 추가
    if st.button("🗂 어차피 보게 될 이번주 뉴스 수집", type="primary", use_container_width=True):
        with st.spinner('🕵️‍♀️ 불가피하게 뉴스를 수집 중입니다'):
            st.session_state.news_results = collect_news_final(st.session_state.keyword_mapping, start_d, end_d)
            st.session_state.cart_list = [] 
            st.rerun()

    st.divider()
    
    with st.expander("📝 분류", expanded=False):
    
    # 2단 컬럼 배치 (가로형)
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("대분류", key="new_group_input", on_change=add_group, placeholder="분류명")
        with col2:
            keys = list(st.session_state.keyword_mapping.keys())
            sel_g = st.selectbox("선택", options=keys, label_visibility="visible") if keys else st.selectbox("없음", ["-"])
        if keys:
            st.text_input(f"➕ '{sel_g}'에 키워드 쏙 넣기", key="new_sub_input", on_change=add_sub, args=(sel_g,), placeholder="입력 후 엔터!")
        st.markdown("---")

# 기존 코드를 아래 코드로 대체하세요
    with st.expander("📋 키워드 리스트", expanded=False):
        # height를 지정한 container가 있으면 내부에서 스크롤이 생깁니다.
        with st.container(height=350, border=False):
            if not st.session_state.keyword_mapping:
                st.caption("등록된 키워드가 없습니다.")
            
            for g, subs in list(st.session_state.keyword_mapping.items()):
                # 1. 대분류 레이아웃 (제목과 작은 삭제 버튼)
                c_title, c_del = st.columns([0.8, 0.2])
                c_title.markdown(f"**{g}**")
                
                # 대분류 삭제 버튼을 텍스트 크기에 맞춰 작게
                if c_del.button("삭제", key=f"del_g_{g}", help=f"{g} 전체 삭제"):
                    del st.session_state.keyword_mapping[g]
                    save_keywords(st.session_state.keyword_mapping)
                    st.rerun()

                # 2. 키워드 개별 삭제 (가로로 여러 개 배치)
                # 한 줄에 키워드를 담을 빈 공간(container) 생성
                kw_cols = st.columns(2) # 한 줄에 2~3개가 적당합니다.
                for idx, s in enumerate(subs):
                    with kw_cols[idx % 2]: # 2개 컬럼을 번갈아가며 사용
                        # 키워드와 X를 합친 작은 버튼 생성
                        if st.button(f"{s} ×", key=f"del_kw_{g}_{s}", use_container_width=True):
                            st.session_state.keyword_mapping[g].remove(s)
                            save_keywords(st.session_state.keyword_mapping)
                            st.rerun()
                st.markdown("---")
                        
# 메인 영역
st.title("📰 Weekly News Clipping")
st.caption("회사 때문에 읽는 뉴스, 대신 모아드립니다")
st.write("")

col_main, col_cart = st.columns([1.3, 0.7])

with col_main:
    st.subheader("🔍 검색 결과")
    
    all_categories = ["전체"] + list(st.session_state.keyword_mapping.keys())
    tabs = st.tabs([f"  {cat}  " for cat in all_categories]) # 탭 간격 조금 벌리기
    
    # 바구니에 담긴 링크 목록 (체크박스 동기화용)
    cart_links = [item['링크'] for item in st.session_state.cart_list]
    
    for i, tab in enumerate(tabs):
        with tab:
            current_cat = all_categories[i]
            filtered_res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
            if current_cat != "전체":
                filtered_res = [r for r in filtered_res if r['키워드'] == current_cat]
            
            if filtered_res:
                st.success(f"총 {len(filtered_res)}건 발견. 실제로 쓸 건 몇 개 안 될겁니다🎉")
                with st. container(height=550):
                    for idx, item in enumerate(filtered_res):
                        # [오류 해결 핵심] Key에 current_cat(현재 탭 이름)을 포함시켜 중복 방지
                        # 예: cb_전체_http://... vs cb_유통_http://... 
                        unique_key = f"cb_{current_cat}_{idx}_{item['링크']}"
                    
                        with st.container(border=True):
                            c_check, c_txt = st.columns([0.05, 0.95])
                            with c_check:
                                st.checkbox(
                                    "", 
                                    key=unique_key,
                                    value=(item['링크'] in cart_links), # 값은 실제 바구니 데이터 기준
                                    on_change=toggle_cart_item,
                                    args=(item, unique_key)
                                )
                            with c_txt:
                                st.markdown(f"**[{item['키워드']}] {item['제목']}**")
                                st.caption(f"🗞 {item['출처']}  |  🗓 {item['기사일자']}  |  ⭐ {item['연관도점수']}점")
                                st.markdown(f"[🔗 기사 원문 보러가기]({item['링크']})")
            else:
                if st.session_state.news_results:
                    st.info(f"💦 '{current_cat}' 쪽은 딱히 쓸만한 뉴스는 없습니다")
                else:
                    st.warning("👈 왼쪽 사이드바에서 '뉴스 수집' 버튼을 누르면 최소한 뭔가는 나옵니다")

with col_cart:
    st.subheader("🛒 쓸만한 뉴스 장바구니")
    
    if st.session_state.cart_list:
        with st.container(border=True):
            st.markdown(f"**현재 {len(st.session_state.cart_list)}개 보관 중. 줄어들 예정**")
            
            # 미리보기 데이터프레임
            cart_df = pd.DataFrame(st.session_state.cart_list)
            st.dataframe(
                cart_df[["키워드", "제목"]], 
                use_container_width=True, 
                hide_index=True,
                height=300
            )
            
            st.write("")
            file_name = f"진주햄_뉴스클리핑_{end_d.strftime('%Y%m%d')}.xlsx"
            
            st.download_button(
                label="📥 재미는 없지만 필요한 파일 다운로드",
                data=to_excel(st.session_state.cart_list),
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
            
            if st.button("🔄 후회를 포함하여 다시 처음부터", use_container_width=True):
                st.session_state.cart_list = []
                st.rerun()
    else:
        st.info("아직 쓸만한 게 없습니다 🍂\n\n왼쪽 리스트에서 필요한 기사를 체크하면 여기에 들어와요.")
