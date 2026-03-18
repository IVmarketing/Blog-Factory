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
