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


import streamlit as st
import google.generativeai as genai
import os

# ==========================================
# 0. 页面配置与大模型初始化
# ==========================================
st.set_page_config(page_title="AI Writer - 工具 1：角色背景", layout="wide")

# 获取 API Key (优先从 Secrets 获取，其次从本地环境变量获取)
api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ 未检测到 GEMINI_API_KEY。请在环境或 Secrets 中配置。")
    st.stop()

# 智能获取可用的最快模型 (用于翻译和润色)
@st.cache_resource
def get_flash_model():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in available if "flash" in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel('models/gemini-1.5-flash')

model = get_flash_model()

# ==========================================
# 1. 定义 20 个标准化的业务问题 (融合了你的 B2B 样本)
# ==========================================
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

# ==========================================
# 2. 状态管理 (记录进度和答案，实现“不怕中途退出” )
# ==========================================
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'answers' not in st.session_state:
    st.session_state.answers = [""] * len(QUESTIONS)
if 'persona_cn' not in st.session_state:
    st.session_state.persona_cn = ""
if 'persona_en' not in st.session_state:
    st.session_state.persona_en = ""

# ==========================================
# 3. UI 界面构建
# ==========================================
st.title("👤 工具 1：创建【我的角色背景】")
st.markdown("通过逐步问答，完整描述您的业务和目标客户。这份背景将作为所有自动化写作工具的“灵魂” [cite: 16]。")

# 进度条
progress = st.session_state.current_step / len(QUESTIONS)
st.progress(progress, text=f"当前进度: {st.session_state.current_step} / {len(QUESTIONS)}")

# --- 问答环节 ---
if st.session_state.current_step < len(QUESTIONS):
    q_data = QUESTIONS[st.session_state.current_step]
    
    st.subheader(f"Step {st.session_state.current_step + 1}: {q_data['title']}")
    st.markdown(f"### **{q_data['q']}**")
    st.info(f"💡 **参考示例：** {q_data['example']}")
    
    # 输入框 (绑定 session_state 中的答案)
    current_answer = st.text_area(
        "您的回答（支持随时修改）：", 
        value=st.session_state.answers[st.session_state.current_step],
        height=150,
        key=f"input_{st.session_state.current_step}"
    )
    
    # 底部导航按钮 (模拟文档的“下一步”、“上一步” [cite: 620-621])
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("⬅️ 上一步", disabled=(st.session_state.current_step == 0)):
            st.session_state.answers[st.session_state.current_step] = current_answer
            st.session_state.current_step -= 1
            st.rerun()
    with col2:
        if st.button("下一步 ➡️", type="primary"):
            st.session_state.answers[st.session_state.current_step] = current_answer
            st.session_state.current_step += 1
            st.rerun()

# --- 汇总与生成环节 (对应文档中的“汇总校对 → 一键翻译为英文” [cite: 20]) ---
else:
    st.success("🎉 所有问题已填写完毕！请检查您的业务背景汇总：")
    
    # 将 20 个答案拼接成你提供的那个优秀的 Prompt 模板格式
    draft_cn = f"""
    ## 我的角色：
    ### 关于我的业务
    姓名/职位：{st.session_state.answers[0]}
    品牌名称：{st.session_state.answers[1]}
    网站/邮箱：{st.session_state.answers[2]}
    当前运营：{st.session_state.answers[3]}
    核心产品：{st.session_state.answers[4]}
    产品特点：{st.session_state.answers[5]}
    商业模式：{st.session_state.answers[6]}
    我们的服务：{st.session_state.answers[7]}
    主要出口国家：{st.session_state.answers[8]}
    营销渠道：{st.session_state.answers[9]}

    ### 关于我的典型客户
    职位：{st.session_state.answers[10]}
    企业规模与类型：{st.session_state.answers[11]}
    年龄与性格特点：{st.session_state.answers[12]}
    沟通偏好：{st.session_state.answers[13]}
    盈利模式：{st.session_state.answers[14]}
    采购偏好/看重能力：{st.session_state.answers[15]}
    采购地区偏好：{st.session_state.answers[16]}
    采购要求/商务条件：{st.session_state.answers[17]}
    供应商寻找方式：{st.session_state.answers[18]}
    核心痛点：
    {st.session_state.answers[19]}
    """
    
    # 允许用户最后微调中文草稿
    st.session_state.persona_cn = st.text_area("您可以直接在此修改最终的中文草稿：", value=draft_cn.strip(), height=400)
    
    # 核心动作：一键翻译并保存
    if st.button("✨ 一键翻译并保存为英文角色指令 (System Prompt)", type="primary"):
        with st.spinner("AI 正在将您的业务背景转化为极其专业的英文 System Prompt..."):
            translate_prompt = f"""
            你是一位资深的 B2B 外贸营销专家。请将以下中文的客户业务背景，翻译并润色成一段极其地道、专业的英文。
            这段英文将被用作后续 AI 自动写文章时的“System Prompt（系统指令）”，用来约束 AI 的写作口吻、背景设定和受众定位。
            请确保语气专业，直接输出英文结果，不要包含任何多余的解释。
            
            原始中文背景：
            {st.session_state.persona_cn}
            """
            try:
                response = model.generate_content(translate_prompt)
                st.session_state.persona_en = response.text
                st.success("✅ 英文角色指令已生成并存入系统！它将在工具 4、5、6 中被自动调用 [cite: 624-625]。")
            except Exception as e:
                st.error(f"翻译失败: {e}")
                
    # 展示最终的英文版
    if st.session_state.persona_en:
        st.markdown("### 🏆 最终保存的英文角色指令 (供 AI 写作使用):")
        st.code(st.session_state.persona_en, language="markdown")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ 返回修改问题"):
                st.session_state.current_step = 0
                st.rerun()
        with col2:
            st.info("💡 下一步：您可以前往【工具 2：文章话题生成器】开始策划内容了。")



