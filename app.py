import streamlit as st
import google.generativeai as genai
import os
import math
import time
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta

# ==========================================
# 0. 全局配置与模型初始化 (对接第三方中转 API)
# ==========================================
st.set_page_config(page_title="AI Writer 工业化中心 (终极完整版)", layout="wide")

def get_config(key): return st.secrets.get(key) or os.getenv(key)
api_key = get_config("GEMINI_API_KEY")

if api_key: 
    # ⚠️ 核心修改 1：指定中转域名，并强制使用 REST 协议
    genai.configure(
        api_key=api_key,
        transport="rest",
        client_options={"api_endpoint": "https://api.viviai.cc"}
    )
else: 
    st.error("❌ 未检测到 GEMINI_API_KEY。请配置。")
    st.stop()

# ⚠️ 核心修改 2：跳过模型搜索，直接锁定淘宝商家提供的模型
@st.cache_resource
def get_model(model_type="flash"):
    # 第三方中转站通常会屏蔽 SDK 自带的 list_models() 方法，导致原代码报错。
    # 这里直接硬编码强制调用商家提供的模型名：
    return genai.GenerativeModel('models/gemini-3-flash-preview')

model_flash = get_model("flash")
model_pro = get_model("pro")

safe_config = None


# ==========================================
# 1. 全局状态管理 (集中初始化所有工具的变量)
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
    if 't3_step' not in st.session_state: st.session_state.t3_step = 1
    if 't3_topics_raw' not in st.session_state: st.session_state.t3_topics_raw = ""
    if 't3_topics_list' not in st.session_state: st.session_state.t3_topics_list = []
    if 't3_ai_results' not in st.session_state: st.session_state.t3_ai_results = {}
    if 't3_personal_insights' not in st.session_state: st.session_state.t3_personal_insights = {}
    if 't3_batch_personal' not in st.session_state: st.session_state.t3_batch_personal = ""
    if 't3_final_materials' not in st.session_state: st.session_state.t3_final_materials = ""
    
    # --- Tool 4: 文章生成 ---
    if 't4_article_draft' not in st.session_state: st.session_state.t4_article_draft = ""
    if 't4_validation_res' not in st.session_state: st.session_state.t4_validation_res = ""
    
    # --- Tool 5: 配图与发布 ---
    if 't5_img_prompts' not in st.session_state: st.session_state.t5_img_prompts = ""
    if 't5_seo_markdown' not in st.session_state: st.session_state.t5_seo_markdown = ""
    if 't5_final_markdown' not in st.session_state: st.session_state.t5_final_markdown = ""

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
        
        current_answer = st.text_area("您的回答（支持随时修改）：", value=st.session_state.t1_answers[st.session_state.t1_step], height=150, key=f"t1_in_{st.session_state.t1_step}")
        
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("⬅️ 上一步", disabled=(st.session_state.t1_step == 0), key="t1_p"):
                st.session_state.t1_answers[st.session_state.t1_step] = current_answer
                st.session_state.t1_step -= 1
                st.rerun()
        with c2:
            if st.button("下一步 ➡️", type="primary", key="t1_n"):
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
        st.session_state.persona_cn = st.text_area("您可以直接在此修改最终的中文草稿：", value=draft_cn.strip(), height=400, key="t1_draft")
        
        if st.button("✨ 一键翻译并保存为英文角色指令", type="primary", key="t1_trans"):
            with st.spinner("AI 正在将您的业务背景转化为极其专业的英文 System Prompt..."):
                p = f"你是一位资深的 B2B 外贸营销专家。请将以下中文的客户业务背景，翻译并润色成一段极其地道、专业的英文，作为后续 AI 的 System Prompt。直接输出英文：\n\n{st.session_state.persona_cn}"
                try:
                    st.session_state.persona_en = model_flash.generate_content(p, safety_settings=safe_config).text
                    st.success("✅ 英文角色指令已生成并存入系统！")
                except Exception as e: st.error(f"翻译失败: {e}")
                    
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
        if st.button("下一步 ➡️", type="primary", key="t2_n1"):
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
            if st.button("⬅️ 上一步", key="t2_p2"):
                st.session_state.t2_step = 1
                st.rerun()
        with c2:
            if st.button("下一步 ➡️", type="primary", key="t2_n2"):
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
            if st.button("⬅️ 上一步", key="t2_p3"):
                st.session_state.t2_step = 2
                st.rerun()
        with c2:
            if st.button("下一步 ➡️", type="primary", key="t2_n3"):
                if not current_val.strip(): st.error("请至少填写一种公司类型")
                else:
                    st.session_state.t2_company_type = current_val
                    st.session_state.t2_step = 4
                    st.rerun()

    elif step == 4:
        st.markdown("### **{你的国家}**")
        current_val = st.text_input("你想宣传的公司是哪个国家的？", value=st.session_state.t2_my_country)
        target_count = st.slider("选择想生成的话题数量 (50~600)", 50, 600, st.session_state.t2_topic_count, 50)
        
        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t2_p4"):
                st.session_state.t2_step = 3
                st.rerun()
        with c2:
            if st.button("🚀 生成话题列表", type="primary", key="t2_gen"):
                st.session_state.t2_my_country = current_val
                st.session_state.t2_topic_count = target_count
                
                c_list = [c.strip() for c in st.session_state.t2_countries.split('\n') if c.strip()]
                t_list = [t.strip() for t in st.session_state.t2_company_type.split('\n') if t.strip()]
                total_combo = len(c_list) * len(t_list)
                per_combo = math.ceil(target_count / total_combo)
                st.session_state.t2_results = []
                
                with st.container():
                    st.info(f"检测到 {len(c_list)} 个国家 × {len(t_list)} 个身份 = {total_combo} 个组合。自动去重中...")
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
        with c1: st.download_button("📥 导出 CSV", "Topic\n"+final_text, "topics.csv", "text/csv")
        with c2:
            if st.button("🔄 重置此工具"):
                st.session_state.t2_step = 1
                st.session_state.t2_results = []
                st.rerun()

