import streamlit as st
import google.generativeai as genai
import os
import re
import requests
from requests.auth import HTTPBasicAuth

# ==========================================
# 页面配置与初始化
# ==========================================
st.set_page_config(page_title="HLC B2B SEO 写作工厂", layout="wide")

# 修改点：使用 Streamlit Secrets 模式读取 Gemini 3 Pro 的钥匙
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
else:
    # 兼容本地开发环境
    API_KEY = os.getenv("GEMINI_API_KEY")
    if API_KEY:
        genai.configure(api_key=API_KEY)
    else:
        st.warning("⚠️ 未检测到 API Key。请在 Streamlit Cloud 的 Advanced Settings -> Secrets 中配置。")

# 初始化 Session State
if 'topics' not in st.session_state: st.session_state.topics = []
if 'selected_topic' not in st.session_state: st.session_state.selected_topic = ""
if 'insights' not in st.session_state: st.session_state.insights = []
if 'article_draft' not in st.session_state: st.session_state.article_draft = ""

# ==========================================
# 模块一：B2B 选题与深度调研
# ==========================================
st.title("模块一：B2B 选题与深度调研 🔍")
st.markdown("---")

st.subheader("1. 输入业务背景")
business_bg = st.text_area(
    "描述您的主营业务、目标市场及客户痛点：", 
    height=100, 
    placeholder="例如：定制机械零件工厂，主要面向欧洲制造商。痛点：交期不稳定..."
)

if st.button("🚀 生成 100 个博客话题", type="primary"):
    if not business_bg:
        st.error("请先输入业务背景！")
    else:
        with st.spinner("Gemini 1.5 正在为您策划话题..."):
            try:
                # 修改点：使用 gemini-1.5-pro
                model = genai.GenerativeModel('gemini-1.5-pro')
                prompt = f"基于以下背景，生成100个英文B2B博客标题，直接输出编号列表：{business_bg}"
                response = model.generate_content(prompt)
                raw_topics = response.text.strip().split('\n')
                st.session_state.topics = [t.strip() for t in raw_topics if t.strip()]
                st.success("✅ 100 个话题已准备就绪！")
            except Exception as e:
                st.error(f"生成失败: {e}")

if st.session_state.topics:
    st.subheader("2. 选择话题并进行深度调研")
    selected = st.selectbox("请选择一个进行下一步：", st.session_state.topics)
    
    if st.button("🔍 开始深度调研 (提取 10 条 Insights)"):
        st.session_state.selected_topic = selected
        with st.spinner(f"Gemini 3 Pro 正在深度检索见解..."):
            try:
                model = genai.GenerativeModel('gemini-1.5-pro')
                research_prompt = f"针对话题 '{selected}'，提取10条真实、专业的B2B行业见解（Insights）。要求：包含市场现状、技术标准或成本差异。以'见解 X:'开头。"
                response = model.generate_content(research_prompt)
                st.session_state.insights = [i.strip() for i in response.text.strip().split('\n') if i.strip()]
                st.success("✅ 调研完成！")
            except Exception as e:
                st.error(f"调研失败: {e}")

if st.session_state.insights:
    st.markdown("### 💡 专业见解展示")
    for insight in st.session_state.insights:
        st.write(insight)

# ==========================================
# 模块二：AI 文章生成
# ==========================================
st.markdown("---")
st.title("模块二：AI 深度文章生成 ✍️")

if st.session_state.insights:
    if st.button("📝 生成 1500 字专业长文", type="primary"):
        with st.spinner("Gemini 1.5 Pro 正在按照 SOP 撰写 1500 字长文..."):
            try:
                model = genai.GenerativeModel('gemini-1.5-pro')
                insights_text = "\n".join(st.session_state.insights)
                generation_prompt = f"""
                # Your Role: 资深外贸 B2B 代笔人。
                # Task: 基于话题 {st.session_state.selected_topic} 和见解 {insights_text} 写 1500 字英文博客。
                # Requirements:
                1. 1个 H1，4个 H2。
                2. 段落不少于 200 字，包含 H3 和 Markdown 表格。
                3. 插入 [Image 1] 到 [Image 5] 占位符。
                4. 口吻客观、专业、直接。输出 Markdown 源码。
                """
                response = model.generate_content(generation_prompt)
                st.session_state.article_draft = response.text
                st.success("✅ 文章生成完毕！")
            except Exception as e:
                st.error(f"生成失败: {e}")

if st.session_state.article_draft:
    st.subheader("📄 文章预览区")
    st.session_state.article_draft = st.text_area("手动微调：", st.session_state.article_draft, height=500)
    with st.expander("👁️ 预览排版效果"):
        st.markdown(st.session_state.article_draft)

# ==========================================
# 模块三：SEO 优化与一键发布
# ==========================================
st.markdown("---")
st.title("模块三：SEO 优化与一键发布 🚀")

if st.session_state.article_draft:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🖼️ 优化图片 SEO"):
            with st.spinner("Gemini 1.5 Pro 正在注入 Alt 标签..."):
                try:
                    model = genai.GenerativeModel('gemini-1.5-pro')
                    replace_prompt = f"请通读文章，将所有的 [Image X] 替换为标准的 Markdown 图片格式 ![Alt](Link 'Title')，Link 统一用 https://placehold.co/600x400.jpg。输出全文：\n{st.session_state.article_draft}"
                    st.session_state.article_draft = model.generate_content(replace_prompt).text
                    st.success("✅ SEO 标签已注入！")
                except Exception as e: st.error(e)

    with col2:
        if st.button("🔗 注入权威脚注"):
            with st.spinner("正在检索权威来源..."):
                try:
                    model = genai.GenerativeModel('gemini-1.5-pro')
                    footnote_prompt = f"为话题 '{st.session_state.selected_topic}' 生成 10 个 Markdown 格式的权威脚注引用列表。"
                    st.session_state.article_draft += "\n\n---\n### References\n" + model.generate_content(footnote_prompt).text
                    st.success("✅ 脚注已追加！")
                except Exception as e: st.error(e)

    st.subheader("🌐 推送至 WordPress")
    wp_url = os.getenv("WP_URL")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD")

    if st.button("🚀 立即推送"):
        if not all([wp_url, wp_user, wp_password]):
            st.error("请检查环境变量设置。")
        else:
            try:
                api_endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
                post_data = {"title": st.session_state.selected_topic, "content": st.session_state.article_draft, "status": "draft"}
                response = requests.post(api_endpoint, json=post_data, auth=HTTPBasicAuth(wp_user, wp_password))
                if response.status_code == 201:
                    st.balloons()
                    st.success("🎉 发布成功！已在 WP 草稿箱。")
                else:
                    st.error(f"失败: {response.status_code}")
            except Exception as e: st.error(e)