import streamlit as st
import google.generativeai as genai
import os
import math
import time

# ==========================================
# 0. 页面配置与大模型初始化
# ==========================================
st.set_page_config(page_title="AI Writer - 工具 2：文章话题生成器", layout="wide")

api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ 未检测到 GEMINI_API_KEY。请配置。")
    st.stop()

@st.cache_resource
def get_flash_model():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in available if "flash" in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel('models/gemini-1.5-flash')

model = get_flash_model()

# ==========================================
# 1. 状态管理
# ==========================================
if 't2_step' not in st.session_state: st.session_state.t2_step = 1
if 't2_countries' not in st.session_state: st.session_state.t2_countries = ""
if 't2_product' not in st.session_state: st.session_state.t2_product = ""
if 't2_company_type' not in st.session_state: st.session_state.t2_company_type = ""
if 't2_my_country' not in st.session_state: st.session_state.t2_my_country = "中国"
if 't2_topic_count' not in st.session_state: st.session_state.t2_topic_count = 150
if 't2_results' not in st.session_state: st.session_state.t2_results = []

# ==========================================
# 2. UI 界面 - 头部
# ==========================================
st.title("💡 工具 2：文章话题生成器")
st.markdown("""
**欢迎使用【文章话题生成器】**
通过回答 4 个简单问题，AI 就能为你生成大量精准的文章话题。
* **回答问题**：用中文回答即可，系统会自动翻译为英文话题。
* **生成与后续**：选择想生成的话题数量。建议保存到 Google Sheet 方便管理。
""")
st.divider()

# ==========================================
# 3. 核心逻辑：4 步动态问答向导
# ==========================================
step = st.session_state.t2_step

st.subheader(f"第 {step} / 4 步")
st.info("提示：所有回答用中文即可，最后会帮你翻译成英文。")

# --- 第 1 步：目标国家 ---
if step == 1:
    st.markdown("### **{目标国家}**")
    st.markdown("**问题：** 你写文章针对的目标客户国家是哪一个或哪些？")
    st.caption("**示例：**\n美国\n欧洲")
    current_val = st.text_area("你的回答：", value=st.session_state.t2_countries, height=120)
    
    # 修复点：加入 key="next_1"
    if st.button("下一步 ➡️", type="primary", key="next_1"):
        if not current_val.strip(): st.error("请至少填写一个国家")
        else:
            st.session_state.t2_countries = current_val
            st.session_state.t2_step = 2
            st.rerun()

# --- 第 2 步：三级类目名称 ---
elif step == 2:
    st.markdown("### **{三级类目名称}**")
    st.markdown("**问题：** 你本次想写文章宣传的产品是什么？")
    st.caption("**示例：** 消防无人机 / hydraulic motor")
    current_val = st.text_input("你的回答：", value=st.session_state.t2_product)
    
    col1, col2 = st.columns([1, 6])
    with col1:
        # 修复点：加入 key="prev_2"
        if st.button("⬅️ 上一步", key="prev_2"):
            st.session_state.t2_step = 1
            st.rerun()
    with col2:
        # 修复点：加入 key="next_2"
        if st.button("下一步 ➡️", type="primary", key="next_2"):
            if not current_val.strip(): st.error("请输入产品名称")
            else:
                st.session_state.t2_product = current_val
                st.session_state.t2_step = 3
                st.rerun()

# --- 第 3 步：公司类型 ---
elif step == 3:
    st.markdown("### **{公司类型}**")
    st.markdown("**问题：** 你写文章针对的目标客户公司/身份类型是什么？")
    st.caption("**示例：**\n地方公共安全机构\n能源及关键基础设施运营商")
    current_val = st.text_area("你的回答：", value=st.session_state.t2_company_type, height=120)
    
    col1, col2 = st.columns([1, 6])
    with col1:
        # 修复点：加入 key="prev_3"
        if st.button("⬅️ 上一步", key="prev_3"):
            st.session_state.t2_step = 2
            st.rerun()
    with col2:
        # 修复点：加入 key="next_3"
        if st.button("下一步 ➡️", type="primary", key="next_3"):
            if not current_val.strip(): st.error("请至少填写一种公司类型")
            else:
                st.session_state.t2_company_type = current_val
                st.session_state.t2_step = 4
                st.rerun()

