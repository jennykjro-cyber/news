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

if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart_list" not in st.session_state:
    st.session_state.cart_list = []

# =================================================
# 2. 핵심 로직
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
        t = kw.replace(" ", "").lower()
        if t in title_only:
            score += 2
        elif t in text:
            score += 1
    return score

def collect_news_final(mapping, start_date, end_date):
    google_news = GNews(language="ko", country="KR", max_results=25)
    all_rows = []
    all_search_kws = [kw for sub in mapping.values() for kw in sub]
    exclude_keywords = ["출시", "런칭", "신제품", "이벤트", "증정", "할인행사", "포토존", "팝업스토어", "증시", "주가"]

    for group, sub_kws in mapping.items():
        if not sub_kws:
            continue

        search_query = f"{group} ({' OR '.join(sub_kws)})"
        articles = google_news.get_news(search_query)

        for a in articles:
            title = a.get("title", "제목 없음")
            if any(ex in title for ex in exclude_keywords):
                continue

            article_date = parse_news_date(a.get("published date", ""))
            if not article_date or not (start_date <= article_date <= end_date):
                continue

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

    unique_rows = {r['링크']: r for r in all_rows}.values()
    return sorted(list(unique_rows), key=lambda x: x['연관도점수'], reverse=True)

def to_excel(data_list):
    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        if not df.empty:
            export_df = df[["키워드", "출처", "기사일자", "제목"]]
            export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        else:
            pd.DataFrame().to_excel(writer, sheet_name="뉴스클리핑")
    return output.getvalue()

# =================================================
# 3. UI
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", page_icon="🥓", layout="wide")

# ---------- 사이드바 ----------
with st.sidebar:
    st.title("🥓 진주햄 뉴스봇")
    st.subheader("📝 키워드 관리실")

    # 고정 높이 + 내부 스크롤
    with st.container(height=420):
        for cat in list(st.session_state.keyword_mapping.keys()):
            st.markdown(f"**{cat}**")
            for kw in list(st.session_state.keyword_mapping[cat]):
                c1, c2, c3 = st.columns([0.55, 0.3, 0.15])

                with c1:
                    st.write(kw)

                with c2:
                    move_to = st.selectbox(
                        "이동",
                        list(st.session_state.keyword_mapping.keys()),
                        index=list(st.session_state.keyword_mapping.keys()).index(cat),
                        key=f"move_{cat}_{kw}"
                    )
                    if move_to != cat:
                        st.session_state.keyword_mapping[cat].remove(kw)
                        st.session_state.keyword_mapping[move_to].append(kw)
                        save_keywords(st.session_state.keyword_mapping)
                        st.rerun()

                with c3:
                    if st.button("❌", key=f"del_{cat}_{kw}"):
                        st.session_state.keyword_mapping[cat].remove(kw)
                        save_keywords(st.session_state.keyword_mapping)
                        st.rerun()

    st.divider()

    # 대분류 추가
    new_cat = st.text_input("대분류 입력 후 Enter", key="new_cat")
    if new_cat:
        st.session_state.keyword_mapping.setdefault(new_cat, [])
        save_keywords(st.session_state.keyword_mapping)
        st.session_state.new_cat = ""
        st.rerun()

    # 키워드 추가
    target_cat = st.selectbox("키워드 추가 위치", st.session_state.keyword_mapping.keys())
    new_kw = st.text_input("키워드 입력 후 Enter", key="new_kw")
    if new_kw:
        st.session_state.keyword_mapping[target_cat].append(new_kw)
        save_keywords(st.session_state.keyword_mapping)
        st.session_state.new_kw = ""
        st.rerun()

# ---------- 메인 ----------
start_d, end_d = get_fixed_date_range()

if st.button("🗂 이번 주 어쩔 수 없는 뉴스 수집"):
    st.session_state.news_results = collect_news_final(
        st.session_state.keyword_mapping, start_d, end_d
    )
    st.session_state.cart_list = []

col_main, col_cart = st.columns([1.3, 0.7])

with col_main:
    for item in st.session_state.news_results:
        if st.checkbox(item["제목"], key=item["링크"]):
            if item not in st.session_state.cart_list:
                st.session_state.cart_list.append(item)

with col_cart:
    st.subheader("🛒 쓸만한 뉴스 장바구니")

    if st.session_state.cart_list:
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(
            cart_df[["키워드", "출처", "기사일자", "제목"]],
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "📥 엑셀 다운로드",
            to_excel(st.session_state.cart_list),
            "진주햄_뉴스클리핑.xlsx",
            use_container_width=True
        )
    else:
        st.info("아직 쓸만한 뉴스가 없습니다.")
