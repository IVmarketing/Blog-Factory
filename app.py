import streamlit as st
import google.generativeai as genai
import os
import requests
from requests.auth import HTTPBasicAuth

# ==========================================
# 1. 页面配置与初始化
# ==========================================
st.set_page_config(page_title="B2B SEO 写作工厂 (2026 稳定版)", layout="wide")

# 安全读取 Secrets
def get_config(key):
    return st.secrets.get(key) or os.getenv(key)

api_key = get_config("GEMINI_API_KEY")
wp_url = get_config("WP_URL")
wp_user = get_config("WP_USER")
wp_password = get_config("WP_APP_PASSWORD")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ 缺少 API Key。请在 Advanced settings -> Secrets 中配置 GEMINI_API_KEY。")

# ==========================================
# 2. 智能模型诊断逻辑 (解决 404 的关键)
# ==========================================
@st.cache_resource
def get_available_models():
    """获取该 Key 真正能调用的模型列表"""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return models
    except Exception as e:
        st.sidebar.error(f"无法获取模型列表: {e}")
        return []

available_models = get_available_models()

# 在侧边栏显示诊断信息
with st.sidebar:
    st.title("⚙️ 系统诊断")
    if available_models:
        st.success(f"已检测到 {len(available_models)} 个可用模型")
        # 自动选择最强的 Pro 模型
        default_pro = next((m for m in available_models if "pro" in m), available_models[0])
        default_flash = next((m for m in available_models if "flash" in m), available_models[0])
        
        st.session_state.pro_model = st.selectbox("核心写作大脑 (Pro):", available_models, index=available_models.index(default_pro))
        st.session_state.flash_model = st.selectbox("快速调研大脑 (Flash):", available_models, index=available_models.index(default_flash))
    else:
        st.error("无法找到可用模型，请检查 API Key 区域限制。")

# 初始化数据状态
for key in ['topics', 'selected_topic', 'insights', 'article_draft']:
    if key not in st.session_state: 
        st.session_state[key] = [] if key in ['topics', 'insights'] else ""

# ==========================================
# 3. 模块一：选题与调研 (对应文档 3 & 4)
# ==========================================
st.title("🏗️ 模块一：选题与调研")
st.markdown("---")

business_bg = st.text_area("1. 输入业务背景 (主营业务 + 痛点):", height=100, placeholder="例如：我们是液压马达工厂，客户痛点是交期太慢...")

if st.button("🚀 第一步：策划 100 个高转化话题", type="primary"):
    if not business_bg: st.error("请填入背景信息")
    else:
        with st.spinner("正在根据文档 3 逻辑生成话题..."):
            try:
                model = genai.GenerativeModel(st.session_state.flash_model)
                prompt = f"扮演 B2B 专家，基于背景：{business_bg}，生成 100 个英文博客标题，解决客户痛点。直接输出列表。"
                res = model.generate_content(prompt)
                st.session_state.topics = [t.strip() for t in res.text.split('\n') if t.strip()]
                st.success(f"✅ 已利用 {st.session_state.flash_model} 生成成功！")
            except Exception as e: st.error(f"生成失败: {e}")

if st.session_state.topics:
    selected = st.selectbox("2. 选择一个话题进行深度调研:", st.session_state.topics)
    if st.button("🔍 第二步：自动提取 10 条专业见解"):
        st.session_state.selected_topic = selected
        with st.spinner("正在模拟 Pro Search 提取深度见解 (文档 4)..."):
            try:
                model = genai.GenerativeModel(st.session_state.pro_model)
                research_p = f"针对话题 '{selected}'，提取 10 条像行业专家写的专业见解（Insights），包含技术指标或市场事实。以'见解 X:'开头。"
                res = model.generate_content(research_p)
                st.session_state.insights = [i.strip() for i in res.text.split('\n') if i.strip()]
                st.success("✅ 调研完成！")
            except Exception as e: st.error(e)

if st.session_state.insights:
    with st.expander("👁️ 查看 10 条调研见解"):
        for i in st.session_state.insights: st.write(i)

# ==========================================
# 4. 模块二：1500 字长文生成 (对应文档 5 - 开启流式)
# ==========================================
st.markdown("---")
st.title("✍️ 模块二：深度文章生成")

if st.session_state.insights:
    if st.button("📝 第三步：撰写 1500 字专业长文 (流式生成)", type="primary"):
        st.session_state.article_draft = "" # 清空旧稿
        with st.spinner("正在执行 Ghostwriter SOP 写作..."):
            try:
                model = genai.GenerativeModel(st.session_state.pro_model)
                insights_str = "\n".join(st.session_state.insights)
                write_prompt = f"""
                # Your Role: 资深外贸 B2B 代笔专家。
                # Task: 基于话题 {st.session_state.selected_topic} 和见解 {insights_str} 写 1500 字英文博客。
                # SOP Requirements:
                1. 1个 H1，恰好 4个 H2。
                2. 段落深度分析，每段 >200 字，包含 H3。
                3. 插入 [Image 1] 到 [Image 5] 占位符。
                4. 包含 1 个 Markdown 表格。
                输出 Markdown 源码。
                """
                # 开启流式生成 (stream=True)
                response = model.generate_content(write_prompt, stream=True)
                
                placeholder = st.empty() # 创建动态显示区域
                full_text = ""
                for chunk in response:
                    full_text += chunk.text
                    placeholder.markdown(full_text + "▌") # 模拟打字机
                st.session_state.article_draft = full_text
                st.success("✅ 1500 字长文创作完成！")
            except Exception as e: st.error(e)

if st.session_state.article_draft:
    st.subheader("文章编辑区")
    st.session_state.article_draft = st.text_area("您可以直接在此修改:", st.session_state.article_draft, height=500)

# ==========================================
# 5. 模块三：SEO 优化与发布 (对应文档 7 & 9 & 10)
# ==========================================
st.markdown("---")
st.title("🚀 模块三：SEO 与发布")

if st.session_state.article_draft:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🖼️ 自动图片 SEO"):
            model = genai.GenerativeModel(st.session_state.flash_model)
            p = f"将文章中的 [Image X] 替换为带 Alt 标签的 Markdown 图片链接。全文如下：\n{st.session_state.article_draft}"
            st.session_state.article_draft = model.generate_content(p).text
            st.success("✅ SEO 标签已注入")
    with col2:
        if st.button("🔗 注入 10 个权威脚注"):
            model = genai.GenerativeModel(st.session_state.flash_model)
            p = f"为话题 '{st.session_state.selected_topic}' 生成 10 个 Markdown 格式的权威脚注（如 ISO 官网、行业报告）。"
            res = model.generate_content(p)
            st.session_state.article_draft += "\n\n---\n### References\n" + res.text
            st.success("✅ 脚注已追加")

    st.markdown("### 🌐 一键推送到 WordPress")
    status = st.selectbox("发布状态:", ["draft", "publish"])
    if st.button("🚀 立即推送"):
        if not all([wp_url, wp_user, wp_password]):
            st.error("请检查 WP 配置")
        else:
            try:
                endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
                data = {"title": st.session_state.selected_topic, "content": st.session_state.article_draft, "status": status}
                r = requests.post(endpoint, json=data, auth=HTTPBasicAuth(wp_user, wp_password))
                if r.status_code == 201:
                    st.balloons()
                    st.success(f"🎉 发布成功！链接: {r.json().get('link')}")
                else: st.error(f"发布失败: {r.text}")
            except Exception as e: st.error(e)