# --- 第 4 步：你的国家 & 生成动作 ---
elif step == 4:
    st.markdown("### **{你的国家}**")
    st.markdown("**问题：** 你想宣传的公司是哪个国家的？")
    current_val = st.text_input("你的回答：", value=st.session_state.t2_my_country)
    st.markdown("---")
    
    target_count = st.slider("选择想生成的话题数量 (50~600)", min_value=50, max_value=600, value=st.session_state.t2_topic_count, step=50)
    
    col1, col2 = st.columns([1, 6])
    with col1:
        # 修复点：加入 key="prev_4"
        if st.button("⬅️ 上一步", key="prev_4"):
            st.session_state.t2_step = 3
            st.rerun()
    with col2:
        # 修复点：加入 key="gen_btn"
        if st.button("🚀 生成话题列表", type="primary", key="gen_btn"):
            st.session_state.t2_my_country = current_val
            st.session_state.t2_topic_count = target_count
            
            countries_list = [c.strip() for c in st.session_state.t2_countries.split('\n') if c.strip()]
            company_types_list = [t.strip() for t in st.session_state.t2_company_type.split('\n') if t.strip()]
            
            total_combinations = len(countries_list) * len(company_types_list)
            topics_per_combo = math.ceil(target_count / total_combinations)
            st.session_state.t2_results = []
            
            status_container = st.container()
            with status_container:
                st.info(f"检测到 {len(countries_list)} 个国家 × {len(company_types_list)} 个身份类型 = {total_combinations} 个组合\n每个组合生成约 {topics_per_combo} 个话题，生成后自动去重")
                progress_bar = st.progress(0)
                current_combo = 0
                
                for target_c in countries_list:
                    for comp_type in company_types_list:
                        current_combo += 1
                        with st.spinner(f"[{current_combo}/{total_combinations}] 正在生成: {target_c} × {comp_type}..."):
                            prompt = f"""
                            你是一个资深的 B2B 内容营销与 SEO 专家。
                            我的公司位于：{st.session_state.t2_my_country}。
                            我们推广的核心产品/服务是：{st.session_state.t2_product}。
                            当前我需要针对目标市场：【{target_c}】，撰写针对【{comp_type}】这一目标客户的高转化 B2B 博客文章。
                            请生成 {topics_per_combo} 个精准的【英文】文章话题（标题）。
                            要求：
                            1. 极度贴合上述行业的痛点、采购指南或技术趋势。
                            2. 标题必须是英文。
                            3. 直接输出标题列表，每行一个，不要带编号、横线或其他任何前言后语。
                            """
                            try:
                                if current_combo > 1: time.sleep(2) 
                                response = model.generate_content(prompt)
                                raw_lines = response.text.strip().split('\n')
                                clean_lines = [line.strip().lstrip('0123456789.-* ') for line in raw_lines if line.strip()]
                                st.session_state.t2_results.extend(clean_lines)
                            except Exception as e:
                                st.error(f"生成出错: {e}")
                        
                        progress_bar.progress(current_combo / total_combinations)
                
                # 自动去重与截断
                st.session_state.t2_results = list(dict.fromkeys(st.session_state.t2_results))
                if len(st.session_state.t2_results) > target_count:
                    st.session_state.t2_results = st.session_state.t2_results[:target_count]
                st.success("🎉 话题生成完毕！")

# ==========================================
# 4. 结果展示区
# ==========================================
if st.session_state.t2_results:
    st.markdown("---")
    st.subheader(f"文章话题列表（AI 生成，英文）- 共 {len(st.session_state.t2_results)} 个")
    
    final_text = "\n".join(st.session_state.t2_results)
    st.text_area("一键复制原始文本：", value=final_text, height=400)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 导出 CSV", 
            data="Topic\n" + final_text, 
            file_name=f"topics_{st.session_state.t2_product}.csv", 
            mime="text/csv",
            key="download_csv"
        )
    with col2:
        if st.button("🔄 重置此工具", key="reset_btn"):
            st.session_state.t2_step = 1
            st.session_state.t2_results = []
            st.rerun()
            



import streamlit as st
import google.generativeai as genai
import os
import time
from datetime import datetime

# ==========================================
# 0. 页面配置与初始化
# ==========================================
st.set_page_config(page_title="AI Writer - 写文章原材料生成", layout="wide")

api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ 未检测到 GEMINI_API_KEY。请配置。")
    st.stop()

# 使用 Pro 模型进行深度调研
@st.cache_resource
def get_pro_model():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in available if "pro" in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel('models/gemini-1.5-pro')

model = get_pro_model()

# 宽松的安全策略，防止 B2B 专业词汇被误杀
safe_config = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# ==========================================
# 1. 状态管理
# ==========================================
if 't3_step' not in st.session_state: st.session_state.t3_step = 1
if 't3_topics_raw' not in st.session_state: st.session_state.t3_topics_raw = ""
if 't3_topics_list' not in st.session_state: st.session_state.t3_topics_list = []
if 't3_ai_results' not in st.session_state: st.session_state.t3_ai_results = {}
if 't3_personal_insights' not in st.session_state: st.session_state.t3_personal_insights = {}
if 't3_batch_personal' not in st.session_state: st.session_state.t3_batch_personal = ""

# ==========================================
# 2. UI 界面 - 头部说明
# ==========================================
st.title("🗄️ 写文章原材料生成")
st.markdown("""
**深度调研 + 个人见解 | 单篇发布**
把话题转化为完整的写作原材料，包含 AI 深度调研结果（Perplexity + Google SERP）和你的个人见解。

✨ **核心功能**
✓ AI 深度调研（Perplexity + Google）
✓ 支持录入个人见解
✓ 支持批量粘贴多个话题
✓ 结果可一键复制
""")
st.divider()

step = st.session_state.t3_step
st.subheader(f"第 {step} / 4 步")
st.caption("批量输入话题 → AI见解调研 → 录入个人见解 → 输出可复制的原材料")

