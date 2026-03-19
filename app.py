import streamlit as st
import google.generativeai as genai
import os
import math
import time
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime

# ==========================================
# 0. 全局配置与模型初始化 (全局仅限执行一次)
# ==========================================
st.set_page_config(page_title="AI Writer 工具集 (1:1 深度复刻版)", layout="wide")

# 提取 API Key
def get_config(key): return st.secrets.get(key) or os.getenv(key)
api_key = get_config("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ 未检测到 GEMINI_API_KEY。请在 Streamlit Secrets 或环境变量中配置。")
    st.stop()

# 智能缓存与加载模型
@st.cache_resource
def get_model(model_type="flash"):
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in available if model_type in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel(f'models/gemini-1.5-{model_type}')

model_flash = get_model("flash")
model_pro = get_model("pro")

# 统一的宽松安全设置，防止 B2B 工业词汇被误拦截
safe_config = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# ==========================================
# 1. 全局状态管理 (集中初始化，避免冲突)
# ==========================================
def init_session_state():
    # --- Tool 1: 角色背景 ---
    if 't1_step' not in st.session_state: st.session_state.t1_step = 0
    if 't1_answers' not in st.session_state: st.session_state.t1_answers = [""] * 20
    if 'persona_cn' not in st.session_state: st.session_state.persona_cn = ""
    if 'persona_en' not in st.session_state: st.session_state.persona_en = ""
    
    # --- Tool 2: 话题生成 ---
    if 't2_step' not in st.session_state: st.session_state.t2_step = 1
    if 't2_countries' not in st.session_state: st.session_state.t2_countries = ""
    if 't2_product' not in st.session_state: st.session_state.t2_product = ""
    if 't2_company_type' not in st.session_state: st.session_state.t2_company_type = ""
    if 't2_my_country' not in st.session_state: st.session_state.t2_my_country = "中国"
    if 't2_topic_count' not in st.session_state: st.session_state.t2_topic_count = 150
    if 't2_results' not in st.session_state: st.session_state.t2_results = []
    
    # --- Tool 3: 原材料生成 ---
    if 't4_m_step' not in st.session_state: st.session_state.t4_m_step = 1
    if 't4_m_topics_raw' not in st.session_state: st.session_state.t4_m_topics_raw = ""
    if 't4_m_topics_list' not in st.session_state: st.session_state.t4_m_topics_list = []
    if 't4_m_ai_results' not in st.session_state: st.session_state.t4_m_ai_results = {}
    if 't4_m_personal_insights' not in st.session_state: st.session_state.t4_m_personal_insights = {}
    if 't4_m_batch_personal' not in st.session_state: st.session_state.t4_m_batch_personal = ""
    if 't4_m_final_materials' not in st.session_state: st.session_state.t4_m_final_materials = ""
    
    # --- Tool 4: 文章生成 ---
    if 't5_article_draft' not in st.session_state: st.session_state.t5_article_draft = ""
    if 't5_validation_res' not in st.session_state: st.session_state.t5_validation_res = ""
    
    # --- Tool 5: 配图与发布 ---
    if 't6_img_prompts' not in st.session_state: st.session_state.t6_img_prompts = ""
    if 't6_seo_markdown' not in st.session_state: st.session_state.t6_seo_markdown = ""
    if 't6_final_markdown' not in st.session_state: st.session_state.t6_final_markdown = ""

init_session_state()