# ==========================================
# 工具 3：写文章原材料生成 (严格执行自定义 Prompt)
# ==========================================
def tool3_materials():
    st.title("🗄️ 工具 3：写文章原材料生成")
    st.caption("把话题转化为完整的写作原材料，包含 AI 深度调研结果（Perplexity + Google SERP）和你的个人见解。")
    st.divider()

    step = st.session_state.t3_step
    st.subheader(f"第 {step} / 4 步")

    if step == 1:
        st.markdown("### 第 1 步：批量粘贴话题")
        default_val = "\n".join(st.session_state.t2_results[:2]) if st.session_state.t2_results else ""
        current_val = st.text_area("请从 Excel / 工具 2 中复制话题列表粘贴到下方：", value=st.session_state.t3_topics_raw or default_val, height=150)
        
        if st.button("下一步 ➡️ (开始 AI 调研)", type="primary", key="t3_n1"):
            if not current_val.strip(): st.error("请至少输入一个话题！")
            else:
                st.session_state.t3_topics_raw = current_val
                st.session_state.t3_topics_list = [t.strip() for t in current_val.split('\n') if t.strip()]
                st.session_state.t3_step = 2
                st.rerun()

    elif step == 2:
        st.markdown("### 第 2 步：AI 见解调研")
        topics = st.session_state.t3_topics_list
        total = len(topics)
        
        if len(st.session_state.t3_ai_results) < total:
            pb = st.progress(0)
            st_txt = st.empty()
            for idx, topic in enumerate(topics):
                if topic in st.session_state.t3_ai_results: continue
                st_txt.text(f"正在执行深度调研任务 ({idx+1}/{total}): {topic}")
                
                # ---------------------------------------------------------
                # 💡 核心注入：100% 严格执行你提供的 Prompt 逻辑
                # ---------------------------------------------------------
                prompt = f"""
我会给你一个问题，请你帮我生成 10 条英文见解。 
问题（话题）：{topic}

要求： 
1. 你要基于 Google SERP 排名前 10 的自然搜索页面，提炼出 6 条明确提到的关键见解。 
2. 再补充 4 条不在前 10 页中出现，但基于其他可靠信息或逻辑推理得出的见解。 
3. 总共输出 10 条见解。 
4. 只输出见解内容，不要提到数据来源、研究过程，也不要写解释性文字。 
5. 输出必须是英文，每条见解简洁、事实化。

---
【系统排版要求】：为了衔接下一个写作工具，请在输出上述 10 条见解的同时，顺便提供 4 个相关的英文二级标题 (H2)。并严格按照以下固定格式输出（必须保留前面的星号标签）：

*二级标题：
* [H2 1]
* [H2 2]
* [H2 3]
* [H2 4]
*AI见解：
1. [见解 1]
2. [见解 2]
...
10. [见解 10]
                """
                try:
                    if idx > 0: time.sleep(1.5)
                    st.session_state.t3_ai_results[topic] = model_pro.generate_content(prompt, safety_settings=safe_config).text
                except Exception as e:
                    st.session_state.t3_ai_results[topic] = "调研失败，请检查网络或 API 额度。"
                pb.progress((idx + 1) / total)
            st_txt.success(f"✅ 调研完成 ({total}/{total})")
        else:
            st.success(f"✅ 调研完成 ({total}/{total})")

        with st.expander("👁️ 查看 AI 调研结果"):
            for t in topics: st.markdown(f"**{t}**\n{st.session_state.t3_ai_results.get(t, '')}")

        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t3_p2"):
                st.session_state.t3_step = 1
                st.rerun()
        with c2:
            if st.button("下一步 ➡️ (录入个人见解)", type="primary", key="t3_n2"):
                st.session_state.t3_step = 3
                st.rerun()

    elif step == 3:
        st.markdown("### 第 3 步：录入个人见解（选填）")
        topics = st.session_state.t3_topics_list
        mode = st.radio("录入方式：", ["逐一输入", "批量粘贴"])
        
        if mode == "逐一输入":
            for idx, topic in enumerate(topics):
                if topic not in st.session_state.t3_personal_insights: st.session_state.t3_personal_insights[topic] = ""
                st.session_state.t3_personal_insights[topic] = st.text_input(f"{idx+1}. {topic}", value=st.session_state.t3_personal_insights[topic], key=f"t3_in_{idx}")
        else:
            b_input = st.text_area("批量粘贴 (每行对应一个话题)：", value=st.session_state.t3_batch_personal, height=150)
            st.session_state.t3_batch_personal = b_input
            b_lines = [l.strip() for l in b_input.split('\n')]
            for idx, topic in enumerate(topics):
                st.session_state.t3_personal_insights[topic] = b_lines[idx] if idx < len(b_lines) else ""

        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t3_p3"):
                st.session_state.t3_step = 2
                st.rerun()
        with c2:
            if st.button("下一步 ➡️ (生成结果)", type="primary", key="t3_n3"):
                st.session_state.t3_step = 4
                st.rerun()

    elif step == 4:
        st.markdown("### 第 4 步：生成结果")
        out = ""
        for t in st.session_state.t3_topics_list:
            ai_r = st.session_state.t3_ai_results.get(t, "")
            p_r = st.session_state.t3_personal_insights.get(t, "")
            out += f"*主标题：{t}\n{ai_r}\n*人工见解：{p_r}\n\n--------------------------------------------------\n\n"
        
        st.session_state.t3_final_materials = out
        st.text_area("最终原材料提取结果 (直接复制供工具4使用)：", value=out.strip(), height=400)
        
        c1, c2 = st.columns([1, 6])
        with c1:
            if st.button("⬅️ 上一步", key="t3_p4"):
                st.session_state.t3_step = 3
                st.rerun()
        with c2:
            if st.button("🔄 重置此工具", key="t3_reset"):
                st.session_state.t3_step = 1
                st.session_state.t3_topics_raw = ""
                st.session_state.t3_ai_results = {}
                st.session_state.t3_personal_insights = {}
                st.rerun()