# ==========================================
# 第 1 步：批量粘贴话题
# ==========================================
if step == 1:
    st.markdown("### 第 1 步：批量粘贴话题")
    st.markdown("请从 Excel / Google Sheets 中复制你的话题列表，直接粘贴到下方，每一行代表一个话题。")
    st.warning("⚠️ 仅用于「单篇发布」工具：如果你使用的是「批量发布工具」，不需要在这里生成文章原材料，批量发布工具已内置自动调研流程。")
    
    current_val = st.text_area("粘贴话题列表：", value=st.session_state.t3_topics_raw, height=150)
    
    # 动态显示话题数量
    topic_count = len([t for t in current_val.split('\n') if t.strip()])
    st.info(f"当前话题数量：**{topic_count}** 个 | 每个话题将进行 Perplexity + SERP 见解调研")
    
    if st.button("下一步 ➡️ (开始 AI 调研)", type="primary", key="t3_btn_1"):
        if topic_count == 0:
            st.error("请至少输入一个话题！")
        else:
            st.session_state.t3_topics_raw = current_val
            st.session_state.t3_topics_list = [t.strip() for t in current_val.split('\n') if t.strip()]
            st.session_state.t3_step = 2
            st.rerun()

# ==========================================
# 第 2 步：AI 见解调研 (接入你的核心 Prompt)
# ==========================================
elif step == 2:
    st.markdown("### 第 2 步：AI 见解调研")
    st.info("正在服务器后台对每个话题进行 Perplexity 深度调研 + Google SERP 见解分析。\n✓ 你可以安全关闭此页面甚至关闭电脑，任务会在服务器后台继续执行。再次打开时可以从「调研任务」按钮查看进度。")
    
    topics = st.session_state.t3_topics_list
    total = len(topics)
    
    # 如果还没调研过，则开始循环调用大模型
    if len(st.session_state.t3_ai_results) < total:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, topic in enumerate(topics):
            # 跳过已完成的话题
            if topic in st.session_state.t3_ai_results:
                continue
                
            status_text.text(f"正在深度调研 ({idx+1}/{total}): {topic}")
            
            # --- 融入你提供的硬核 Prompt，并要求顺便输出 4 个 H2 ---
            prompt = f"""
            我会给你一个话题，请你帮我生成 10 条英文见解，并顺便提供 4 个相关的二级标题。 
            话题：{topic}
            
            要求： 
            1. 你要基于 Google SERP 排名前 10 的自然搜索页面，提炼出 6 条明确提到的关键见解。 
            2. 再补充 4 条不在前 10 页中出现，但基于其他可靠信息或逻辑推理得出的见解。 
            3. 总共输出 10 条见解。 
            4. 只输出见解内容和 4 个二级标题，不要提到数据来源、研究过程，也不要写解释性文字。 
            5. 输出必须是英文，每条见解简洁、事实化。
            
            请严格按照以下格式输出（保留前面的星号标签）：
            *二级标题：
            * [H2 1]
            * [H2 2]
            * [H2 3]
            * [H2 4]
            *AI见解：
            1. [见解 1]
            ...
            10. [见解 10]
            """
            
            try:
                # 为了避免 429 报错，稍微延迟
                if idx > 0: time.sleep(2)
                response = model.generate_content(prompt, safety_settings=safe_config)
                st.session_state.t3_ai_results[topic] = response.text
            except Exception as e:
                st.error(f"话题 '{topic}' 调研失败: {e}")
                st.session_state.t3_ai_results[topic] = "调研失败，请稍后重试。"
                
            progress_bar.progress((idx + 1) / total)
            
        status_text.success(f"✅ 调研完成 ({total}/{total})")
    else:
        st.success(f"✅ 调研完成 ({total}/{total})")
        
    # 展示调研结果
    with st.expander("👁️ 查看 AI 调研结果", expanded=True):
        for idx, topic in enumerate(topics):
            st.markdown(f"**{idx+1}. {topic}**")
            st.text(st.session_state.t3_ai_results.get(topic, ""))
            st.divider()

    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("⬅️ 上一步", key="t3_btn_prev2"):
            st.session_state.t3_step = 1
            st.rerun()
    with col2:
        if st.button("下一步 ➡️ (录入个人见解)", type="primary", key="t3_btn_next2"):
            st.session_state.t3_step = 3
            st.rerun()

# ==========================================
# 第 3 步：录入个人见解
# ==========================================
elif step == 3:
    st.markdown("### 第 3 步：录入个人见解（选填）")
    st.markdown("你可以为每个话题添加你的专业见解，这些见解将与 AI 调研结果合并。个人见解越独特，生成的文章越有竞争力。即使留空，AI 也能生成高质量内容。")
    
    input_mode = st.radio("选择录入方式：", ["方式 1：逐一输入 - 每个话题对应一个输入框", "方式 2：批量粘贴 - 从 Google Sheet 复制粘贴，每行对应一个话题"])
    
    topics = st.session_state.t3_topics_list
    
    if "方式 1" in input_mode:
        for idx, topic in enumerate(topics):
            # 初始化字典中的键
            if topic not in st.session_state.t3_personal_insights:
                st.session_state.t3_personal_insights[topic] = ""
                
            st.markdown(f"**{idx+1}. {topic}**")
            st.session_state.t3_personal_insights[topic] = st.text_input(
                f"输入见解 (话题 {idx+1})：", 
                value=st.session_state.t3_personal_insights[topic],
                label_visibility="collapsed",
                key=f"p_insight_{idx}"
            )
    else:
        st.info("提示：请确保粘贴的行数与话题数一致。每行对应一个话题。")
        batch_input = st.text_area("批量粘贴个人见解：", value=st.session_state.t3_batch_personal, height=200)
        st.session_state.t3_batch_personal = batch_input
        
        # 实时将批量输入分配给各个话题
        batch_lines = [line.strip() for line in batch_input.split('\n')]
        for idx, topic in enumerate(topics):
            if idx < len(batch_lines):
                st.session_state.t3_personal_insights[topic] = batch_lines[idx]
            else:
                st.session_state.t3_personal_insights[topic] = ""

    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("⬅️ 上一步", key="t3_btn_prev3"):
            st.session_state.t3_step = 2
            st.rerun()
    with col2:
        if st.button("下一步 ➡️ (生成最终原材料)", type="primary", key="t3_btn_next3"):
            st.session_state.t3_step = 4
            st.rerun()