# ==========================================
# 工具 1：创建【我的角色背景】
# ==========================================
def tool1_persona():
    st.title("👤 工具 1：创建【我的角色背景】")
    st.markdown("通过逐步问答，完整描述您的业务和目标客户。这份背景将作为所有自动化写作工具的“灵魂”。")
    
    QUESTIONS = [
        {"title": "基本信息", "q": "您的姓名和职位？", "example": "Jack，市场经理"},
        {"title": "基本信息", "q": "您的公司名称（或品牌名称）是什么？", "example": "hgp 制造"},
        {"title": "基本信息", "q": "您的公司官方网站和联系邮箱是什么？", "example": "www.hgp.com, jack@hpc.com"},
        {"title": "业务运营", "q": "您的公司总部在哪里？是否有海外分支机构或生产基地？", "example": "总部在新加坡，在中国和越南有分公司"},
        {"title": "业务运营", "q": "您主要销售的核心产品或服务是什么？", "example": "定制机械零件"},
        {"title": "产品特征", "q": "您的产品有哪些独特的生产特点或技术门槛？", "example": "需根据图纸开模定制、在越南本地生产避开高关税"},
        {"title": "商业模式", "q": "您的核心商业模式是什么？", "example": "B2B 国际出口贸易，仅限大宗批发"},
        {"title": "商业模式", "q": "除了产品本身，您还为客户提供哪些增值服务？", "example": "寻源采购、验厂、质量检测、门到门物流管理"},
        {"title": "市场营销", "q": "您的主要出口/销售目标国家或地区是哪里？", "example": "美国、加拿大"},
        {"title": "市场营销", "q": "您目前主要通过哪些营销渠道获取客户？", "example": "公司官网 SEO、阿里巴巴、LinkedIn"},
        {"title": "目标客户", "q": "您的典型客户在企业中通常担任什么职位？", "example": "采购经理、产品总监或 CEO"},
        {"title": "目标客户", "q": "您的客户所在企业属于什么规模和类型？", "example": "北美中等规模的进口批发商或中型制造商"},
        {"title": "客户画像", "q": "您的典型客户的大致年龄段和性格特征是什么？", "example": "50岁左右，行业知识丰富，自信，习惯主导对话"},
        {"title": "客户画像", "q": "您的客户在沟通上有何偏好？", "example": "喜欢简短直接的邮件，讨厌挤牙膏式回复，要求极度专业"},
        {"title": "客户痛点", "q": "客户目前的盈利模式（赚钱方式）是什么？", "example": "低成本进口定制零件，然后高价转售给美国本土制造商"},
        {"title": "客户痛点", "q": "在选择供应商时，客户最看重哪些核心能力？", "example": "工程设计能力、项目进度管理能力和质量控制能力"},
        {"title": "客户偏好", "q": "客户受宏观环境影响，在采购地区上有何偏好？", "example": "为规避中美关税，更倾向于从东南亚国家采购"},
        {"title": "客户偏好", "q": "客户在采购流程和商务条件上有什么特殊要求？", "example": "要求提供门到门的物流解决方案，以及支持赊销"},
        {"title": "客户行为", "q": "客户目前习惯通过什么方式寻找新供应商？", "example": "Google 搜索、阿里巴巴展会"},
        {"title": "核心痛点", "q": "客户在采购过程中遇到的最大、最痛的 3 个问题是什么？", "example": "1. 销售不懂技术；2. 交期延误导致赔钱；3. 品控差导致尺寸不达标"}
    ]

    progress = st.session_state.t1_step / len(QUESTIONS)
    st.progress(progress, text=f"当前进度: {st.session_state.t1_step} / {len(QUESTIONS)}")

    if st.session_state.t1_step < len(QUESTIONS):
        q_data = QUESTIONS[st.session_state.t1_step]
        st.subheader(f"Step {st.session_state.t1_step + 1}: {q_data['title']}")
        st.markdown(f"### **{q_data['q']}**")
        st.info(f"💡 **参考示例：** {q_data['example']}")
        
        current_answer = st.text_area("您的回答（支持随时修改）：", value=st.session_state.t1_answers[st.session_state.t1_step], height=150, key=f"t1_input_{st.session_state.t1_step}")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("⬅️ 上一步", disabled=(st.session_state.t1_step == 0), key="t1_prev"):
                st.session_state.t1_answers[st.session_state.t1_step] = current_answer
                st.session_state.t1_step -= 1
                st.rerun()
        with col2:
            if st.button("下一步 ➡️", type="primary", key="t1_next"):
                st.session_state.t1_answers[st.session_state.t1_step] = current_answer
                st.session_state.t1_step += 1
                st.rerun()
    else:
        st.success("🎉 所有问题已填写完毕！请检查您的业务背景汇总：")
        draft_cn = f"""
        ## 我的角色：
        ### 关于我的业务
        姓名/职位：{st.session_state.t1_answers[0]}
        品牌名称：{st.session_state.t1_answers[1]}
        网站/邮箱：{st.session_state.t1_answers[2]}
        当前运营：{st.session_state.t1_answers[3]}
        核心产品：{st.session_state.t1_answers[4]}
        产品特点：{st.session_state.t1_answers[5]}
        商业模式：{st.session_state.t1_answers[6]}
        我们的服务：{st.session_state.t1_answers[7]}
        主要出口国家：{st.session_state.t1_answers[8]}
        营销渠道：{st.session_state.t1_answers[9]}

        ### 关于我的典型客户
        职位：{st.session_state.t1_answers[10]}
        企业规模与类型：{st.session_state.t1_answers[11]}
        年龄与性格特点：{st.session_state.t1_answers[12]}
        沟通偏好：{st.session_state.t1_answers[13]}
        盈利模式：{st.session_state.t1_answers[14]}
        采购偏好/看重能力：{st.session_state.t1_answers[15]}
        采购地区偏好：{st.session_state.t1_answers[16]}
        采购要求/商务条件：{st.session_state.t1_answers[17]}
        供应商寻找方式：{st.session_state.t1_answers[18]}
        核心痛点：
        {st.session_state.t1_answers[19]}
        """
        st.session_state.persona_cn = st.text_area("您可以直接在此修改最终的中文草稿：", value=draft_cn.strip(), height=400, key="t1_draft_cn")
        
        if st.button("✨ 一键翻译并保存为英文角色指令 (System Prompt)", type="primary"):
            with st.spinner("AI 正在将您的业务背景转化为极其专业的英文 System Prompt..."):
                translate_prompt = f"你是一位资深的 B2B 外贸营销专家。请将以下中文的客户业务背景，翻译并润色成一段极其地道、专业的英文，作为后续 AI 的 System Prompt。直接输出英文结果：\n\n{st.session_state.persona_cn}"
                try:
                    st.session_state.persona_en = model_flash.generate_content(translate_prompt, safety_settings=safe_config).text
                    st.success("✅ 英文角色指令已生成并存入系统！")
                except Exception as e:
                    st.error(f"翻译失败: {e}")
                    
        if st.session_state.persona_en:
            st.markdown("### 🏆 最终保存的英文角色指令 (供 AI 写作使用):")
            st.code(st.session_state.persona_en, language="markdown")
            if st.button("⬅️ 返回修改问题", key="t1_back"):
                st.session_state.t1_step = 0
                st.rerun()