# ==========================================
# 工具 4：文章生成器 (严格执行 1500 字 PAS 顶级提示词)
# ==========================================
def tool4_article():
    st.title("✍️ 工具 4：文章生成器")
    st.caption("输入角色背景和写作原材料，AI 会为你生成一篇完整的 Markdown 格式文章。")
    st.divider()

    st.subheader("第 1 步：确认角色背景")
    persona_input = st.text_area("角色背景 (默认读取工具1，将自动注入 Prompt 的 My Role 中)：", value=st.session_state.persona_en, height=150)

    st.subheader("第 2 步：输入写作原材料")
    mat_input = st.text_area("粘贴从工具3生成的写作原材料 (取单篇即可)：", value=st.session_state.t3_final_materials.split('---')[0].strip() if st.session_state.t3_final_materials else "", height=200)

    if st.button("📝 生成文章 (流式输出，约需 1-3 分钟)", type="primary", key="t4_gen"):
        if not mat_input.strip() or not persona_input.strip(): 
            st.error("背景和原材料不能为空！")
        else:
            st.session_state.t4_article_draft = ""
            with st.spinner("AI 正在严格执行顶级 SEO SOP 撰写长文，请耐心等待..."):
                
                # ---------------------------------------------------------
                # 💡 核心注入：100% 像素级还原你的顶级 PAS 文章生成 Prompt
                # ---------------------------------------------------------
                prompt = f"""
# Your Role:
你是一个我写博客文章的枪手，你会使用我的口吻，用Markdown语言输出指定格式的博客文章。

# Your Responsibilities:
当我输入如下格式的内容给你时:
{mat_input}

你按照如下的格式输出一篇文章给我：

# 这里是文章的主标题，以问号结尾

[图片占位符]

Leading paragraph:
开头第一段，会使用PAS策略，吸引读者注意力，在这一段里使用第一人称的语气。(Max 30 words)

Featured paragraph:
**开头第二段，回答标题提出的问题，这个段落，后面会用来竞争谷歌的精选摘要。** (Min 30 words and Max 50 words)

Transition paragraph:
承上启下的段落，会挽留客户继续往下阅读。

LOOP START

## 我输入给你的二级标题，也是以问号结尾

Leading paragraph:
开头第一段，会使用PAS策略，吸引读者注意力，在这一段里使用第一人称的语气。(Max 30 words)

Featured paragraph:
**开头第二段，回答标题提出的问题，这个段落，后面会用来竞争谷歌的精选摘要。** (Min 30 words and Max 50 words)

[图片占位符]

Dive deeper paragraph:
根据二级标题，继续延展和深入，可以用批判性思维，来拆分问题，帮助读者更加深入地理解。(Min 200 words)

LOOP END

## Conclusion

写一段结论，总结全文。(Max 30 words)

## My Role:
{persona_input}

# My Requirements:
1. 文章的长度，不得少于1500个单词，文章的每个Dive deeper paragraph，都不得少于200个单词；
2. 全文除了所有的Featured paragraphs必须使用第一人称的口吻进行写作，在必要时补充个人故事（我会稍后替换）；
3. 在二级标题之下的段落中，当进行Dive deeper paragraph写作时，多穿插一些必要的Markdown格式的H3s和表格；
4. 写作风格介于书面学术写作和口语描述之间，所有句子都有主语，使用Plain English和简单词汇，让高中学生也能读懂，不要用复杂的长难句，不要用复杂、高级、生僻的词汇，尽可能用短句输出，替换掉非日常的词汇；
5. 将所有句子中过渡词和连接词替换成最基础，最常用的词语，尽可能试试简单的、直接的表达方式，避免使用复杂或生僻的词汇。保证句子的逻辑关系清晰，不要主动添加任何总结（除非文章最后的Conslusion部分）；
6. 你输出给我的内容不能包含任何Leading paragraph:、Featured paragraph:、Transition paragraph:、Dive deeper paragraph:、LOOP START、LOOP END这些或类似于这些的解释性文本；
7. 图片占位符用以下链接表示：![alt with keywords]("https://placehold.co/600x400.jpg")
8. 文章默认使用英语输出；
9. 你输出给我的文章，必须转换成Markdown格式；
10. 你输出给我的内容，必须包含3个表格。
11. 在每个二级标题下的Featured paragraph下边的位置生成图片占位符。
12. 在每个二级标题下的图片占位符之下的位置都要生成Dive deeper paragraph。
"""
                try:
                    # ⚠️ 关闭流式输出 (stream=False)，完美适配第三方中转站
                    res = model_pro.generate_content(prompt, stream=False, safety_settings=safe_config)
                    st.session_state.t4_article_draft = res.text
                    st.success("✅ 文章生成完毕！")
                except Exception as e: 
                    st.error(f"生成中断: {e}")

    if st.session_state.t4_article_draft:
        st.subheader("第 3 步：编辑与使用")
        c1, c2, c3 = st.columns([1.5, 2, 2])
        with c1:
            if st.button("✅ 一键校验格式", key="t4_val"):
                d = st.session_state.t4_article_draft
                words = len(d.split())
                h2_count = d.count("## ") - d.count("### ") - (1 if "## Conclusion" in d else 0)
                img_count = d.count("![")
                table_count = d.count("|---|")
                st.session_state.t4_validation_res = f"字数: {words} 词 | H2数量: {h2_count} | 图片: {img_count} | 表格: {table_count}"
        with c2: 
            lang = st.selectbox("翻译:", ["简体中文", "Español", "Deutsch"], label_visibility="collapsed")
        with c3:
            if st.button("🌐 翻译此文", key="t4_trans"):
                try:
                    trans_prompt = f"Translate the following Markdown article into {lang}. Keep all the Markdown formatting (like #, ##, tables, and image links) intact:\n\n{st.session_state.t4_article_draft}"
                    res = model_flash.generate_content(trans_prompt, safety_settings=safe_config)
                    st.session_state.t4_article_draft = res.text
                    st.success(f"已翻译为 {lang}")
                except Exception as e: 
                    st.error(e)

        if st.session_state.t4_validation_res: 
            st.info(st.session_state.t4_validation_res)
        
        st.session_state.t4_article_draft = st.text_area("Markdown 编辑器：", value=st.session_state.t4_article_draft, height=600, key="t4_editor")
        
        with st.expander("👁️ 预览网页渲染效果"):
            st.markdown(st.session_state.t4_article_draft, unsafe_allow_html=True)

import json
import time
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import streamlit as st

