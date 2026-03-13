import streamlit as st
import google.generativeai as genai
import os

# ==========================================
# 页面配置与初始化
# ==========================================
st.set_page_config(page_title="B2B AI 写作工作流", layout="wide")

# 建议在部署时将 API Key 配置在环境变量中
# 也可以在本地运行前在终端执行：export GEMINI_API_KEY="your_api_key_here"
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    st.warning("⚠️ 未检测到 GEMINI_API_KEY 环境变量，请配置后再使用生成功能。")

# 初始化 Streamlit Session State，用于跨操作保存数据
if 'topics' not in st.session_state:
    st.session_state.topics = []
if 'selected_topic' not in st.session_state:
    st.session_state.selected_topic = ""
if 'insights' not in st.session_state:
    st.session_state.insights = []

# ==========================================
# 模块一：B2B 选题与深度调研
# ==========================================
st.title("模块一：B2B 选题与深度调研 🔍")
st.markdown("---")

# 1. 业务背景输入
st.subheader("1. 输入业务背景")
business_bg = st.text_area(
    "描述您的主营业务、目标市场及客户痛点：", 
    height=100, 
    placeholder="例如：我们是一家生产定制机械零件的中国工厂，主要面向欧洲和北美的中大型制造商。客户痛点是交期不稳定和供应商缺乏沟通效率..."
)

# 2. 生成 100 个话题
if st.button("🚀 生成 100 个博客话题", type="primary"):
    if not business_bg:
        st.error("请先输入业务背景！")
    else:
        with st.spinner("正在呼叫大模型为您生成 100 个高转化话题..."):
            try:
                model = genai.GenerativeModel('gemini-1.5-pro')
                prompt = f"""
                基于以下外贸B2B业务背景，生成100个具有吸引力和SEO价值的英文B2B博客文章主标题。
                要求：
                1. 围绕客户痛点、行业趋势、采购指南等维度。
                2. 直接输出编号列表，不要任何前言后语。
                业务背景：{business_bg}
                """
                response = model.generate_content(prompt)
                
                # 简单解析返回的文本并存入 session_state
                raw_topics = response.text.strip().split('\n')
                st.session_state.topics = [t.strip() for t in raw_topics if t.strip()]
                st.success("✅ 100 个话题生成完毕！")
            except Exception as e:
                st.error(f"生成失败: {e}")

# 3. 选择话题与深度调研
if st.session_state.topics:
    st.subheader("2. 选择话题并进行深度调研")
    
    # 用户从生成的列表中选择一个话题
    selected = st.selectbox("请从生成的话题中选择一个进行下一步：", st.session_state.topics)
    
    if st.button("🔍 开始深度调研 (提取 10 条 Insights)"):
        st.session_state.selected_topic = selected
        
        with st.spinner(f"正在模拟 Pro Search 深度检索并提取见解：\n{selected}"):
            try:
                model = genai.GenerativeModel('gemini-1.5-pro')
                research_prompt = f"""
                针对以下外贸B2B博客话题：“{selected}”，请模拟专业搜索引擎（如Perplexity）的深度检索能力，提取10条真实、专业、带有行业背景或事实数据的深刻见解（Insights）。
                
                严格要求：
                1. 这10条见解将作为后续撰写长篇专业文章的基础事实依据。
                2. 每条见解必须具体、客观，能让海外B2B采购商感受到专业度（如提及市场现状、技术标准、常见陷阱、成本差异等）。
                3. 直接输出10条见解的列表，必须以“见解 X: ”开头，无须寒暄或总结。
                """
                response = model.generate_content(research_prompt)
                
                # 解析并保存 Insights
                raw_insights = response.text.strip().split('\n')
                st.session_state.insights = [i.strip() for i in raw_insights if i.strip()]
                st.success("✅ 调研完成！已成功提取 10 条专业见解。")
            except Exception as e:
                st.error(f"调研失败: {e}")

# 4. 展示保存的 Insights
if st.session_state.insights:
    st.markdown("### 💡 当前话题的专业见解 (Insights)")
    st.info(f"**当前锁定话题：** {st.session_state.selected_topic}")
    
    for insight in st.session_state.insights:
        st.write(insight)
