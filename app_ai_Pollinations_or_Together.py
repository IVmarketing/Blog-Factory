import streamlit as st
import google.generativeai as genai
import os
import math
import time
import requests
import json
import urllib.parse
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta

# ==========================================
# 0. 全局配置与模型初始化 (对接第三方中转 API)
# ==========================================
st.set_page_config(page_title="AI Writer 工业化中心 (完美全量版)", layout="wide")

def get_config(key): return st.secrets.get(key) or os.getenv(key)
api_key = get_config("GEMINI_API_KEY")

if api_key: 
    genai.configure(
        api_key=api_key,
        transport="rest",
        client_options={"api_endpoint": "api.viviai.cc"}
    )
else: 
    st.error("❌ 未检测到 GEMINI_API_KEY。请配置。")
    st.stop()

@st.cache_resource
def get_model(model_type="flash"):
    return genai.GenerativeModel('models/gemini-3-flash-preview')

model_flash = get_model("flash")
model_pro = get_model("pro")
safe_config = None

# ==========================================
# 1. 全局状态管理
# ==========================================
def init_session_state():
    if 't1_step' not in st.session_state: st.session_state.t1_step = 0
    if 't1_answers' not in st.session_state: st.session_state.t1_answers = [""] * 20
    if 'persona_cn' not in st.session_state: st.session_state.persona_cn = ""
    if 'persona_en' not in st.session_state: st.session_state.persona_en = ""
    
    if 't2_step' not in st.session_state: st.session_state.t2_step = 1
    if 't2_countries' not in st.session_state: st.session_state.t2_countries = ""
    if 't2_product' not in st.session_state: st.session_state.t2_product = ""
    if 't2_company_type' not in st.session_state: st.session_state.t2_company_type = ""
    if 't2_my_country' not in st.session_state: st.session_state.t2_my_country = "中国"
    if 't2_topic_count' not in st.session_state: st.session_state.t2_topic_count = 150
    if 't2_results' not in st.session_state: st.session_state.t2_results = []
    
    if 't3_step' not in st.session_state: st.session_state.t3_step = 1
    if 't3_topics_raw' not in st.session_state: st.session_state.t3_topics_raw = ""
    if 't3_topics_list' not in st.session_state: st.session_state.t3_topics_list = []
    if 't3_ai_results' not in st.session_state: st.session_state.t3_ai_results = {}
    if 't3_personal_insights' not in st.session_state: st.session_state.t3_personal_insights = {}
    if 't3_batch_personal' not in st.session_state: st.session_state.t3_batch_personal = ""
    if 't3_final_materials' not in st.session_state: st.session_state.t3_final_materials = ""
    
    if 't4_article_draft' not in st.session_state: st.session_state.t4_article_draft = ""
    if 't4_validation_res' not in st.session_state: st.session_state.t4_validation_res = ""
    
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
# 工具 3：写文章原材料生成
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
3. [见解 3]
4. [见解 4]
5. [见解 5]
6. [见解 6]
7. [见解 7]
8. [见解 8]
9. [见解 9]
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
# 工具 4：文章生成器 (单篇测试)
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