# ==========================================
# 工具 2：文章话题生成器
# ==========================================
def tool2_topics():
    st.title("💡 工具 2：文章话题生成器")
    st.markdown("通过回答 4 个简单问题，AI 就能为你生成大量精准的文章话题。")
    st.divider()

    step = st.session_state.t2_step
    st.subheader(f"第 {step} / 4 步")

    if step == 1:
        st.markdown("### **{目标国家}**")
        current_val = st.text_area("你写文章针对的目标客户国家是哪一个或哪些？(每行一个)", value=st.session_state.t2_countries, height=120)
        if st.button("下一步 ➡️", type="primary", key="t2_next_1"):
            if not current_val.strip(): st.error("请至少填写一个国家")
            else:
                st.session_state.t2_countries = current_val
                st.session_state.t2_step = 2
                st.rerun()

    elif step == 2:
        st.markdown("### **{三级类目名称}**")
        current_val = st.text_input("你本次想写文章宣传的产品是什么？(如：hydraulic motor)", value=st.session_state.t2_product)
        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t2_prev_2"):
                st.session_state.t2_step = 1
                st.rerun()
        with c2:
            if st.button("下一步 ➡️", type="primary", key="t2_next_2"):
                if not current_val.strip(): st.error("请输入产品名称")
                else:
                    st.session_state.t2_product = current_val
                    st.session_state.t2_step = 3
                    st.rerun()

    elif step == 3:
        st.markdown("### **{公司类型}**")
        current_val = st.text_area("目标客户公司/身份类型是什么？(每行一个)", value=st.session_state.t2_company_type, height=120)
        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t2_prev_3"):
                st.session_state.t2_step = 2
                st.rerun()
        with c2:
            if st.button("下一步 ➡️", type="primary", key="t2_next_3"):
                if not current_val.strip(): st.error("请至少填写一种公司类型")
                else:
                    st.session_state.t2_company_type = current_val
                    st.session_state.t2_step = 4
                    st.rerun()

    elif step == 4:
        st.markdown("### **{你的国家}**")
        current_val = st.text_input("你想宣传的公司是哪个国家的？", value=st.session_state.t2_my_country)
        target_count = st.slider("选择想生成的话题数量 (50~600)", min_value=50, max_value=600, value=st.session_state.t2_topic_count, step=50)
        
        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t2_prev_4"):
                st.session_state.t2_step = 3
                st.rerun()
        with c2:
            if st.button("🚀 生成话题列表", type="primary", key="t2_gen_btn"):
                st.session_state.t2_my_country = current_val
                st.session_state.t2_topic_count = target_count
                
                c_list = [c.strip() for c in st.session_state.t2_countries.split('\n') if c.strip()]
                t_list = [t.strip() for t in st.session_state.t2_company_type.split('\n') if t.strip()]
                
                total_combo = len(c_list) * len(t_list)
                per_combo = math.ceil(target_count / total_combo)
                st.session_state.t2_results = []
                
                with st.container():
                    st.info(f"检测到 {len(c_list)} 个国家 × {len(t_list)} 个身份类型 = {total_combo} 个组合。自动去重中...")
                    pb = st.progress(0)
                    curr = 0
                    
                    for tc in c_list:
                        for ct in t_list:
                            curr += 1
                            with st.spinner(f"[{curr}/{total_combo}] 正在生成: {tc} × {ct}..."):
                                prompt = f"角色：外贸SEO专家。我的国家：{current_val}。产品：{st.session_state.t2_product}。目标市场：{tc}。目标客户：{ct}。请生成 {per_combo} 个精准英文文章话题（标题）。直接输出列表，不带编号。"
                                try:
                                    if curr > 1: time.sleep(1.5) 
                                    res = model_flash.generate_content(prompt, safety_settings=safe_config)
                                    cl = [l.strip().lstrip('0123456789.-* ') for l in res.text.strip().split('\n') if l.strip()]
                                    st.session_state.t2_results.extend(cl)
                                except Exception as e: st.error(e)
                            pb.progress(curr / total_combo)
                    
                    st.session_state.t2_results = list(dict.fromkeys(st.session_state.t2_results))[:target_count]
                    st.success("🎉 话题生成完毕！")

    if st.session_state.t2_results:
        st.markdown("---")
        final_text = "\n".join(st.session_state.t2_results)
        st.text_area(f"话题列表 (共 {len(st.session_state.t2_results)} 个)：", value=final_text, height=300)
        c1, c2 = st.columns(2)
        with c1: st.download_button("📥 导出 CSV", "Topic\n"+final_text, f"topics.csv", "text/csv")
        with c2:
            if st.button("🔄 重置此工具"):
                st.session_state.t2_step = 1
                st.session_state.t2_results = []
                st.rerun()