# ==========================================
# 第 4 步：生成结果
# ==========================================
elif step == 4:
    st.markdown("### 第 4 步：生成结果")
    st.markdown("下面是最终的写文章原材料，每行包含：主标题 + 二级标题 + 见解（AI调研见解 + 个人见解）。可以直接复制粘贴到 Google Sheet，以后写文章时只需复制一段原材料即可。")
    
    topics = st.session_state.t3_topics_list
    current_time = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    
    st.success(f"生成时间: {current_time} | 共 {len(topics)} 条 | ✓ 已同步云端")
    
    # 拼装最终结果
    final_output = ""
    for topic in topics:
        ai_res = st.session_state.t3_ai_results.get(topic, "*二级标题：\n* 未获取\n*AI见解：\n未获取")
        personal_res = st.session_state.t3_personal_insights.get(topic, "")
        
        # 组装格式，完全对齐你的文档要求
        final_output += f"*主标题：{topic}\n{ai_res}\n*人工见解：{personal_res}\n\n"
        final_output += "--------------------------------------------------\n\n"

    st.text_area("最终原材料提取结果：", value=final_output.strip(), height=400, key="t3_final_area")
    
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("⬅️ 上一步", key="t3_btn_prev4"):
            st.session_state.t3_step = 3
            st.rerun()
    with col2:
        if st.button("🔄 重置此工具 (开始新任务)", type="primary", key="t3_btn_reset"):
            # 清理状态，重头开始
            for key in ['t3_step', 't3_topics_raw', 't3_topics_list', 't3_ai_results', 't3_personal_insights', 't3_batch_personal']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
            




import streamlit as st
import google.generativeai as genai
import os
import time

# ==========================================
# 0. 页面配置与大模型初始化
# ==========================================
st.set_page_config(page_title="AI Writer - 一键生成文章", layout="wide")

api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ 未检测到 GEMINI_API_KEY。请配置。")
    st.stop()

# 核心写作必须使用 Pro 模型以保证逻辑深度和 1500 字长度
@st.cache_resource
def get_pro_model():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in available if "pro" in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel('models/gemini-1.5-pro')

# 翻译和校验等轻量任务使用 Flash
@st.cache_resource
def get_flash_model():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in available if "flash" in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel('models/gemini-1.5-flash')

model_pro = get_pro_model()
model_flash = get_flash_model()

# 彻底关闭安全限制，防止长文因 B2B 工业词汇被腰斩
safe_config = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# ==========================================
# 1. 状态管理
# ==========================================
if 'persona_en' not in st.session_state: st.session_state.persona_en = ""
if 't4_raw_materials' not in st.session_state: st.session_state.t4_raw_materials = ""
if 't4_article_draft' not in st.session_state: st.session_state.t4_article_draft = ""
if 't4_validation_res' not in st.session_state: st.session_state.t4_validation_res = ""

# ==========================================
# 2. UI 界面 - 头部
# ==========================================
st.title("✍️ 文章生成器 (一键生成 Markdown)")
st.markdown("""
**单篇发布 | 融合背景与素材**
输入角色背景和写作原材料，AI 会为你生成一篇完整的 Markdown 格式文章。支持在线编辑、格式校验和多语言翻译 [cite: 90-97]。
""")
st.divider()

# ==========================================
# 第 1 步：输入角色背景
# ==========================================
st.subheader("第 1 步：输入角色背景")
st.caption("AI 会根据角色背景来定制文章的风格和内容 [cite: 207-208]。")

# 如果之前工具1没有保存背景，提供默认的 Fortis 样本供测试
default_persona = st.session_state.persona_en if st.session_state.persona_en else """### About My Business
Name: Fortis
Email: sales@fortissystemsgroup.com
Website: www.fortissystemsgroup.com
Brand Name: Fortis
Country: USA
Products: Custom Hydraulic Motors
Business Model: B2B international export trade...
(请在此处粘贴您完整的业务和客户背景)"""

persona_input = st.text_area("粘贴或编辑「我的角色背景」：", value=default_persona, height=150, key="t4_persona")

# ==========================================
# 第 2 步：输入写作原材料
# ==========================================
st.subheader("第 2 步：输入写作原材料")
st.caption("把从上一个工具生成的原材料粘贴进来，建议包含：主标题、4 个二级标题、AI 见解、个人见解 [cite: 209-210]。")

default_materials = """*主标题：What are the three main types of hydraulic motors?
*二级标题：
* What is the hydraulic motor?
* How to size a hydraulic motor?
* Why do hydraulic motors fail?
* What is the most common hydraulic motor?
*AI见解：There are three major types of hydraulic motors: gear motors, piston motors, and vane motors...
*人工见解：齿轮马达，柱塞马达，风扇马达"""

materials_input = st.text_area("粘贴写作原材料：", value=st.session_state.t4_raw_materials or default_materials, height=200, key="t4_materials")

