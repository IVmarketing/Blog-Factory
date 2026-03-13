import streamlit as st
import google.generativeai as genai
import os
import requests
from requests.auth import HTTPBasicAuth

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(page_title="B2B SEO 写作工厂 (SOP 2026版)", layout="wide")

# 读取 Secrets
def get_secret(key):
    return st.secrets.get(key) or os.getenv(key)

api_key = get_secret("GEMINI_API_KEY")
wp_url = get_secret("WP_URL")
wp_user = get_secret("WP_USER")
wp_password = get_secret("WP_APP_PASSWORD")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ 缺少 GEMINI_API_KEY。请在 Advanced settings -> Secrets 中配置。")

# 智能模型选择逻辑：优先 Pro 处理复杂写作，Flash 处理简单调研
def load_model(model_type="pro"):
    # 尝试常见的模型名称字符串
    pro_names = ["gemini-1.5-pro", "models/gemini-1.5-pro", "gemini-1.5-pro-latest"]
    flash_names = ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-1.5-flash-latest"]
    
    target_names = pro_names if model_type == "pro" else flash_names
    
    # 自动获取可用列表并匹配
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for name in target_names:
            full_name = f"models/{name}" if not name.startswith("models/") else name
            if full_name in available or name in available:
                return genai.GenerativeModel(name)
        # 兜底
        return genai.GenerativeModel("gemini-1.5-flash")
    except:
        return genai.GenerativeModel("gemini-1.5-flash")

# 初始化状态
for key in ['topics', 'selected_topic', 'insights', 'article_draft']:
    if key not in st.session_state: st.session_state[key] = "" if key != 'topics' and key != 'insights' else []

# ==========================================
# 模块一：选题与调研 (对应文档 3 & 4)
# ==========================================
st.title("🏗️ 模块一：选题与调研 (Doc 3 & 4)")
st.markdown("---")

business_bg = st.text_area("1. 输入业务背景 (主营业务 + 目标市场 + 客户痛点):", height=100)

if st.button("🚀 第一步：批量策划 100 个话题"):
    if not business_bg: st.error("请先输入背景")
    else:
        with st.spinner("AI 正在根据文档 3 逻辑策划话题..."):
            model = load_model("flash")
            prompt = f"你是一位 B2B 营销专家。基于背景：{business_bg}，生成 100 个具有 SEO 价值且解决客户痛点的英文博客标题。直接输出列表，不含废话。"
            res = model.generate_content(prompt)
            st.session_state.topics = [t.strip() for t in res.text.split('\n') if t.strip()]
            st.success("✅ 100 个话题生成成功！")

if st.session_state.topics:
    selected = st.selectbox("2. 选择一个话题开始调研:", st.session_state.topics)
    if st.button("🔍 第二步：自动提取 10 条专业见解 (Insights)"):
        st.session_state.selected_topic = selected
        with st.spinner("正在模拟 Pro Search 提取 10 条行业事实见解..."):
            model = load_model("pro")
            research_prompt = f"针对话题 '{selected}'，执行文档 4 逻辑：联网分析并提炼 10 条像行业专家写的、含事实数据的见解。以'见解 X:'开头。"
            res = model.generate_content(research_prompt)
            st.session_state.insights = [i.strip() for i in res.text.split('\n') if i.strip()]
            st.success("✅ 见解提取完成！")

if st.session_state.insights:
    with st.expander("查看 10 条调研见解"):
        for i in st.session_state.insights: st.write(i)

# ==========================================
# 模块二：深度文章生成 (对应文档 1 & 5)
# ==========================================
st.markdown("---")
st.title("✍️ 模块二：1500 字深度写作 (Doc 1 & 5)")

if st.session_state.insights:
    if st.button("📝 第三步：根据见解撰写专业长文"):
        with st.spinner("Gemini 1.5 Pro 正在执行 Ghostwriter SOP 写作 (约 60 秒)..."):
            model = load_model("pro")
            insights_str = "\n".join(st.session_state.insights)
            # 融入文档 5 的专家指令
            write_prompt = f"""
            # Your Role: 资深外贸 B2B Ghostwriter，使用工程师般的专业口吻。
            # Task: 写一篇不少于 1500 字的英文博客。
            # Topic: {st.session_state.selected_topic}
            # Key Insights to include: {insights_str}
            
            # SOP Requirements (Strictly Follow):
            1. 结构：1个 H1，恰好 4个 H2，1个 Conclusion。
            2. 深度：每个 H2 段落必须详细展开，不少于 200 字，使用 H3 细分。
            3. 排版：包含至少 1 个 Markdown 表格。
            4. 图片：依次在文中插入 [Image 1], [Image 2], [Image 3], [Image 4], [Image 5] 占位符。
            5. 语气：Plain English，短句，直接解决采购经理痛点。
            """
            res = model.generate_content(write_prompt)
            st.session_state.article_draft = res.text
            st.success("✅ 1500 字文章起草完毕！")

if st.session_state.article_draft:
    st.subheader("文章预览与微调")
    st.session_state.article_draft = st.text_area("编辑正文:", st.session_state.article_draft, height=400)
    with st.expander("预览渲染效果"):
        st.markdown(st.session_state.article_draft)

# ==========================================
# 模块三：SEO 与发布 (对应文档 7, 9, 10)
# ==========================================
st.markdown("---")
st.title("🚀 模块三：SEO 增强与一键发布 (Doc 7, 9, 10)")

if st.session_state.article_draft:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🖼️ 自动注入图片 Alt/Title SEO"):
            with st.spinner("正在优化图片标签..."):
                model = load_model("flash")
                seo_p = f"为文章中的 5 个图片占位符生成 SEO Alt 标签。输出 Markdown 格式图片链接，Link 填 https://placehold.co/600x400.png。全文如下：\n{st.session_state.article_draft}"
                st.session_state.article_draft = model.generate_content(seo_p).text
                st.success("✅ SEO 标签已注入")
    with c2:
        if st.button("🔗 自动注入 10 个权威脚注"):
            with st.spinner("正在检索行业标准引用..."):
                model = load_model("flash")
                fn_p = f"为话题 '{st.session_state.selected_topic}' 生成 10 个 Markdown 格式的权威脚注（如 ISO, Statista 链接）。"
                res = model.generate_content(fn_p)
                st.session_state.article_draft += "\n\n---\n### References\n" + res.text
                st.success("✅ 权威外链已注入")

    # WordPress 发布
    st.markdown("### 🌐 一键推送 WordPress")
    status = st.selectbox("发布状态:", ["draft", "publish"])
    if st.button("🚀 确认推送"):
        if not all([wp_url, wp_user, wp_password]):
            st.error("请在 Secrets 中配置 WP 信息")
        else:
            with st.spinner("推送中..."):
                try:
                    endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
                    data = {
                        "title": st.session_state.selected_topic,
                        "content": st.session_state.article_draft,
                        "status": status
                    }
                    r = requests.post(endpoint, json=data, auth=HTTPBasicAuth(wp_user, wp_password))
                    if r.status_code == 201:
                        st.balloons()
                        st.success(f"🎉 已成功发送至 WP！文章地址: {r.json().get('link')}")
                    else:
                        st.error(f"失败: {r.status_code} - {r.text}")
                except Exception as e: st.error(f"请求出错: {e}")
else:
    st.info("完成模块二后即可解锁 SEO 与发布功能。")
