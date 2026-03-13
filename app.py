import streamlit as st
import google.generativeai as genai
import os
import requests
from requests.auth import HTTPBasicAuth
import time

# ==========================================
# 系统初始化与 API 配置
# ==========================================
st.set_page_config(page_title="AI Writer 自动化工具集 (2026版)", layout="wide", initial_sidebar_state="expanded")

def get_config(key):
    return st.secrets.get(key) or os.getenv(key)

api_key = get_config("GEMINI_API_KEY")
wp_url = get_config("WP_URL")
wp_user = get_config("WP_USER")
wp_password = get_config("WP_APP_PASSWORD")

if api_key: genai.configure(api_key=api_key)
else: st.sidebar.error("❌ 未配置 GEMINI_API_KEY")

@st.cache_resource
def get_model(model_type="flash"):
    """智能获取可用模型，优先尝试 2026 年最新模型"""
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if model_type == "pro":
            target = next((m for m in available if "pro" in m), available[0])
        else:
            target = next((m for m in available if "flash" in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel('models/gemini-1.5-flash')

model_flash = get_model("flash")
model_pro = get_model("pro")

# 初始化全局状态 (模拟云端保存)
state_keys = ['persona', 'raw_topics', 'clean_topics', 'materials', 'article_draft']
for k in state_keys:
    if k not in st.session_state: st.session_state[k] = "" if k in ['persona', 'article_draft'] else []

# ==========================================
# 工具 1：创建【我的角色背景】
# ==========================================
def tool1_persona():
    st.title("👤 工具 1：创建【我的角色背景】")
    st.markdown("这是整个流程的起点，用于定制 AI 输出的风格。") # [cite: 2, 14, 16]
    
    with st.form("persona_form"):
        st.write("请描述您的业务和目标客户：") # 
        company = st.text_input("公司简介与优势 (例如: 25年经验的液压马达工厂)")
        product = st.text_input("核心产品类别")
        audience = st.text_input("目标客户画像 (例如: 欧美中大型企业的采购经理)")
        tone = st.selectbox("品牌语气", ["专业严谨的工程师口吻", "热情活泼的销售口吻", "客观中立的分析师口吻"])
        
        if st.form_submit_button("💾 生成并保存角色背景", type="primary"):
            if company and product:
                st.session_state.persona = f"背景：我们是{company}，主营{product}。我们的目标客户是{audience}。写作时请严格采用{tone}。"
                st.success("✅ 角色背景已保存！后续工具将自动调用。") # [cite: 21, 31]
            else: st.error("请至少填写公司和产品信息。")
            
    if st.session_state.persona:
        st.info(f"**当前保存的背景：**\n{st.session_state.persona}")

# ==========================================
# 工具 2：文章话题生成器
# ==========================================
def tool2_topics():
    st.title("💡 工具 2：文章话题生成器")
    st.markdown("回答 4 个简单问题，AI 批量生成精准话题。") # [cite: 4, 34, 36]
    
    col1, col2 = st.columns(2)
    with col1: target_country = st.text_input("1. 目标客户国家 (如: 美国, 欧洲):") # [cite: 674, 678]
    with col1: product_cat = st.text_input("2. 三级类目名称 (如: hydraulic motor):") # [cite: 692, 698]
    with col2: company_type = st.text_input("3. 目标客户公司类型 (如: 能源基础设施运营商):") # [cite: 707, 712]
    with col2: my_country = st.text_input("4. 你的公司所在国家 (如: 中国):", value="中国") # [cite: 724, 728]
    
    num_topics = st.slider("生成数量", 10, 100, 30) # 简化了数量，避免 API 超时
    
    if st.button("🚀 生成话题列表", type="primary"):
        if not all([target_country, product_cat, company_type]): st.error("请填完 4 个问题。")
        else:
            with st.spinner(f"正在为 {target_country} 的 {company_type} 生成话题..."): # [cite: 741, 743]
                prompt = f"针对{my_country}出口到{target_country}的{product_cat}业务，目标客户是{company_type}。请生成 {num_topics} 个具有高SEO价值的英文B2B博客标题。直接输出列表。"
                try:
                    res = model_flash.generate_content(prompt)
                    st.session_state.raw_topics = [t.strip() for t in res.text.split('\n') if t.strip()]
                    st.success("✅ 话题生成完毕！建议前往工具7进行去重。") # [cite: 128, 142]
                except Exception as e: st.error(e)
                
    if st.session_state.raw_topics:
        with st.expander("查看当前生成的话题", expanded=True):
            st.write(st.session_state.raw_topics)

# ==========================================
# 工具 7：话题去重工具
# ==========================================
def tool7_dedupe():
    st.title("🧹 工具 7：话题智能去重")
    st.markdown("AI 语义级去重，避免重复写作。") # [cite: 126, 128, 130]
    
    col1, col2 = st.columns(2)
    with col1:
        old_topics = st.text_area("粘贴历史话题 (每行一个)", height=200) # [cite: 135, 644]
    with col2:
        new_topics = st.text_area("粘贴新生成的话题 (默认读取工具2结果)", value="\n".join(st.session_state.raw_topics), height=200) # [cite: 137, 651]
        
    if st.button("🚀 开始语义去重", type="primary"): # [cite: 139, 658]
        with st.spinner("AI 正在比对语义..."): # [cite: 637]
            prompt = f"历史话题：\n{old_topics}\n\n新话题：\n{new_topics}\n\n请对比新旧话题，剔除新话题中与历史话题语义重复或高度相似的项。直接输出去重后保留的新话题列表。"
            try:
                res = model_flash.generate_content(prompt)
                st.session_state.clean_topics = [t.strip() for t in res.text.split('\n') if t.strip()]
                st.success("✅ 去重完成！")
            except Exception as e: st.error(e)
            
    if st.session_state.clean_topics:
        st.subheader("去重后的优质话题：")
        st.write(st.session_state.clean_topics)

# ==========================================
# 工具 4：写文章原材料生成
# ==========================================
def tool4_materials():
    st.title("🗄️ 工具 4：写作原材料生成")
    st.markdown("深度调研 (Perplexity/Google) + 个人见解。") # [cite: 72, 74, 76]
    
    topic = st.selectbox("选择一个话题进行调研", st.session_state.clean_topics or st.session_state.raw_topics or ["Please generate topics first"])
    personal_insight = st.text_area("录入个人见解（选填）", placeholder="例如：齿轮马达便宜但容易磨损...") # [cite: 77, 85, 195]
    
    if st.button("🔍 开始 AI 见解调研", type="primary"): # [cite: 83, 190]
        with st.spinner("正在后台模拟深度调研分析..."): # [cite: 191]
            prompt = f"话题：{topic}。请模拟 Perplexity 深度检索，提炼出 5 条极其专业的 B2B 行业见解。外加提供 4 个相关的 H2 子标题。"
            try:
                res = model_pro.generate_content(prompt)
                st.session_state.materials = {
                    "topic": topic,
                    "ai_insights": res.text,
                    "personal": personal_insight
                }
                st.success("✅ 原材料准备完毕！") # [cite: 200]
            except Exception as e: st.error(e)
            
    if st.session_state.materials:
        st.info(f"**话题:** {st.session_state.materials['topic']}\n\n**个人见解:** {st.session_state.materials['personal']}\n\n**AI 调研:**\n{st.session_state.materials['ai_insights']}")

# ==========================================
# 工具 5：文章生成器
# ==========================================
def tool5_article():
    st.title("✍️ 工具 5：一键生成 Markdown 文章") # [cite: 90]
    st.markdown("融合角色背景与原材料，生成长文。") # [cite: 92, 206]
    
    if not st.session_state.persona or not st.session_state.materials:
        st.warning("⚠️ 请先在工具 1 配置背景，并在工具 4 生成原材料。")
        return
        
    if st.button("📝 生成文章 (约需 1-3 分钟)", type="primary"): # [cite: 103, 210]
        st.session_state.article_draft = ""
        with st.spinner("AI 正在根据原材料撰写 1500 字 Markdown 文章..."):
            try:
                m = st.session_state.materials
                prompt = f"""
                {st.session_state.persona}
                # 写作任务：基于以下原材料，写一篇不少于 1500 字的 B2B 深度博客文章。
                # 主标题：{m['topic']}
                # 个人要求见解：{m['personal']}
                # AI 调研数据：{m['ai_insights']}
                # 格式要求：包含 1 个 H1, 4 个 H2, H3, 表格, 并在各段落插入 [Image 1] 到 [Image 5] 占位符。直接输出 Markdown 源码。
                """
                # 使用流式输出避免超时
                response = model_pro.generate_content(prompt, stream=True, safety_settings=[{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}])
                placeholder = st.empty()
                full_text = ""
                for chunk in response:
                    if chunk.text:
                        full_text += chunk.text
                        placeholder.markdown(full_text + "▌")
                st.session_state.article_draft = full_text
                st.success("✅ 文章生成完毕！") # [cite: 94]
            except Exception as e: st.error(e)
            
    if st.session_state.article_draft:
        st.session_state.article_draft = st.text_area("在线 Markdown 编辑器：", st.session_state.article_draft, height=600) # [cite: 95, 105, 212]

# ==========================================
# 工具 6：文章配图 + 一键发布
# ==========================================
def tool6_publish():
    st.title("🚀 工具 6：配图与一键发布")
    st.markdown("自动处理 SEO Metadata、配图占位并发布到 WordPress。") # [cite: 11, 108, 110, 113]
    
    if not st.session_state.article_draft:
        st.warning("⚠️ 请先在工具 5 生成文章。")
        return
        
    if st.button("🖼️ 优化图片 SEO 与 Alt 标签"): # [cite: 110]
        with st.spinner("正在将 [Image] 占位符替换为 SEO 格式..."):
            try:
                p = f"将文章中的 [Image X] 替换为带描述性 Alt 标签的 Markdown 图片，URL 统一用 https://placehold.co/800x400.png。全文：\n{st.session_state.article_draft}"
                st.session_state.article_draft = model_flash.generate_content(p).text
                st.success("✅ 配图与 SEO 处理完成！")
            except Exception as e: st.error(e)
            
    st.markdown("### 🌐 推送至 WordPress") # [cite: 115, 123]
    status = st.selectbox("状态", ["draft", "publish"])
    if st.button("一键发布"):
        if not all([wp_url, wp_user, wp_password]): st.error("请在 Secrets 配置 WP 账号。")
        else:
            with st.spinner("正在推送..."):
                try:
                    endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
                    data = {"title": st.session_state.materials.get('topic', 'Draft'), "content": st.session_state.article_draft, "status": status}
                    r = requests.post(endpoint, json=data, auth=HTTPBasicAuth(wp_user, wp_password))
                    if r.status_code == 201: st.success(f"🎉 发布成功！链接: {r.json().get('link')}")
                    else: st.error(r.text)
                except Exception as e: st.error(e)

# ==========================================
# 侧边栏导航与主控 (模拟文档的工具集菜单)
# ==========================================
with st.sidebar:
    st.title("⚙️ AI Writer 工具集")
    st.markdown("*(依据 2026.03 SOP 构建)*")
    page = st.radio("导航菜单", [
        "1. 创建角色背景", 
        "2. 文章话题生成器", 
        "7. 话题去重工具",
        "4. 写文章原材料生成",
        "5. 文章生成器",
        "6. 配图 + 一键发布"
    ])
    st.markdown("---")
    st.caption(f"当前 Pro 模型: {model_pro.model_name}")
    st.caption(f"当前 Flash 模型: {model_flash.model_name}")

# 路由分发
if page.startswith("1"): tool1_persona()
elif page.startswith("2"): tool2_topics()
elif page.startswith("7"): tool7_dedupe()
elif page.startswith("4"): tool4_materials()
elif page.startswith("5"): tool5_article()
elif page.startswith("6"): tool6_publish()