# --- 核心动作：生成文章 ---
if st.button("📝 生成文章 (约需 1~3 分钟)", type="primary", key="t4_gen_btn"):
    if not materials_input.strip():
        st.error("请粘贴写作原材料！")
    else:
        st.session_state.t4_raw_materials = materials_input
        st.session_state.t4_article_draft = ""
        st.session_state.t4_validation_res = ""
        
        with st.spinner("AI 正在严格执行 SOP 撰写 1500 字深度长文，请稍候..."):
            # ==========================================
            # 💡 核心 Prompt 组装 (完全对齐你的指令要求)
            # ==========================================
            prompt = f"""
            # Your Role:
            你是一个我写博客文章的枪手，你会使用我的口吻，用Markdown语言输出指定格式的博客文章。

            # Your Responsibilities:
            当我输入如下格式的内容给你时:
            {materials_input}

            你按照如下的格式输出一篇文章给我：

            # [这里是文章的主标题，以问号结尾]

            ![alt with keywords]("https://placehold.co/600x400.jpg")

            [开头第一段，会使用PAS策略，吸引读者注意力，在这一段里使用第一人称的语气。(Max 30 words)]

            **[开头第二段，回答标题提出的问题，这个段落，后面会用来竞争谷歌的精选摘要。(Min 30 words and Max 50 words)]**

            [承上启下的段落，会挽留客户继续往下阅读。]

            ## [二级标题1，以问号结尾]

            [开头第一段，会使用PAS策略，吸引读者注意力，在这一段里使用第一人称的语气。(Max 30 words)]

            **[开头第二段，回答标题提出的问题，这个段落，后面会用来竞争谷歌的精选摘要。(Min 30 words and Max 50 words)]**

            ![alt with keywords]("https://placehold.co/600x400.jpg")

            [Dive deeper paragraph: 根据二级标题，继续延展和深入，可以用批判性思维，来拆分问题，帮助读者更加深入地理解。(Min 200 words)]
            
            (请对剩下的 3 个二级标题重复上述 H2 结构)

            ## Conclusion

            [写一段结论，总结全文。(Max 30 words)]

            # My Role:
            {persona_input}

            # My Requirements:
            1. 文章的长度，不得少于1500个单词，文章的每个Dive deeper paragraph，都不得少于200个单词；
            2. 全文除了所有的Featured paragraphs必须使用第一人称的口吻进行写作，在必要时补充个人故事；
            3. 在二级标题之下的段落中，当进行Dive deeper paragraph写作时，多穿插一些必要的Markdown格式的H3s和表格；
            4. 写作风格介于书面学术写作和口语描述之间，所有句子都有主语，使用Plain English和简单词汇，让高中学生也能读懂，不要用复杂的长难句，尽可能用短句输出；
            5. 将所有句子中过渡词和连接词替换成最基础，最常用的词语。保证句子的逻辑关系清晰，不要主动添加任何总结（除非文章最后的Conclusion部分）；
            6. 你输出给我的内容不能包含任何Leading paragraph:、Featured paragraph:、Transition paragraph:、Dive deeper paragraph:、LOOP START、LOOP END这些或类似于这些的解释性文本；
            7. 图片占位符用以下链接表示：![alt with keywords]("https://placehold.co/600x400.jpg")
            8. 文章默认使用英语输出；
            9. 你输出给我的文章，必须转换成Markdown格式；
            10. 你输出给我的内容，必须包含至少3个表格；
            11. 在每个二级标题下的Featured paragraph下边的位置生成图片占位符；
            12. 在每个二级标题下的图片占位符之下的位置都要生成Dive deeper paragraph。
            """
            
            try:
                # 开启流式输出 (打字机效果) 避免 UI 假死
                response = model_pro.generate_content(prompt, stream=True, safety_settings=safe_config)
                placeholder = st.empty()
                full_text = ""
                for chunk in response:
                    if chunk.text:
                        full_text += chunk.text
                        placeholder.markdown(full_text + "▌")
                st.session_state.t4_article_draft = full_text
                st.success("✅ 文章生成完毕！")
            except Exception as e:
                st.error(f"文章生成中断: {e}")

# ==========================================
# 第 3 步：编辑与使用
# ==========================================
if st.session_state.t4_article_draft:
    st.markdown("---")
    st.subheader("第 3 步：编辑与使用 [cite: 211]")
    st.caption("生成的文章可以在线编辑修改。生成后建议先用「校验」功能检查格式 。")
    
    # 顶部工具栏
    col1, col2, col3 = st.columns([1.5, 2, 2])
    
    with col1:
        # 校验功能
        if st.button("✅ 一键校验格式", key="t4_validate_btn"):
            draft = st.session_state.t4_article_draft
            words = len(draft.split())
            h2_count = draft.count("## ") - draft.count("### ") - (1 if "## Conclusion" in draft else 0)
            img_count = draft.count("![")
            table_count = draft.count("|---|")
            
            val_text = f"""
            **校验结果：**
            - **字数统计**: 约 {words} 词 (目标: >1500)
            - **H2 数量**: {h2_count} 个 (目标: 4)
            - **图片占位符**: {img_count} 个 (目标: 5)
            - **Markdown表格**: {table_count} 个 (目标: ≥3)
            """
            st.session_state.t4_validation_res = val_text
            
    with col2:
        # 翻译功能 [cite: 478-490]
        lang_options = ["简体中文", "繁体中文", "日本語", "한국어", "Español", "Deutsch", "Français", "Português", "Italiano", "Русский", "Tiếng Việt", "العربية"]
        target_lang = st.selectbox("选择翻译语言 (不扣费)：", lang_options, label_visibility="collapsed")
    with col3:
        if st.button("🌐 开始翻译", key="t4_translate_btn"):
            with st.spinner(f"正在翻译为 {target_lang}..."):
                try:
                    p = f"Translate the following Markdown article into {target_lang}. Keep all the Markdown formatting (like #, ##, tables, and image links) intact:\n\n{st.session_state.t4_article_draft}"
                    res = model_flash.generate_content(p, safety_settings=safe_config)
                    st.session_state.t4_article_draft = res.text # 覆盖原草稿
                    st.success(f"✅ 已翻译为 {target_lang}")
                except Exception as e: st.error(e)

    # 显示校验结果
    if st.session_state.t4_validation_res:
        st.info(st.session_state.t4_validation_res)

    # 核心编辑器
    word_count = len(st.session_state.t4_article_draft.split())
    st.markdown(f"**Word count: {word_count}** [cite: 244]")
    
    st.session_state.t4_article_draft = st.text_area(
        "Markdown 编辑器：", 
        value=st.session_state.t4_article_draft, 
        height=600, 
        key="t4_editor"
    )
    
    # 预览与复制区
    with st.expander("👁️ 预览网页渲染效果 / 复制内容"):
        st.markdown(st.session_state.t4_article_draft, unsafe_allow_html=True)
        st.code(st.session_state.t4_article_draft, language="markdown")