# ==========================================
# 工具 3：写文章原材料生成
# ==========================================
def tool3_materials():
    st.title("🗄️ 工具 3：写文章原材料生成")
    st.caption("把话题转化为完整的写作原材料，包含 AI 深度调研结果（Perplexity + Google SERP）和你的个人见解。")
    st.divider()

    step = st.session_state.t4_m_step
    st.subheader(f"第 {step} / 4 步")

    if step == 1:
        st.markdown("### 第 1 步：批量粘贴话题")
        default_val = "\n".join(st.session_state.t2_results[:2]) if st.session_state.t2_results else ""
        current_val = st.text_area("请从 Excel / 工具 2 中复制话题列表粘贴到下方：", value=st.session_state.t4_m_topics_raw or default_val, height=150)
        
        if st.button("下一步 ➡️ (开始 AI 调研)", type="primary"):
            if not current_val.strip(): st.error("请至少输入一个话题！")
            else:
                st.session_state.t4_m_topics_raw = current_val
                st.session_state.t4_m_topics_list = [t.strip() for t in current_val.split('\n') if t.strip()]
                st.session_state.t4_m_step = 2
                st.rerun()

    elif step == 2:
        st.markdown("### 第 2 步：AI 见解调研")
        topics = st.session_state.t4_m_topics_list
        total = len(topics)
        
        if len(st.session_state.t4_m_ai_results) < total:
            pb = st.progress(0)
            st_txt = st.empty()
            for idx, topic in enumerate(topics):
                if topic in st.session_state.t4_m_ai_results: continue
                st_txt.text(f"正在深度调研 ({idx+1}/{total}): {topic}")
                prompt = f"针对话题：{topic}\n提炼出6条来自SERP的关键见解，再补充4条逻辑推理见解。同时提供4个相关的英文二级标题。\n严格按照格式：\n*二级标题：\n* [H2 1]...\n*AI见解：\n1. [见解1]..."
                try:
                    if idx > 0: time.sleep(1.5)
                    st.session_state.t4_m_ai_results[topic] = model_pro.generate_content(prompt, safety_settings=safe_config).text
                except Exception as e:
                    st.session_state.t4_m_ai_results[topic] = "调研失败。"
                pb.progress((idx + 1) / total)
            st_txt.success(f"✅ 调研完成 ({total}/{total})")
        else:
            st.success(f"✅ 调研完成 ({total}/{total})")

        with st.expander("👁️ 查看 AI 调研结果"):
            for t in topics:
                st.markdown(f"**{t}**\n{st.session_state.t4_m_ai_results.get(t, '')}")

        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t4_m_prev2"):
                st.session_state.t4_m_step = 1
                st.rerun()
        with c2:
            if st.button("下一步 ➡️ (录入个人见解)", type="primary"):
                st.session_state.t4_m_step = 3
                st.rerun()

    elif step == 3:
        st.markdown("### 第 3 步：录入个人见解（选填）")
        topics = st.session_state.t4_m_topics_list
        
        mode = st.radio("录入方式：", ["逐一输入", "批量粘贴"])
        if mode == "逐一输入":
            for idx, topic in enumerate(topics):
                if topic not in st.session_state.t4_m_personal_insights: st.session_state.t4_m_personal_insights[topic] = ""
                st.session_state.t4_m_personal_insights[topic] = st.text_input(f"{idx+1}. {topic}", value=st.session_state.t4_m_personal_insights[topic])
        else:
            b_input = st.text_area("批量粘贴 (每行对应一个话题)：", value=st.session_state.t4_m_batch_personal, height=150)
            st.session_state.t4_m_batch_personal = b_input
            b_lines = [l.strip() for l in b_input.split('\n')]
            for idx, topic in enumerate(topics):
                st.session_state.t4_m_personal_insights[topic] = b_lines[idx] if idx < len(b_lines) else ""

        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t4_m_prev3"):
                st.session_state.t4_m_step = 2
                st.rerun()
        with c2:
            if st.button("下一步 ➡️ (生成结果)", type="primary"):
                st.session_state.t4_m_step = 4
                st.rerun()

    elif step == 4:
        st.markdown("### 第 4 步：生成结果")
        out = ""
        for t in st.session_state.t4_m_topics_list:
            ai_r = st.session_state.t4_m_ai_results.get(t, "")
            p_r = st.session_state.t4_m_personal_insights.get(t, "")
            out += f"*主标题：{t}\n{ai_r}\n*人工见解：{p_r}\n\n--------------------------------------------------\n\n"
        
        st.session_state.t4_m_final_materials = out
        st.text_area("最终原材料提取结果 (直接复制供工具5使用)：", value=out.strip(), height=400)
        
        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t4_m_prev4"):
                st.session_state.t4_m_step = 3
                st.rerun()
        with c2:
            if st.button("🔄 重置此工具"):
                st.session_state.t4_m_step = 1
                st.session_state.t4_m_topics_raw = ""
                st.session_state.t4_m_ai_results = {}
                st.session_state.t4_m_personal_insights = {}
                st.rerun()