# ==========================================
# 工具 5：文章配图 + 一键发布 (Recraft全自动版 + 100%原生顶级提示词)
# ==========================================
def tool5_publish():
    st.title("🚀 工具 5：文章配图 + 一键发布 (全自动真图上传版)")
    st.markdown("通过接入 Recraft API，实现自动画图、自动上传 WP 媒体库、自动替换占位符并注入 SEO。")
    st.divider()

    st.subheader("第 1 步：配置所有 API 与凭证")
    st.info("WP 媒体库上传必须验证账号密码。如果你之前配置过，这里会自动读取。")
    c1, c2, c3, c4 = st.columns(4)
    with c1: w_url = st.text_input("WP URL (含 https)", value=get_config("WP_URL") or "")
    with c2: w_user = st.text_input("WP User", value=get_config("WP_USER") or "")
    with c3: w_pass = st.text_input("WP App Password", type="password", value=get_config("WP_APP_PASSWORD") or "")
    with c4: recraft_key = st.text_input("Recraft API Key", type="password", value=get_config("RECRAFT_API_KEY") or "")

    st.subheader("第 2 步：确认文章与背景")
    persona_input = st.text_area("角色背景 (用于配图基调)：", value=st.session_state.get('persona_en', ''), height=100)
    md_input = st.text_area("粘贴 Markdown 文章全文 (包含占位符)：", value=st.session_state.get('t4_article_draft', ''), height=200)

    st.subheader("第 3 步：全自动化处理 (AI配图 → WP上传 → SEO替换 → 脚注)")
    
    if st.button("🌟 一键执行：全自动配图与深度优化", type="primary", use_container_width=True):
        if not all([w_url, w_user, w_pass, recraft_key, md_input]):
            st.error("⚠️ 请填写完整的 WP凭证、Recraft Key 和文章内容！")
            return

        # ---------------------------------------------------------
        # 1. 提取 5 个纯英文 Prompt (严格原生提示词)
        # ---------------------------------------------------------
        with st.spinner("1/4 正在让大模型提取 5 个专业配图 Prompt..."):
            p = f"""
Your Role:

You are an SEO expert specializing in image SEO optimization to enhance search engine visibility for my website.

Your Responsibilities:

Each time I upload one or multiple images, you must generate SEO-optimized metadata for each image in the following Markdown format:

![Alternative text, concise image description (≤15 words)](#placeholder_link "Title text (≤5 words)")

Key Formatting Rules:
1. Alternative Text (Alt Text):
• Describe the image concisely in 15 words or fewer.
• Make it descriptive and meaningful for both SEO and accessibility.
2. Title Text:
• Keep it 5 words or fewer.
• It should be a short, catchy phrase that enhances the image’s SEO relevance.
3. Direct Integration (CRITICAL):
• Each image’s metadata must be presented on a separate line.
• Do NOT wrap the image tag in a code block (```markdown). Embed it directly into the article text so the image renders natively in WordPress.

My Requirements (Output Guidelines)
1. All outputs must be in English.
2. DO NOT wrap the output or the images inside a code block. 
3. Each image must have a separate SEO-optimized Alt Text and Title Text following the specified format.
4. Ensure descriptions are relevant to my industry and improve SEO rankings for my website.

[SYSTEM CRITICAL INSTRUCTION]: You MUST replace all `[Image X]` placeholders or existing image tags in the article with the REAL WordPress URLs provided below. OUTPUT THE FULL UPDATED MARKDOWN ARTICLE. Do not output code blocks around the article text or around the images.

REAL WordPress URLs to use sequentially:
1. {wp_urls[0] if len(wp_urls) > 0 else 'https://placehold.co/600'}
2. {wp_urls[1] if len(wp_urls) > 1 else 'https://placehold.co/600'}
3. {wp_urls[2] if len(wp_urls) > 2 else 'https://placehold.co/600'}
4. {wp_urls[3] if len(wp_urls) > 3 else 'https://placehold.co/600'}
5. {wp_urls[4] if len(wp_urls) > 4 else 'https://placehold.co/600'}

Article Content:
{md_input}
            """
            try:
                res = model_flash.generate_content(p, safety_settings=None).text
                json_str = res.replace('```json', '').replace('```', '').strip()
                prompts = json.loads(json_str)
            except Exception as e:
                st.error(f"解析 Prompt 失败，大模型没有返回标准 JSON: {e}")
                return
            st.session_state.t5_img_prompts = "\n\n".join(prompts)

        # ---------------------------------------------------------
        # 2. 调用 Recraft 并上传 WordPress (带尺寸修复和网址修复)
        # ---------------------------------------------------------
        wp_urls = []
        progress_bar = st.progress(0)
        status_txt = st.empty()

        for i, img_prompt in enumerate(prompts):
            status_txt.text(f"2/4 正在调用 Recraft 出图并上传网站图库... ({i+1}/5)")
            try:
                r_url_raw = "https://external.api.recraft.ai/v1/images/generations"
                r_url = r_url_raw.encode('ascii', 'ignore').decode('ascii')
                r_head = {"Authorization": f"Bearer {recraft_key}", "Content-Type": "application/json"}
                r_data = {"prompt": img_prompt, "style": "realistic_image", "size": "1365x1024"} 
                r_resp = requests.post(r_url, json=r_data, headers=r_head)
                if r_resp.status_code != 200: raise Exception(f"Recraft 报错: {r_resp.text}")
                img_url = r_resp.json()['data'][0]['url']

                img_bytes = requests.get(img_url).content

                wp_media_url = f"{w_url.rstrip('/')}/wp-json/wp/v2/media"
                wp_head = {
                    "Content-Disposition": f"attachment; filename=seo-img-{i+1}-{int(time.time())}.jpg", 
                    "Content-Type": "image/jpeg"
                }
                w_resp = requests.post(wp_media_url, headers=wp_head, data=img_bytes, auth=HTTPBasicAuth(w_user, w_pass))
                if w_resp.status_code == 201:
                    wp_urls.append(w_resp.json().get('source_url'))
                else:
                    raise Exception(f"WP 媒体库上传失败: {w_resp.text}")
            except Exception as e:
                st.error(f"处理第 {i+1} 张图时出错: {e}")
                wp_urls.append("https://placehold.co/800x400.png?text=Image+Upload+Error") 
            progress_bar.progress((i + 1) / 5)
        
        status_txt.success("✅ 5 张真实图片已成功生成并上传到 WordPress 媒体库！")

        # ---------------------------------------------------------
        # 3. 真实链接注入与 SEO 优化 (严格原生提示词)
        # ---------------------------------------------------------
        with st.spinner("3/4 正在将网站真实图片链接注入文章，并生成 SEO Alt 标签..."):
            seo_p = f"""
            
Your Role:

You are an SEO expert specializing in image SEO optimization to enhance search engine visibility for my website.

Your Responsibilities:

Each time I upload one or multiple images, you must generate SEO-optimized metadata for each image in the following Markdown format:

![Alternative text, concise image description (≤15 words)](#placeholder_link "Title text (≤5 words)")

Key Formatting Rules:
1. Alternative Text (Alt Text):
• Describe the image concisely in 15 words or fewer.
• Make it descriptive and meaningful for both SEO and accessibility.
2. Title Text:
• Keep it 5 words or fewer.
• It should be a short, catchy phrase that enhances the image’s SEO relevance.
3. Markdown Code Block:
• The output must always be formatted as a code block (```markdown) for easy copy-pasting.
• Each image’s metadata must be presented on a separate line.

My Requirements (Output Guidelines)
1. All outputs must be in English.
2. All outputs must be in Markdown format and wrapped inside a code block.
3. Each image must have a separate SEO-optimized Alt Text and Title Text following the specified format.
4. Ensure descriptions are relevant to my industry and improve SEO rankings for my website.

[SYSTEM CRITICAL INSTRUCTION]: You MUST replace all `[Image X]` placeholders or existing image tags in the article with the REAL WordPress URLs provided below, formatted with the exact SEO Markdown structure requested above. OUTPUT THE FULL UPDATED MARKDOWN ARTICLE. Do not output code blocks around the entire article text, just the updated text itself.

REAL WordPress URLs to use sequentially:
1. {wp_urls[0] if len(wp_urls) > 0 else 'https://placehold.co/600'}
2. {wp_urls[1] if len(wp_urls) > 1 else 'https://placehold.co/600'}
3. {wp_urls[2] if len(wp_urls) > 2 else 'https://placehold.co/600'}
4. {wp_urls[3] if len(wp_urls) > 3 else 'https://placehold.co/600'}
5. {wp_urls[4] if len(wp_urls) > 4 else 'https://placehold.co/600'}

Article Content:
{md_input}
            """
            st.session_state.t5_seo_markdown = model_flash.generate_content(seo_p, safety_settings=None).text

        # ---------------------------------------------------------
        # 4. 构建双向脚注系统 (满血原生提示词 + 完整Example)
        # ---------------------------------------------------------
        with st.spinner("4/4 最后一步：构建高级双向脚注系统..."):
            fn_p = f"""
## Your Role

You are an SEO expert responsible for enhancing articles by inserting relevant external links while maintaining readability, proper formatting, and structured footnotes in Markdown format.

## Your Responsibilities

### Input

You will receive an article in Markdown format.

### Output Guidelines

1. **Identify Key Phrases for Hyperlinking**

   * Select meaningful noun phrases that require additional explanation or supporting data.
   * Do not hyperlink single words; instead, choose context-rich phrases that fit naturally within the content.
   * Exclude bolded paragraphs from hyperlinking.

2. **Insert Hyperlinks Correctly**

   * Embed links directly within the content using Markdown format (e.g., `[ISO 9001](https://www.example.com)`).
   * Avoid adding separate footnotes within bolded paragraphs.
   * Display the footnote number as an **upward superscript digit** using `<sup>` (e.g., `[ISO 9001](https://www.example.com) <sup>[1](#footnote-1){{#ref-1}}</sup>`).

3. **Ensure Proper Footnote Usage**

   * Do **not** use Markdown Extra’s `[^1]` syntax. Instead, implement a **manual bidirectional system**:

     * In the main text: `<sup>[1](#footnote-1){{#ref-1}}</sup>`
     * In the footnotes: `<span id="footnote-1">1. Short explanation. [↩︎](#ref-1)</span>`
   * At the bottom of the article, create a **“Footnotes”** section listing all referenced links.
   * Each footnote should include a concise explanation (max 20 words) of why users should visit the link.
   * After each footnote entry, add a **return link `[↩︎]`** that navigates back to the corresponding keyword in the main text.
   * Each footnote number must be unique and non-repetitive to ensure accurate linking.

4. **Maintain Consistency and Readability**

   * Each article must contain **exactly ten external links** — no more, no less.
   * No duplicate key phrases should be hyperlinked.
   * The selected phrases should be seamlessly integrated within the article to maintain smooth readability.

5. **Ensure Markdown Formatting for Output**

   * The final output must be in **Markdown format** after inserting hyperlinks and footnotes.
   * You may use minimal HTML tags (`<sup>`, `<span>`) to enable superscripts and anchor navigation.
   * Avoid unnecessary HTML to ensure compatibility across Markdown-based platforms.

---

## Example Formatting

✅ Correct:

```markdown
Certifications such as [ISO 9001](https://www.example.com) <sup>[1](#footnote-1){{#ref-1}}</sup> demonstrate a supplier’s commitment to quality management.
```

❌ Incorrect:

```markdown
Certifications such as [ISO 9001](https://www.example.com) [^1] demonstrate a supplier’s commitment to quality management.
```

---

## Footnotes Formatting

At the end of the article, include a **Footnotes** section listing all 10 inserted links along with a short explanation and return link.

✅ Markdown Example:

```markdown
---
## Footnotes  

<span id="footnote-1">1. Learn how ISO 9001 ensures consistent quality standards. [↩︎](#ref-1)</span>  
<span id="footnote-2">2. Guide to analyzing customer reviews for supplier reliability. [↩︎](#ref-2)</span>  
<span id="footnote-3">3. Role of third-party verification in supplier compliance. [↩︎](#ref-3)</span>  
<span id="footnote-4">4. Insights into cost-effective logistics for supply chains. [↩︎](#ref-4)</span>  
<span id="footnote-5">5. How trade policies affect procurement strategies. [↩︎](#ref-5)</span>  
<span id="footnote-6">6. Explanation of sustainable sourcing practices. [↩︎](#ref-6)</span>  
<span id="footnote-7">7. Impact of digital tools on supplier evaluation. [↩︎](#ref-7)</span>  
<span id="footnote-8">8. Why supplier diversity strengthens global supply chains. [↩︎](#ref-8)</span>  
<span id="footnote-9">9. Benefits of certifications for international trade compliance. [↩︎](#ref-9)</span>  
<span id="footnote-10">10. Key trends in supplier risk management. [↩︎](#ref-10)</span>  
```

[SYSTEM INSTRUCTION: OUTPUT THE FULL UPDATED MARKDOWN ARTICLE. Do not output code blocks around the article text, just the text itself.]

Article to process:
{st.session_state.t5_seo_markdown}
            """
            st.session_state.t5_final_markdown = model_flash.generate_content(fn_p, safety_settings=None).text
        
        st.success("🎉 全套自动化处理完毕！您现在拥有了一篇带真实图片、完美 SEO 和脚注的终极 Markdown 文章。")

    # ---------------------------------------------------------
    # 第 4 步：展示结果并发布
    # ---------------------------------------------------------
    if st.session_state.get('t5_final_markdown') or st.session_state.get('t5_seo_markdown'):
        st.subheader("第 4 步：检查并推送到网站")
        with st.expander("👁️ 查看生成的 Recraft Prompt 历史"):
            st.code(st.session_state.get('t5_img_prompts', ''), language="json")
            
        st.session_state.t5_final_markdown = st.text_area("最终 Markdown (所有图片已替换为您的网站图库链接)：", value=st.session_state.get('t5_final_markdown') or st.session_state.get('t5_seo_markdown'), height=400)
        
        status = st.selectbox("发布状态", ["draft", "publish"])
        if st.button("🚀 立即推送文章到 WordPress", type="primary"):
            with st.spinner("文章发布中..."):
                try:
                    title = "AI Draft"
                    # 1. 拿到最终的文章文本
                    raw_content = st.session_state.t5_final_markdown.strip()
                    
                    # 2. 暴力清洗外壳：如果大模型在开头加了 ```markdown 或 ```，直接砍掉！
                    if raw_content.startswith('```markdown'):
                        raw_content = raw_content[11:].strip()
                    elif raw_content.startswith('```md'):
                        raw_content = raw_content[5:].strip()
                    elif raw_content.startswith('```'):
                        raw_content = raw_content[3:].strip()
                        
                    # 3. 暴力清洗尾部：如果结尾带了 ```，也直接砍掉！
                    if raw_content.endswith('```'):
                        raw_content = raw_content[:-3].strip()

                    final_content = raw_content
                    
                    # 提取标题的循环保持不变
                    for line in final_content.split('\n'):
                        if line.startswith("# "):
                            title = line.replace("# ", "").strip()
                            final_content = final_content.replace(line, "", 1)
                            break
                    data = {"title": title, "content": final_content, "status": status}
                    r = requests.post(f"{w_url.rstrip('/')}/wp-json/wp/v2/posts", json=data, auth=HTTPBasicAuth(w_user, w_pass))
                    if r.status_code == 201: 
                        st.balloons()
                        st.success(f"🎉 发布成功！点击查看：[立即预览]({r.json().get('link')})")
                    else: st.error(f"发布失败 ({r.status_code}): {r.text}")
                except Exception as e: st.error(f"网络报错: {e}")

