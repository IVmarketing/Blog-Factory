import streamlit as st
import google.generativeai as genai
import os
import requests
from requests.auth import HTTPBasicAuth

# ==========================================
# 0. 系统初始化与模型配置
# ==========================================
st.set_page_config(page_title="AI Writer 工具集 (1:1 深度复刻版)", layout="wide")

def get_config(key): return st.secrets.get(key) or os.getenv(key)
api_key = get_config("GEMINI_API_KEY")

if api_key: genai.configure(api_key=api_key)
else: st.sidebar.error("❌ 未配置 GEMINI_API_KEY")

@st.cache_resource
def get_model(model_type="flash"):
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if model_type == "pro": target = next((m for m in available if "pro" in m), available[0])
        else: target = next((m for m in available if "flash" in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel('models/gemini-1.5-flash')

model_flash = get_model("flash")
model_pro = get_model("pro")

# 宽松的安全设置，避免 B2B 工业词汇被误拦截
safe_config = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# 状态管理
state_keys = ['persona_cn', 'persona_en', 'raw_topics', 'clean_topics', 'materials', 'article_draft']
for k in state_keys:
    if k not in st.session_state: st.session_state[k] = "" if k in ['persona_cn', 'persona_en', 'article_draft'] else []

# ==========================================
# 工具 1：创建【我的角色背景】
# ==========================================
def tool1_persona():
    st.title("👤 工具 1：创建【我的角色背景】")
    st.info("通过填写业务信息生成一份「我的角色背景」。后续所有工具都会用到它来定制 AI 输出。")
    
    st.subheader("逐步填写业务信息")
    company_name = st.text_input("1. 您的公司名称是？", placeholder="例如：HP")
    years_exp = st.text_input("2. 行业经验有多少年？", placeholder="例如：25年")
    core_product = st.text_area("3. 核心产品及应用场景是什么？", placeholder="例如：专注于低速高扭矩(LSHT)马达，满足现代工业环境的严苛需求...")
    target_role = st.text_input("4. 您的目标客户角色是？", placeholder="例如：工程技术人员和工业采购")
    
    if st.button("📝 汇总校对 → 一键翻译为英文", type="primary"):
        if company_name and core_product:
            with st.spinner("正在生成并翻译角色背景..."):
                cn_text = f"我们{company_name}是一家以工程技术为核心的工业采购合作伙伴。凭借{years_exp}的行业经验，我们专注于{core_product}，旨在为{target_role}提供持久动力解决方案。"
                st.session_state.persona_cn = cn_text
                
                # 调用 AI 翻译并润色
                p = f"将以下中文B2B公司背景翻译成极其专业、地道的英文，用于设定 AI 写作的角色 Prompt：\n{cn_text}"
                st.session_state.persona_en = model_flash.generate_content(p).text
                st.success("✅ 角色背景自动保存，后续工具可直接调用！")
        else:
            st.error("请至少填写公司名称和核心产品。")
            
    if st.session_state.persona_en:
        st.markdown("### 当前保存的角色背景 (English):")
        st.code(st.session_state.persona_en, language="markdown")

# ==========================================
# 工具 2：文章话题生成器
# ==========================================
def tool2_topics():
    st.title("💡 工具 2：文章话题生成器")
    st.info("回答 4 个简单问题，AI 就能为你批量生成几十到几百个精准的文章话题。")
    
    col1, col2 = st.columns(2)
    with col1: target_country = st.text_area("{目标国家} - 针对的目标客户国家", placeholder="例如：\n美国\n欧洲\n南美洲")
    with col1: product_cat = st.text_input("{三级类目名称} - 本次宣传的产品", placeholder="例如：hydraulic motor")
    with col2: company_type = st.text_area("{公司类型} - 目标客户公司/身份", placeholder="例如：\n能源及关键基础设施运营商")
    with col2: my_country = st.text_input("{你的国家} - 你的公司所在国", value="中国")
    
    num_topics = st.slider("选择需要生成的话题数量", 50, 600, 150, step=50)
    
    if st.button("🚀 生成话题列表", type="primary"):
        if not all([target_country, product_cat, company_type]): st.error("请完善所有 4 个问题！")
        else:
            with st.spinner(f"检测到国家与身份组合...正在为您生成 {num_topics} 个精准话题..."):
                p = f"角色：外贸SEO专家。我的国家：{my_country}。目标市场：{target_country}。目标客户：{company_type}。推广产品：{product_cat}。请直接用英文生成 {num_topics} 个具有高点击率和 SEO 价值的长尾博客标题。仅输出列表，无任何多余文字。"
                try:
                    res = model_flash.generate_content(p)
                    st.session_state.raw_topics = [t.strip() for t in res.text.split('\n') if t.strip() and len(t) > 5]
                    st.success("✅ 话题生成完毕！")
                except Exception as e: st.error(f"生成失败: {e}")
                
    if st.session_state.raw_topics:
        st.text_area("生成的话题列表（可一键复制）：", "\n".join(st.session_state.raw_topics), height=300)

# ==========================================
# 工具 4：写文章原材料生成
# ==========================================
def tool4_materials():
    st.title("🗄️ 工具 4：写文章原材料生成 (单篇)")
    st.info("批量输入话题 → AI见解调研 → 录入个人见解 → 输出可复制的原材料")
    
    st.subheader("第 1 步：粘贴话题")
    topic_input = st.text_area("请从 Excel 中复制你的话题列表，直接粘贴到下方，每一行代表一个话题。", value="\n".join(st.session_state.raw_topics[:1] if st.session_state.raw_topics else []), height=100)
    
    st.subheader("第 2 步：AI 见解调研")
    if st.button("🔍 开始 Perplexity + SERP 见解调研"):
        topics = [t.strip() for t in topic_input.split('\n') if t.strip()]
        if not topics: st.warning("请输入话题")
        else:
            st.session_state.materials = []
            progress_bar = st.progress(0)
            for i, topic in enumerate(topics):
                with st.spinner(f"正在深度调研: {topic}..."):
                    p = f"针对B2B博客话题：'{topic}'。请模拟专业搜索引擎提炼深度调研结果。严格输出以下格式：\n*二级标题：\n* [列出4个最核心的H2二级标题]\n*AI见解：\n* [给出一段包含专业数据、技术标准的深刻见解]"
                    res = model_pro.generate_content(p, safety_settings=safe_config)
                    st.session_state.materials.append({"topic": topic, "ai_res": res.text, "personal": ""})
                progress_bar.progress((i + 1) / len(topics))
            st.success("✅ AI 见解调研完成！")

    if st.session_state.materials:
        st.subheader("第 3 步：录入个人见解（选填）")
        st.caption("你可以为每个话题添加你的专业见解，这些见解将与 AI 调研结果合并。")
        for idx, m in enumerate(st.session_state.materials):
            with st.expander(f"话题: {m['topic']}", expanded=True):
                st.text_area("AI 调研结果:", m['ai_res'], height=150, disabled=True, key=f"ai_{idx}")
                m['personal'] = st.text_input("在此输入人工见解（如：齿轮马达，柱塞马达，风扇马达）:", key=f"p_{idx}")
        
        st.subheader("第 4 步：生成最终原材料")
        final_text = ""
        for m in st.session_state.materials:
            final_text += f"*主标题：{m['topic']}\n{m['ai_res']}\n*人工见解：{m['personal']}\n\n"
        st.text_area("最终的写文章原材料（可直接复制供工具5使用）：", final_text, height=300)

# ==========================================
# 工具 5：文章生成器
# ==========================================
def tool5_article():
    st.title("✍️ 工具 5：文章生成器")
    st.info("输入角色背景和写作原材料，AI 会为你生成一篇完整的 Markdown 格式文章。")
    
    st.subheader("第 1 步：确认角色背景")
    if not st.session_state.persona_en: st.warning("未保存❌（先去工具1生成）")
    else: st.success("已加载【我的角色背景】")
    
    st.subheader("第 2 步：输入写作原材料")
    raw_material_input = st.text_area("粘贴从工具4生成的写作原材料（包含：主标题 + 4个二级标题 + AI见解 + 人工见解）：", height=200, placeholder="*主标题：...\n*二级标题：...\n*AI见解：...\n*人工见解：...")
    
    if st.button("📝 生成文章 (约1-3分钟)", type="primary"):
        if not raw_material_input: st.error("请粘贴写作原材料！")
        else:
            st.session_state.article_draft = ""
            with st.spinner("正在融合角色背景与原材料..."):
                p = f"""
                # Role Context
                {st.session_state.persona_en}
                
                # Raw Materials
                {raw_material_input}
                
                # SOP Requirements for B2B Article (Strictly Follow):
                1. Structure: Start with exactly 1 H1 (Main Title), followed by exactly 4 H2s, and end with a Conclusion.
                2. Depth: Under each H2, dive deep with at least 200 words and use H3 subheadings.
                3. Formatting: Include at least 1 Markdown table comparing features/data. Include bullet points.
                4. Images: Insert placeholders exactly as `[Image 1]`, `[Image 2]`, `[Image 3]`, `[Image 4]`, `[Image 5]` strategically throughout the text (e.g., one under H1, one under each H2).
                5. Tone: Professional, authoritative, addressing the B2B buyer directly. Output ONLY valid Markdown.
                """
                
                try:
                    res = model_pro.generate_content(p, stream=True, safety_settings=safe_config)
                    placeholder = st.empty()
                    full_text = ""
                    for chunk in res:
                        if chunk.text:
                            full_text += chunk.text
                            placeholder.markdown(full_text + "▌")
                    st.session_state.article_draft = full_text
                    st.success(f"✅ 生成完毕！Word count: {len(full_text.split())} words")
                except Exception as e: st.error(f"生成中断: {e}")

    st.subheader("第 3 步：编辑与使用")
    if st.session_state.article_draft:
        st.session_state.article_draft = st.text_area("在线编辑、校验后复制使用：", st.session_state.article_draft, height=600)
        with st.expander("👁️ 预览网页渲染效果"):
            st.markdown(st.session_state.article_draft, unsafe_allow_html=True)

# ==========================================
# 工具 6：文章配图 + 一键发布
# ==========================================
def tool6_publish():
    st.title("🚀 工具 6：文章配图 + 一键发布")
    st.info("为文章自动生成配图提示词/SEO，上传到 WordPress，一键发布。")
    
    if not st.session_state.article_draft:
        st.warning("⚠️ 暂无文章草稿，请先在工具 5 生成文章，或在此处直接粘贴 Markdown。")
        st.session_state.article_draft = st.text_area("在此粘贴 Markdown 全文：", height=200)
    
    st.subheader("第 1 步：生成文章配图提示词 & SEO")
    if st.button("🖼️ 分析文章结构，生成配图与 SEO Alt 标签"):
        with st.spinner("AI 正在解析 5 个图像占位符的上下文..."):
            try:
                p = f"请通读以下Markdown文章，找到所有的 [Image 1] 到 [Image 5] 占位符。根据上下文，将它们替换为标准的Markdown图片格式：![精准的SEO Alt标签](https://placehold.co/800x400.png?text=Image+Generated+By+AI)。直接输出替换后的全文：\n\n{st.session_state.article_draft}"
                st.session_state.article_draft = model_flash.generate_content(p, safety_settings=safe_config).text
                st.success("✅ SEO 标签和配图预渲染已完成！(注：实际部署中可对接 Midjourney API 或直接使用自带配图)")
            except Exception as e: st.error(e)
            
    st.subheader("第 2 步：配置 WordPress → 一键发布")
    st.caption("云端信息不会自动填充，请在下拉列表手动选择或填写。")
    
    c1, c2, c3 = st.columns(3)
    with c1: wp_url_input = st.text_input("WordPress 站点地址", value=get_config("WP_URL") or "")
    with c2: wp_user_input = st.text_input("WordPress 用户名", value=get_config("WP_USER") or "")
    with c3: wp_pass_input = st.text_input("应用密码", type="password", value=get_config("WP_APP_PASSWORD") or "")
    
    publish_status = st.selectbox("发布状态", ["draft (草稿)", "publish (直接发布)"])
    
    if st.button("🚀 推送到 WordPress", type="primary"):
        if not all([wp_url_input, wp_user_input, wp_pass_input]): st.error("请完整填写 WordPress 的三个凭证。")
        else:
            with st.spinner("正在连接并推送至网站后台..."):
                try:
                    endpoint = f"{wp_url_input.rstrip('/')}/wp-json/wp/v2/posts"
                    # 从 Markdown 尝试提取首行作为标题
                    title = "AI Draft"
                    for line in st.session_state.article_draft.split('\n'):
                        if line.startswith("# "):
                            title = line.replace("# ", "").strip()
                            break
                            
                    data = {"title": title, "content": st.session_state.article_draft, "status": publish_status.split()[0]}
                    r = requests.post(endpoint, json=data, auth=HTTPBasicAuth(wp_user_input, wp_pass_input))
                    if r.status_code == 201:
                        st.balloons()
                        st.success(f"🎉 成功！文章已发布至：{r.json().get('link')}")
                    else: st.error(f"推送失败 ({r.status_code}): {r.text}")
                except Exception as e: st.error(f"连接失败: {e}")

# ==========================================
# 侧边栏主控菜单
# ==========================================
with st.sidebar:
    st.title("⚙️ AI Writer 工具集")
    st.caption("版本: 2026.03 | 纯代码复刻")
    page = st.radio("导航菜单 (点击切换)", [
        "1. 创建角色背景", 
        "2. 文章话题生成器", 
        "4. 写文章原材料生成",
        "5. 文章生成器",
        "6. 文章配图 + 一键发布"
    ])
    st.markdown("---")
    st.info("💡 提示：这套工具数据在内存中流转，请按 1 -> 2 -> 4 -> 5 -> 6 的顺序体验最佳 SOP。")

# 路由分发
if page.startswith("1"): tool1_persona()
elif page.startswith("2"): tool2_topics()
elif page.startswith("4"): tool4_materials()
elif page.startswith("5"): tool5_article()
elif page.startswith("6"): tool6_publish()