# ==========================================
# 工具 4：文章生成器
# ==========================================
def tool5_article():
    st.title("✍️ 工具 5：文章生成器")
    st.caption("输入角色背景和写作原材料，AI 会为你生成一篇完整的 Markdown 格式文章。")
    st.divider()

    st.subheader("第 1 步：确认角色背景")
    persona_input = st.text_area("角色背景 (默认读取工具1)：", value=st.session_state.persona_en, height=150)

    st.subheader("第 2 步：输入写作原材料")
    mat_input = st.text_area("粘贴从工具4生成的写作原材料 (取单篇即可)：", value=st.session_state.t4_m_final_materials.split('---')[0].strip() if st.session_state.t4_m_final_materials else "", height=200)

    if st.button("📝 生成文章 (流式输出 约1-3分钟)", type="primary"):
        if not mat_input.strip() or not persona_input.strip(): st.error("背景和原材料不能为空！")
        else:
            st.session_state.t5_article_draft = ""
            with st.spinner("AI 正在严格执行 SOP 撰写 1500 字长文..."):
                prompt = f"""
                # Your Role: Write a blog article matching my tone.
                # Materials:
                {mat_input}
                
                Structure strictly as follows:
                # [Main Title?]
                ![alt]("https://placehold.co/600x400.jpg")
                [PAS intro, first person, max 30 words]
                **[Snippet answer, 30-50 words]**
                [Transition]
                
                ## [H2 Title 1?]
                [PAS intro, max 30 words]
                **[Snippet answer, 30-50 words]**
                ![alt]("https://placehold.co/600x400.jpg")
                [Dive deeper paragraph: Min 200 words, use H3 and Markdown tables]
                (Repeat for exactly 4 H2s)
                
                ## Conclusion
                [Summary, max 30 words]

                # My Background:
                {persona_input}
                
                # Requirements: Total > 1500 words. Plain English. Only Markdown output. No meta-explanations like 'Dive deeper paragraph:'.
                """
                try:
                    res = model_pro.generate_content(prompt, stream=True, safety_settings=safe_config)
                    ph = st.empty()
                    txt = ""
                    for chunk in res:
                        if chunk.text:
                            txt += chunk.text
                            ph.markdown(txt + "▌")
                    st.session_state.t5_article_draft = txt
                    st.success("✅ 文章生成完毕！")
                except Exception as e: st.error(f"生成中断: {e}")

    if st.session_state.t5_article_draft:
        st.subheader("第 3 步：编辑与使用")
        c1, c2, c3 = st.columns([1.5, 2, 2])
        with c1:
            if st.button("✅ 一键校验格式"):
                d = st.session_state.t5_article_draft
                st.session_state.t5_validation_res = f"字数: {len(d.split())} 词 | H2数量: {d.count('## ')-d.count('### ')-1} | 图片: {d.count('![')} | 表格: {d.count('|---|')}"
        with c2: lang = st.selectbox("翻译:", ["简体中文", "Español", "Deutsch"], label_visibility="collapsed")
        with c3:
            if st.button("🌐 翻译此文"):
                try:
                    res = model_flash.generate_content(f"Translate to {lang}, keep markdown:\n{st.session_state.t5_article_draft}", safety_settings=safe_config)
                    st.session_state.t5_article_draft = res.text
                    st.success(f"已翻译为 {lang}")
                except Exception as e: st.error(e)

        if st.session_state.t5_validation_res: st.info(st.session_state.t5_validation_res)
        
        st.session_state.t5_article_draft = st.text_area("Markdown 编辑器：", value=st.session_state.t5_article_draft, height=500)