# ==========================================
# 工具 7：全自动批量发布工具 (100% 严格原生提示词 + 真图上传版)
# ==========================================
def tool7_batch_publish():
    st.title("🤖 工具 7：全自动批量发布与排期 (满血顶配版)")
    st.markdown("**🔥 终极效率工具**：全自动执行调研、长文、Recraft真图生成、WP图库上传、图片 SEO 与双向脚注系统。")
    st.divider()

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("1. 基础素材配置")
        persona_input = st.text_area("角色背景 (必填)：", value=st.session_state.get('persona_en', ''), height=150)
        default_topics = "\n".join(st.session_state.get('t2_results', [])) if st.session_state.get('t2_results') else ""
        topics_input = st.text_area("粘贴批量话题 (每行一个)：", value=default_topics, height=200)

    with col2:
        st.subheader("2. API 与 WordPress 配置")
        w_url = st.text_input("WP URL (含 https://)", value=get_config("WP_URL") or "", key="w_url_7")
        w_user = st.text_input("WP 用户名", value=get_config("WP_USER") or "", key="w_user_7")
        w_pass = st.text_input("WP 应用密码", type="password", value=get_config("WP_APP_PASSWORD") or "", key="w_pass_7")
        recraft_key = st.text_input("Recraft API Key", type="password", value=get_config("RECRAFT_API_KEY") or "", key="rc_key_7")
        
        st.markdown("---")
        start_date = st.date_input("排期开始日期", value=datetime.today())
        posts_per_day = st.number_input("每天发布几篇文章？", min_value=1, max_value=10, value=2)

    st.markdown("---")
    
    if st.button("🚀 确认无误，开始全自动批量执行", type="primary", use_container_width=True):
        topics = [t.strip() for t in topics_input.split('\n') if t.strip()]
        if not topics or not persona_input or not all([w_url, w_user, w_pass, recraft_key]):
            st.error("⚠️ 请确保填完了话题、背景、WordPress 凭证 以及 Recraft Key！")
            return
            
        st.success(f"初始化成功！共检测到 {len(topics)} 个任务。即将开始包含【自动画图与上传】的无人值守作业...")
        
        progress_bar = st.progress(0)
        status_box = st.empty()
        log_box = st.empty()
        logs = []
        
        interval_hours = 24 / posts_per_day
        current_schedule_time = datetime.combine(start_date, datetime.min.time()) + timedelta(hours=8)
        
        for idx, topic in enumerate(topics):
            status_box.info(f"🔄 **正在处理第 {idx+1}/{len(topics)} 篇**: {topic}")
            try:
                # 步骤 A: 调研
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 开始深度调研...")
                log_box.code("\n".join(logs[-5:]))
                
                research_p = f"""
我会给你一个问题，请你帮我生成 10 条英文见解。 
问题（话题）：{topic}

要求： 
1. 你要基于 Google SERP 排名前 10 的自然搜索页面，提炼出 6 条明确提到的关键见解。 
2. 再补充 4 条不在前 10 页中出现，但基于其他可靠信息或逻辑推理得出的见解。 
3. 总共输出 10 条见解。 
4. 只输出见解内容，不要提到数据来源、研究过程，也不要写解释性文字。 
5. 输出必须是英文，每条见解简洁、事实化。

---
【系统排版要求】：为了衔接下一个写作工具，请在输出上述 10 条见解的同时，顺便提供 4 个相关的英文二级标题 (H2)。并严格按照以下固定格式输出（必须保留前面的星号标签）：

*二级标题：
* [H2 1]
* [H2 2]
* [H2 3]
* [H2 4]
*AI见解：
1. [见解 1]
2. [见解 2]
3. [见解 3]
4. [见解 4]
5. [见解 5]
6. [见解 6]
7. [见解 7]
8. [见解 8]
9. [见解 9]
10. [见解 10]
                """
                ai_insights = model_flash.generate_content(research_p, safety_settings=None).text
                time.sleep(3)
                
                # 步骤 B: PAS 1500 字长文
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✍️ 撰写 1500 字长文...")
                log_box.code("\n".join(logs[-5:]))
                
                write_p = f"""
# Your Role:
你是一个我写博客文章的枪手，你会使用我的口吻，用Markdown语言输出指定格式的博客文章。

# Your Responsibilities:
当我输入如下格式的内容给你时:
{ai_insights}

你按照如下的格式输出一篇文章给我：

# 这里是文章的主标题，以问号结尾

[图片占位符]

Leading paragraph:
开头第一段，会使用PAS策略，吸引读者注意力，在这一段里使用第一人称的语气。(Max 30 words)

Featured paragraph:
**开头第二段，回答标题提出的问题，这个段落，后面会用来竞争谷歌的精选摘要。** (Min 30 words and Max 50 words)

Transition paragraph:
承上启下的段落，会挽留客户继续往下阅读。

LOOP START

## 我输入给你的二级标题，也是以问号结尾

Leading paragraph:
开头第一段，会使用PAS策略，吸引读者注意力，在这一段里使用第一人称的语气。(Max 30 words)

Featured paragraph:
**开头第二段，回答标题提出的问题，这个段落，后面会用来竞争谷歌的精选摘要。** (Min 30 words and Max 50 words)

[图片占位符]

Dive deeper paragraph:
根据二级标题，继续延展和深入，可以用批判性思维，来拆分问题，帮助读者更加深入地理解。(Min 200 words)

LOOP END

## Conclusion

写一段结论，总结全文。(Max 30 words)

## My Role:
{persona_input}

# My Requirements:
1. 文章的长度，不得少于1500个单词，文章的每个Dive deeper paragraph，都不得少于200个单词；
2. 全文除了所有的Featured paragraphs必须使用第一人称的口吻进行写作，在必要时补充个人故事（我会稍后替换）；
3. 在二级标题之下的段落中，当进行Dive deeper paragraph写作时，多穿插一些必要的Markdown格式的H3s和表格；
4. 写作风格介于书面学术写作和口语描述之间，所有句子都有主语，使用Plain English和简单词汇，让高中学生也能读懂，不要用复杂的长难句，不要用复杂、高级、生僻的词汇，尽可能用短句输出，替换掉非日常的词汇；
5. 将所有句子中过渡词和连接词替换成最基础，最常用的词语，尽可能试试简单的、直接的表达方式，避免使用复杂或生僻的词汇。保证句子的逻辑关系清晰，不要主动添加任何总结（除非文章最后的Conslusion部分）；
6. 你输出给我的内容不能包含任何Leading paragraph:、Featured paragraph:、Transition paragraph:、Dive deeper paragraph:
、LOOP START、LOOP END这些或类似于这些的解释性文本；
7. 图片占位符用以下链接表示：![alt with keywords]("https://placehold.co/600x400.jpg")
8. 文章默认使用英语输出；
9. 你输出给我的文章，必须转换成Markdown格式；
10. 你输出给我的内容，必须包含3个表格。
11. 在每个二级标题下的Featured paragraph下边的位置生成图片占位符。
12. 在每个二级标题下的图片占位符之下的位置都要生成Dive deeper paragraph。
                """
                article_md = model_flash.generate_content(write_p, safety_settings=None).text
                time.sleep(4)
                
                # 步骤 C1: 提取 Recraft 提示词并画图上传
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎨 提取 Recraft 提示词并开始云端作图...")
                log_box.code("\n".join(logs[-5:]))
                
                img_prompt_req = f"""
Your Role:

You will generate Recraft.ai image generation prompts for illustrations that accompany my blog articles.

Your Responsibilities:

When I provide you with the content of a blog article, you must generate five image generation prompts that accurately match the meaning or scenario described in the input.

Each prompt must follow these guidelines:
1. Start each prompt with a concise Chinese title that summarizes the scene depicted. Ensure the title is clearly separated from the prompt text and does not mix with it.
2. Each prompt must be at least 70 words long and written in clear, specific English. Avoid vague descriptions.
3. Each prompt should provide a detailed description of the image, including:
• Objects, people, and scene elements
• Colors, lighting, and atmosphere
• Perspective (e.g., close-up shot, wide-angle, aerial view, etc.)
• Possible artistic style (e.g., photography, 3D render, digital illustration, etc.)

## My Role:
{persona_input}

My Requirements (Output Guidelines)
1. All prompts must be written in English.
2. Each prompt must be at least 70 words long.
3. Each prompt must begin with a Chinese title summarizing the scene, ensuring it is distinct from the prompt itself.
4. The prompts must be precise and vivid, aligned with my industry background. Avoid vague descriptions.

[SYSTEM CRITICAL INSTRUCTION]: You MUST output the final result strictly as a valid JSON array containing exactly 5 strings. Do not include any markdown formatting like ```json.
Example: ["Title 1 prompt...", "Title 2 prompt...", "Title 3 prompt...", "Title 4 prompt...", "Title 5 prompt..."]

Article Content:
{article_md}
                """
                res = model_flash.generate_content(img_prompt_req, safety_settings=None).text
                
                json_str = res.replace('```json', '').replace('```', '').strip()
                try:
                    img_prompts_list = json.loads(json_str)
                except Exception:
                    img_prompts_list = [f"Illustration for {topic} part {i+1}, highly detailed, industrial setting" for i in range(5)]

                wp_urls = []
                for i, p_text in enumerate(img_prompts_list[:5]): 
                    try:
                        r_url_raw = "https://external.api.recraft.ai/v1/images/generations"
                        r_url = r_url_raw.encode('ascii', 'ignore').decode('ascii')
                        r_head = {"Authorization": f"Bearer {recraft_key}", "Content-Type": "application/json"}
                        r_data = {"prompt": p_text, "style": "realistic_image", "size": "1365x1024"} 
                        r_resp = requests.post(r_url, json=r_data, headers=r_head)
                        if r_resp.status_code != 200: raise Exception(f"Recraft failed")
                        img_url = r_resp.json()['data'][0]['url']
                        
                        img_bytes = requests.get(img_url).content
                        wp_media_url = f"{w_url.rstrip('/')}/wp-json/wp/v2/media"
                        wp_head = {
                            "Content-Disposition": f"attachment; filename=auto-img-{i+1}-{int(time.time())}.jpg", 
                            "Content-Type": "image/jpeg"
                        }
                        w_resp = requests.post(wp_media_url, headers=wp_head, data=img_bytes, auth=HTTPBasicAuth(w_user, w_pass))
                        if w_resp.status_code == 201:
                            wp_urls.append(w_resp.json().get('source_url'))
                        else:
                            raise Exception("WP Media Upload failed")
                    except Exception as e:
                        wp_urls.append("[https://placehold.co/800x400.png?text=Image+Upload+Error](https://placehold.co/800x400.png?text=Image+Upload+Error)") 
                        
                # 步骤 C2: 图片 SEO
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🖼️ 将真实图片注入文章并执行 SEO...")
                log_box.code("\n".join(logs[-5:]))
                seo_prompt = f"""
      
Your Role:

You are an SEO expert specializing in image SEO optimization to enhance search engine visibility for my website.

Your Responsibilities:

Each time I upload one or multiple images, you must generate SEO-optimized metadata for each image in the following Markdown format:

![Alternative text, concise image description (≤15 words)](#placeholder_link "Title text (≤5 words)")

Key Formatting Rules:
1. Alternative Text (Alt Text):
• Describe the image concisely in 15 words or fewer.
• Make it descriptive and meaningful for both SEO and accessibility.
2. Title Text:
• Keep it 5 words or fewer.
• It should be a short, catchy phrase that enhances the image’s SEO relevance.
3. Direct Integration (CRITICAL):
• Each image’s metadata must be presented on a separate line.
• Do NOT wrap the image tag in a code block (```markdown). Embed it directly into the article text so the image renders natively in WordPress.

My Requirements (Output Guidelines)
1. All outputs must be in English.
2. DO NOT wrap the output or the images inside a code block. 
3. Each image must have a separate SEO-optimized Alt Text and Title Text following the specified format.
4. Ensure descriptions are relevant to my industry and improve SEO rankings for my website.

[SYSTEM CRITICAL INSTRUCTION]: You MUST replace all `[Image X]` placeholders or existing image tags in the article with the REAL WordPress URLs provided below. OUTPUT THE FULL UPDATED MARKDOWN ARTICLE. Do not output code blocks around the article text or around the images.

REAL WordPress URLs to use sequentially:
1. {wp_urls[0] if len(wp_urls) > 0 else 'https://placehold.co/600'}
2. {wp_urls[1] if len(wp_urls) > 1 else 'https://placehold.co/600'}
3. {wp_urls[2] if len(wp_urls) > 2 else 'https://placehold.co/600'}
4. {wp_urls[3] if len(wp_urls) > 3 else 'https://placehold.co/600'}
5. {wp_urls[4] if len(wp_urls) > 4 else 'https://placehold.co/600'}

Article Content:
{md_input}
                """
                seo_md = model_flash.generate_content(seo_prompt, safety_settings=None).text
                time.sleep(3)

                # 步骤 C3: 双向脚注
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔗 构建 10 个双向脚注系统...")
                log_box.code("\n".join(logs[-5:]))
                
                fn_prompt = f"""
## Your Role

You are an SEO expert responsible for enhancing articles by inserting relevant external links while maintaining readability, proper formatting, and structured footnotes in Markdown format.

## Your Responsibilities

### Input

You will receive an article in Markdown format.

### Output Guidelines

1. **Identify Key Phrases for Hyperlinking**

   * Select meaningful noun phrases that require additional explanation or supporting data.
   * Do not hyperlink single words; instead, choose context-rich phrases that fit naturally within the content.
   * Exclude bolded paragraphs from hyperlinking.

2. **Insert Hyperlinks Correctly**

   * Embed links directly within the content using Markdown format (e.g., `[ISO 9001](https://www.example.com)`).
   * Avoid adding separate footnotes within bolded paragraphs.
   * Display the footnote number as an **upward superscript digit** using `<sup>` (e.g., `[ISO 9001](https://www.example.com) <sup>[1](#footnote-1){{#ref-1}}</sup>`).

3. **Ensure Proper Footnote Usage**

   * Do **not** use Markdown Extra’s `[^1]` syntax. Instead, implement a **manual bidirectional system**:

     * In the main text: `<sup>[1](#footnote-1){{#ref-1}}</sup>`
     * In the footnotes: `<span id="footnote-1">1. Short explanation. [↩︎](#ref-1)</span>`
   * At the bottom of the article, create a **“Footnotes”** section listing all referenced links.
   * Each footnote should include a concise explanation (max 20 words) of why users should visit the link.
   * After each footnote entry, add a **return link `[↩︎]`** that navigates back to the corresponding keyword in the main text.
   * Each footnote number must be unique and non-repetitive to ensure accurate linking.

4. **Maintain Consistency and Readability**

   * Each article must contain **exactly ten external links** — no more, no less.
   * No duplicate key phrases should be hyperlinked.
   * The selected phrases should be seamlessly integrated within the article to maintain smooth readability.

5. **Ensure Markdown Formatting for Output**

   * The final output must be in **Markdown format** after inserting hyperlinks and footnotes.
   * You may use minimal HTML tags (`<sup>`, `<span>`) to enable superscripts and anchor navigation.
   * Avoid unnecessary HTML to ensure compatibility across Markdown-based platforms.

---

## Example Formatting

✅ Correct:

```markdown
Certifications such as [ISO 9001](https://www.example.com) <sup>[1](#footnote-1){{#ref-1}}</sup> demonstrate a supplier’s commitment to quality management.
```

❌ Incorrect:

```markdown
Certifications such as [ISO 9001](https://www.example.com) [^1] demonstrate a supplier’s commitment to quality management.
```

---

## Footnotes Formatting

At the end of the article, include a **Footnotes** section listing all 10 inserted links along with a short explanation and return link.

✅ Markdown Example:

```markdown
---
## Footnotes  

<span id="footnote-1">1. Learn how ISO 9001 ensures consistent quality standards. [↩︎](#ref-1)</span>  
<span id="footnote-2">2. Guide to analyzing customer reviews for supplier reliability. [↩︎](#ref-2)</span>  
<span id="footnote-3">3. Role of third-party verification in supplier compliance. [↩︎](#ref-3)</span>  
<span id="footnote-4">4. Insights into cost-effective logistics for supply chains. [↩︎](#ref-4)</span>  
<span id="footnote-5">5. How trade policies affect procurement strategies. [↩︎](#ref-5)</span>  
<span id="footnote-6">6. Explanation of sustainable sourcing practices. [↩︎](#ref-6)</span>  
<span id="footnote-7">7. Impact of digital tools on supplier evaluation. [↩︎](#ref-7)</span>  
<span id="footnote-8">8. Why supplier diversity strengthens global supply chains. [↩︎](#ref-8)</span>  
<span id="footnote-9">9. Benefits of certifications for international trade compliance. [↩︎](#ref-9)</span>  
<span id="footnote-10">10. Key trends in supplier risk management. [↩︎](#ref-10)</span>  
```

[SYSTEM INSTRUCTION: OUTPUT THE FULL UPDATED MARKDOWN ARTICLE. Do not output code blocks around the article text, just the text itself.]

Article to process:
{seo_md}
                """
                final_md = model_flash.generate_content(fn_prompt, safety_settings=None).text
                
                # ==================================
                # 步骤 D: WP 自动排期发布 (脱壳核心)
                # ==================================
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 推送到 WordPress 排期...")
                log_box.code("\n".join(logs[-5:]))
                
                title = topic
                
                # 💡核心修复：暴力清洗 Markdown 外壳，防止前端将图文渲染成代码块
                raw_content = final_md.strip()
                if raw_content.startswith('```markdown'):
                    raw_content = raw_content[11:].strip()
                elif raw_content.startswith('```md'):
                    raw_content = raw_content[5:].strip()
                elif raw_content.startswith('```'):
                    raw_content = raw_content[3:].strip()
                    
                if raw_content.endswith('```'):
                    raw_content = raw_content[:-3].strip()

                final_md_clean = raw_content
                
                for line in final_md_clean.split('\n'):
                    if line.startswith("# "):
                        title = line.replace("# ", "").strip()
                        final_md_clean = final_md_clean.replace(line, "", 1) 
                        break
                        
                schedule_iso = current_schedule_time.strftime("%Y-%m-%dT%H:%M:%S")
                wp_data = {"title": title, "content": final_md_clean, "status": "future", "date": schedule_iso}
                r = requests.post(f"{w_url.rstrip('/')}/wp-json/wp/v2/posts", json=wp_data, auth=HTTPBasicAuth(w_user, w_pass))
                
                if r.status_code == 201: logs.append(f"✅ 成功！已排期至 {schedule_iso}")
                else: logs.append(f"❌ 发布失败: {r.text}")
                log_box.code("\n".join(logs[-5:]))
                
                current_schedule_time += timedelta(hours=interval_hours)
                time.sleep(10)
                
            except Exception as e:
                logs.append(f"⚠️ 发生错误，跳过此篇: {e}")
                log_box.code("\n".join(logs[-5:]))
                time.sleep(15) 
                continue
            
            progress_bar.progress((idx + 1) / len(topics))
            
        status_box.success(f"🎉 批量任务全部执行完毕！")

# ==========================================
# 左侧主控导航菜单
# ==========================================
with st.sidebar:
    st.title("⚙️ AI Writer 工业化中心")
    st.caption("版本: 2026 最终全自动版")
    page = st.radio("系统功能导航", [
        "1. 创建角色背景", 
        "2. 文章话题生成器", 
        "3. 写文章原材料生成 (单篇)",
        "4. 文章生成器 (单篇)",
        "5. 文章配图 + 一键发布 (单篇)",
        "7. 批量发布工具 (全自动无人值守) ⭐"
    ])
    st.markdown("---")
    st.info("💡 **系统状态**：模块化联通正常。")

# 路由分发
if page.startswith("1"): tool1_persona()
elif page.startswith("2"): tool2_topics()
elif page.startswith("3"): tool3_materials()
elif page.startswith("4"): tool4_article()
elif page.startswith("5"): tool5_publish()
elif page.startswith("7"): tool7_batch_publish()