import streamlit as st
import google.generativeai as genai
import os
import requests
from requests.auth import HTTPBasicAuth
import re

# ==========================================
# 0. 页面配置与大模型初始化
# ==========================================
st.set_page_config(page_title="AI Writer - 配图与一键发布", layout="wide")

def get_config(key): return st.secrets.get(key) or os.getenv(key)
api_key = get_config("GEMINI_API_KEY")

if api_key: genai.configure(api_key=api_key)
else: st.stop()

@st.cache_resource
def get_model(model_type="flash"):
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = next((m for m in available if model_type in m), available[0])
        return genai.GenerativeModel(target)
    except:
        return genai.GenerativeModel(f'models/gemini-1.5-{model_type}')

model_pro = get_model("pro") # 用于处理复杂的脚注插入
model_flash = get_model("flash") # 用于处理短文本 SEO 和配图 Prompt

safe_config = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# ==========================================
# 1. 状态管理
# ==========================================
if 'persona_en' not in st.session_state: st.session_state.persona_en = ""
if 't6_markdown_input' not in st.session_state: st.session_state.t6_markdown_input = ""
if 't6_img_prompts' not in st.session_state: st.session_state.t6_img_prompts = ""
if 't6_seo_markdown' not in st.session_state: st.session_state.t6_seo_markdown = ""
if 't6_final_markdown' not in st.session_state: st.session_state.t6_final_markdown = ""

# ==========================================
# 2. UI 界面 - 头部
# ==========================================
st.title("🚀 工具 6：文章配图 + 一键发布")
st.markdown("""
**配图 → SEO → 发布一条龙 | 单篇发布**
为文章自动生成精美配图提示词，自动生成 SEO Metadata 和复杂的双向脚注外链，一键发布到 WordPress。
""")
st.divider()

# ==========================================
# 第 1 步：输入角色背景
# ==========================================
st.subheader("第 1 步：确认「我的角色背景」")
st.caption("AI 会根据你的角色背景生成更贴合自己行业的配图提示词 [cite: 498-504]。")

default_persona = st.session_state.persona_en if st.session_state.persona_en else """### About My Business
Name: Fortis
Products: Custom Hydraulic Motors..."""

persona_input = st.text_area("角色背景 (用于配图基调)：", value=default_persona, height=100, disabled=(st.session_state.persona_en != ""))
if not st.session_state.persona_en:
    st.warning("⚠️ 检测到您未在工具 1 中保存背景，当前使用的是默认示例。建议您先返回工具 1 进行设置。")

# ==========================================
# 第 2 步：粘贴 Markdown 文章
# ==========================================
st.subheader("第 2 步：粘贴 Markdown 文章全文")
st.caption("直接粘贴完整 Markdown（包含 H1/H2、段落、图片占位符）。系统会自动分析文章结构并为每个部分生成配图提示词 [cite: 516-519]。")

md_input = st.text_area("粘贴文章全文：", value=st.session_state.t6_markdown_input, height=200, key="t6_md_input")

# ==========================================
# 第 3 步：自动化 SEO 与配图提示词生成
# ==========================================
st.subheader("第 3 步：自动处理 (图片提示词 + SEO + 脚注)")
st.caption("这一步将并行处理您提供的三个核心 Prompt。")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🎨 1. 生成 5 张配图 Prompt", use_container_width=True):
        if not md_input: st.error("请先粘贴文章！")
        else:
            with st.spinner("正在生成 Recraft 级配图提示词..."):
                p = f"""
                # Your Role:
                You will generate Recraft.ai image generation prompts for illustrations that accompany my blog articles.
                
                # Article Content:
                {md_input}
                
                # My Role:
                {persona_input}
                
                # Your Responsibilities:
                Generate FIVE image generation prompts.
                1. Start each prompt with a concise Chinese title.
                2. Each prompt must be at least 70 words long in English.
                3. Include: Objects, Colors/lighting, Perspective, Artistic style (e.g., photography, 3D render).
                """
                try:
                    res = model_flash.generate_content(p, safety_settings=safe_config)
                    st.session_state.t6_img_prompts = res.text
                    st.success("✅ 配图 Prompt 生成完毕")
                except Exception as e: st.error(e)

