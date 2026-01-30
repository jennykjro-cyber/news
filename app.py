import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
import json
import os

# =================================================
# 기본 설정
# =================================================
st.set_page_config(page_title="Weekly News Clipping", layout="wide")

DB_FILE = "keywords_db.json"

# =================================================
# 키워드 DB 로드 / 저장
# =================================================
def load_keywords():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_keywords(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if "keywords" not in st.session_state:
    st.session_state.keywords = load_keywords()

# =================================================
# 사이드바 : 키워드 등록 UI (복구)
# =================================================
st.sidebar.header("🔑 키워드 관리")

with st.sidebar:
    major = st.text_input("대분류")
    minor = st.text_input("소분류(키워드)")

    if st.button("등록"):
        if major and minor:
            st.session_state.keywords.setdefault(major, [])
            if minor not in st.session_state.keywords[major]:
                st.session_state.keywords[major].append(minor)
                save_keywords(st.session_state.keywords)
        else:
            st.warning("대분류와 소분류를 모두 입력하세요.")

    st.divider()

    st.markdown("### 📂 등록된 키워드")

    # 기본 접힘 상태
    for cat in list(st.session_state.keywords.keys()):
        with st.expander(cat, expanded=False):
            col1, col2 = st.columns([8, 2])

            with col2:
                if st.button("대분류 삭제", key=f"del_cat_{cat}"):
                    del st.session_state.keywords[cat]
                    save_keywords(st.session_state.keywords)
                    st.experimental_rerun()

            with col1:
                if not st.session_state.keywords[cat]:
                    st.caption("등록된 키워드 없음")

                for kw in st.session_state.keywords[cat]:
                    # 텍스트 클릭에 가장 가까운 UX
                    if st.button(kw, key=f"kw_{cat}_{kw}", use_container_width=True):
                        st.session_state.keywords[cat].remove(kw)
                        save_keywords(st.session_state.keywords)
                        st.experimental_rerun()

# =================================================
# 메인 영역
# =================================================
st.title("📰 Weekly News Clipping")

st.caption("불가피하게 뉴스를 수집중입니다. 잠시만 기다려 주세요.")

# =================================================
# 뉴스 수집 기간 (기존 로직 유지)
# =================================================
today = datetime.today()
weekday = today.weekday()

# 전주 토요일 ~ 이번주 목요일
start_date = today - timedelta(days=weekday + 2)
end_date = today - timedelta(days=weekday - 3)

st.write(
    f"📅 뉴스 수집 기간 : "
    f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
)

# =================================================
# 뉴스 수집
# =================================================
gnews = GNews(
    language="ko",
    country="KR",
    max_results=50
)

all_keywords = []
for kws in st.session_state.keywords.values():
    all_keywords.extend(kws)

news_rows = []

for kw in all_keywords:
    try:
        articles = gnews.get_news(kw)
        for a in articles:
            pub_date = datetime.fromisoformat(a["published date"].replace("Z", ""))
            if start_date <= pub_date <= end_date:
                news_rows.append({
                    "키워드": kw,
                    "제목": a["title"],
                    "언론사": a["publisher"]["title"],
                    "일자": pub_date.date(),
                    "링크": a["url"]
                })
    except Exception:
        pass

# =================================================
# 결과 표시
# =================================================
if news_rows:
    df = pd.DataFrame(news_rows).drop_duplicates(subset=["제목", "링크"])
    st.dataframe(df, use_container_width=True)
else:
    st.info("조건에 맞는 뉴스가 없습니다.")
