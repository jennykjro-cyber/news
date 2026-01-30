import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 1. 설정 및 세션 초기화
# =================================================
# 그룹별 세분화 키워드 설정 (원하시는 대로 수정 가능)
KEYWORD_MAPPING = {
    "유통": ["홈플러스", "이마트", "롯데마트", "편의점", "GS25", "CU"],
    "육가공/식품": ["육가공", "햄", "소시지", "냉동식품", "HMR", "밀키트"],
    "시장동향": ["가격인상", "원가", "물가", "식품 매출", "대체육"]
}

# 검색용 평탄화 리스트 생성
SEARCH_KEYWORDS = [kw for sublist in KEYWORD_MAPPING.values() for kw in sublist]

# 세션 상태 초기화
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0
if "news_results" not in st.session_state:
    st.session_state.news_results = [] 
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

google_news = GNews(language="ko", country="KR", max_results=10)

# =================================================
# 2. 기능 함수
# =================================================
def get_fixed_date_range():
    today = datetime.today()
    this_thursday = today - timedelta(days=(today.weekday() - 3) % 7)
    last_friday = this_thursday - timedelta(days=6)
    return last_friday.date(), this_thursday.date()

def parse_news_date(date_str):
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
    except:
        return None

def get_group_name(detail_kw):
    for group, details in KEYWORD_MAPPING.items():
        if detail_kw in details:
            return group
    return "기타"

def relevance_score(text: str):
    # 등록된 모든 세