with col2:
    if st.button("🖼️ 2. 优化图片 SEO (Alt & Title)", use_container_width=True):
        if not md_input: st.error("请先粘贴文章！")
        else:
            with st.spinner("正在为 [Image X] 占位符注入 SEO 元数据..."):
                p = f"""
                # Your Role: SEO expert specializing in image SEO optimization.
                
                # Article Context:
                {md_input}
                
                # Task:
                Find all `[Image X]` placeholders or `![alt with keywords]("https://placehold.co/600x400.jpg")` in the article.
                Replace them with strictly formatted SEO markdown:
                `![Alternative text, concise image description (≤15 words)](https://placehold.co/800x400.png "Title text (≤5 words)")`
                
                Output the FULL updated article in Markdown.
                """
                try:
                    res = model_flash.generate_content(p, safety_settings=safe_config)
                    st.session_state.t6_seo_markdown = res.text
                    st.success("✅ 图片 SEO 注入完毕")
                except Exception as e: st.error(e)

with col3:
    if st.button("🔗 3. 注入 10 个高级双向脚注", use_container_width=True):
        source_text = st.session_state.t6_seo_markdown if st.session_state.t6_seo_markdown else md_input
        if not source_text: st.error("请先粘贴文章或完成上一步！")
        else:
            with st.spinner("正在分析上下文并植入双向脚注 (这需要较强逻辑，约需 30 秒)..."):
                p = f"""
                # Your Role: SEO expert enhancing articles with external links.
                
                # Input Article:
                {source_text}
                
                # Output Guidelines:
                1. Identify exactly 10 meaningful noun phrases for hyperlinking. Do not hyperlink bolded paragraphs.
                2. Insert manual bidirectional footnotes in the text: `[Phrase](https://www.example.com) <sup>[1](#footnote-1){{#ref-1}}</sup>`
                3. At the VERY END of the article, create a "## Footnotes" section.
                4. Format footnotes exactly like this: `<span id="footnote-1">1. Short explanation. [↩︎](#ref-1)</span>`
                5. Output the FULL updated article in Markdown.
                """
                try:
                    res = model_pro.generate_content(p, safety_settings=safe_config)
                    st.session_state.t6_final_markdown = res.text
                    st.success("✅ 脚注系统植入完毕")
                except Exception as e: st.error(e)

# --- 展示处理结果 ---
if st.session_state.t6_img_prompts:
    with st.expander("👁️ 查看生成的配图 Prompt (用于 Midjourney / Recraft)"):
        st.code(st.session_state.t6_img_prompts, language="markdown")

if st.session_state.t6_final_markdown or st.session_state.t6_seo_markdown:
    st.subheader("最终优化的 Markdown 文章 (含 SEO & 脚注)")
    st.session_state.t6_final_markdown = st.text_area(
        "您可以在发布前最后一次校对代码：", 
        value=st.session_state.t6_final_markdown or st.session_state.t6_seo_markdown, 
        height=400
    )

# ==========================================
# 第 4 步：配置 WordPress → 一键发布
# ==========================================
st.markdown("---")
st.subheader("第 4 步：配置 WordPress → 一键发布")
st.info("💡 不知道应用密码在哪拿？[cite: 584-589]\n1. 打开 WP 后台 -> 用户 -> 个人资料\n2. 找到应用密码 (Application Passwords) -> 新增\n3. 复制生成的长串密码粘贴到下方。")

c1, c2, c3 = st.columns(3)
with c1: wp_url_input = st.text_input("WordPress 站点地址 (含 https://)", value=get_config("WP_URL") or "")
with c2: wp_user_input = st.text_input("WordPress 用户名", value=get_config("WP_USER") or "")
with c3: wp_pass_input = st.text_input("应用密码", type="password", value=get_config("WP_APP_PASSWORD") or "")

publish_status = st.selectbox("发布状态", ["draft (保存为草稿)", "publish (立即公开)"])

if st.button("🚀 立即推送至 WordPress", type="primary", use_container_width=True):
    final_content = st.session_state.t6_final_markdown or st.session_state.t6_seo_markdown or md_input
    if not final_content:
        st.error("没有可发布的文章内容！")
    elif not all([wp_url_input, wp_user_input, wp_pass_input]):
        st.error("请完整填写 WordPress 的三个凭证。")
    else:
        with st.spinner("正在通过 REST API 推送至您的网站后台..."):
            try:
                endpoint = f"{wp_url_input.rstrip('/')}/wp-json/wp/v2/posts"
                
                # 智能提取 Markdown 首行作为 WP 标题
                title = "AI SEO Article"
                for line in final_content.split('\n'):
                    if line.startswith("# "):
                        title = line.replace("# ", "").strip()
                        # 将正文中的 H1 删掉，避免 WP 中出现两个大标题
                        final_content = final_content.replace(line, "", 1)
                        break
                        
                data = {
                    "title": title, 
                    "content": final_content, 
                    "status": publish_status.split()[0]
                }
                
                r = requests.post(endpoint, json=data, auth=HTTPBasicAuth(wp_user_input, wp_pass_input))
                if r.status_code == 201:
                    st.balloons()
                    link = r.json().get('link')
                    st.success(f"🎉 成功！文章已推送至您的网站。")
                    st.markdown(f"**[点击这里查看文章]({link})**")
                else: 
                    st.error(f"推送失败 ({r.status_code}): {r.text}")
                    st.warning("⚠️ 如果您使用 SiteGround 等主机，可能被防火墙拦截，请检查后台防盗链或白名单设置 [cite: 590-592]。")
            except Exception as e: 
                st.error(f"连接或网络失败: {e}")







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