# ==========================================
# 工具 5：文章配图 + 一键发布
# ==========================================
def tool6_publish():
    st.title("🚀 工具 6：文章配图 + 一键发布")
    st.divider()

    st.subheader("第 1 步 & 第 2 步：确认素材")
    persona_input = st.text_area("角色背景 (用于配图基调)：", value=st.session_state.persona_en, height=100)
    md_input = st.text_area("粘贴 Markdown 文章全文 (默认读取工具5)：", value=st.session_state.t5_article_draft, height=200)

    st.subheader("第 3 步：自动处理 (图片提示词 + SEO + 脚注)")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎨 1. 生成 5 张配图 Prompt", use_container_width=True):
            if not md_input: st.error("请粘贴文章！")
            else:
                p = f"Generate FIVE Midjourney/Recraft prompts for this article based on my persona. Format: Chinese Title followed by 70+ words English description.\nArticle:\n{md_input}\nPersona:\n{persona_input}"
                st.session_state.t6_img_prompts = model_flash.generate_content(p, safety_settings=safe_config).text
                st.success("✅ 配图 Prompt 生成完毕")
    with c2:
        if st.button("🖼️ 2. 优化图片 SEO", use_container_width=True):
            if not md_input: st.error("请粘贴文章！")
            else:
                p = f"Replace all `[Image X]` or dummy image tags in this markdown with SEO markdown: `![Alt Text (≤15 words)](https://placehold.co/800x400.png \"Title (≤5 words)\")`. Output full markdown.\n\n{md_input}"
                st.session_state.t6_seo_markdown = model_flash.generate_content(p, safety_settings=safe_config).text
                st.success("✅ 图片 SEO 注入完毕")
    with c3:
        if st.button("🔗 3. 注入 10 个双向脚注", use_container_width=True):
            src = st.session_state.t6_seo_markdown or md_input
            if not src: st.error("请先完成前置步骤！")
            else:
                p = f"Insert exactly 10 manual bidirectional footnotes (using `<sup>[1](#footnote-1){{#ref-1}}</sup>` in text and `<span id=\"footnote-1\">1. Short explanation. [↩︎](#ref-1)</span>` in a new '## Footnotes' section at the end) into this article. Output full markdown.\n\n{src}"
                st.session_state.t6_final_markdown = model_pro.generate_content(p, safety_settings=safe_config).text
                st.success("✅ 脚注系统植入完毕")

    if st.session_state.t6_img_prompts:
        with st.expander("👁️ 查看生成的配图 Prompt"): st.code(st.session_state.t6_img_prompts, language="markdown")
    if st.session_state.t6_final_markdown or st.session_state.t6_seo_markdown:
        st.session_state.t6_final_markdown = st.text_area("最终 Markdown (发版用)：", value=st.session_state.t6_final_markdown or st.session_state.t6_seo_markdown, height=300)

    st.subheader("第 4 步：一键发布到 WordPress")
    c1, c2, c3 = st.columns(3)
    with c1: w_url = st.text_input("WP URL", value=get_config("WP_URL") or "")
    with c2: w_user = st.text_input("WP User", value=get_config("WP_USER") or "")
    with c3: w_pass = st.text_input("App Password", type="password", value=get_config("WP_APP_PASSWORD") or "")
    status = st.selectbox("状态", ["draft", "publish"])
    
    if st.button("🚀 立即推送", type="primary"):
        final_content = st.session_state.t6_final_markdown or st.session_state.t6_seo_markdown or md_input
        if not final_content: st.error("内容为空！")
        else:
            with st.spinner("推送中..."):
                try:
                    title = "AI Draft"
                    for line in final_content.split('\n'):
                        if line.startswith("# "):
                            title = line.replace("# ", "").strip()
                            final_content = final_content.replace(line, "", 1)
                            break
                    data = {"title": title, "content": final_content, "status": status}
                    r = requests.post(f"{w_url.rstrip('/')}/wp-json/wp/v2/posts", json=data, auth=HTTPBasicAuth(w_user, w_pass))
                    if r.status_code == 201: st.success(f"🎉 发布成功！[链接]({r.json().get('link')})")
                    else: st.error(f"失败 ({r.status_code}): {r.text}")
                except Exception as e: st.error(e)

# ==========================================
# 左侧主控导航菜单
# ==========================================
with st.sidebar:
    st.title("⚙️ AI Writer 工业化中心")
    st.caption("版本: 2026 最终聚合版")
    page = st.radio("系统功能导航", [
        "1. 创建角色背景", 
        "2. 文章话题生成器", 
        "3. 写文章原材料生成",
        "4. 文章生成器",
        "5. 文章配图 + 一键发布"
    ])
    st.markdown("---")
    st.success("✅ 模块化联通正常\n\n各工具数据已实现自动流转。")

# 路由分发
if page.startswith("1"): tool1_persona()
elif page.startswith("2"): tool2_topics()
elif page.startswith("4"): tool4_materials()
elif page.startswith("5"): tool5_article()
elif page.startswith("6"): tool6_publish()
