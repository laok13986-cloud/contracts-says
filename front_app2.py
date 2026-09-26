import streamlit as st
import requests
import time
import os
import subprocess

# 自动尝试安装缺失的库
try:
    import streamlit_autorefresh
except ImportError:
    subprocess.check_call(["pip", "install", "streamlit-autorefresh"])
    import streamlit_autorefresh

# 💡 新增：设置前端看板每 10 秒自动刷新一次页面（无需手动按 F5）
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=10000, key="data_refresher") # 10000 毫秒 = 10 秒

# ... (保持你原本的 Streamlit 页面代码不变) ...


# 配置后端 API 的基础路径 (对应你的 FastAPI 地址)
BASE_URL = "http://127.0.0.1:8001"

st.set_page_config(page_title="公司合同与流程监控系统", layout="wide")
st.title("💼 公司合同与操作流程监控看板")

# ==========================================
# 1. 初始化 Session 状态
# ==========================================
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = ""

# ==========================================
# 2. 侧边栏：用户登录模块
# ==========================================
st.sidebar.header("🔐 用户身份验证")

# (这里为了方便调试，暂时跳过真实的 Token 拦截；在实际生产中你还可以配合 JWT)
st.session_state.token = "dummy-token"  
st.session_state.username = "boss"

st.sidebar.write(f"当前登录用户: **{st.session_state.username}**")
if st.sidebar.button("切换/退出登录"):
    st.sidebar.info("已重置环境")

headers = {"Authorization": f"Bearer {st.session_state.token}"}

# ==========================================
# 3. 主界面：功能分栏
# ==========================================
tab1, tab2 = st.tabs(["📊 合同动态看板", "➕ 录入新合同"])

# ------------------------------------------
# Tab 1: 合同动态看板
# ------------------------------------------
with tab1:
    st.subheader("📋 所有合同执行状态一览")
    
    try:
        res = requests.get(f"{BASE_URL}/contracts/", headers=headers)
        if res.status_code == 200:
            contracts = res.json()
            
            if not contracts:
                st.info("目前系统中暂无合同数据，请前往'录入新合同'页面添加。")
            else:
                for c in contracts:
                    # 💡 核心自动化升级点：智能付款与进度检测警告
                    warning_flag = False
                    is_finished = (c['progress'] == "100%")
                    is_unpaid = (c['payment_status'] == "未付款")
                    
                    header_status = f"📄 合同：{c['contract_number']} | 阶段：{c['stage']}"
                    if is_finished and is_unpaid:
                        header_status += " ⚠️ [警告：合同已完成但未付款！]"
                        warning_flag = True
                    
                    with st.expander(header_status, expanded=warning_flag):
                        # 如果出现异常，首行渲染红色警告横幅
                        if warning_flag:
                            st.error("🚨 **系统智能检测：该合同的所有操作步骤均已完成，但当前付款状态仍为【未付款】！请尽快催收货款。**")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("合同当前阶段", c['stage'])
                        with col2:
                            st.metric("付款状态", c['payment_status'])
                        with col3:
                            st.metric("流程自动进度", c['progress'])
                        
                        # 进度条显示 (从后端自动计算得来)
                        progress_float = float(c['progress'].replace('%', '')) / 100.0
                        st.progress(progress_float)
                        
                        # 修改付款状态
                        new_payment = st.selectbox(
                            "更改付款状态", 
                            ["未付款", "已付款"], 
                            index=0 if c['payment_status'] == "未付款" else 1,
                            key=f"pay_{c['id']}"
                        )
                        if new_payment != c['payment_status']:
                            requests.put(f"{BASE_URL}/contracts/{c['id']}/payment?payment_status={new_payment}", headers=headers)
                            st.toast("付款状态已更新！")
                            st.rerun()

                        st.write("---")
                        st.write("**👣 详细操作步骤流转与文件归档：**")
                        
                        # 渲染步骤列表
                        for step in c['steps']:
                            step_col1, step_col2, step_col3, step_col4 = st.columns([2, 1, 2, 2])
                            
                            with step_col1:
                                st.write(f"🔹 **{step['name']}**")
                                st.caption(f"负责人: `{step['operator']}`")
                            
                            with step_col2:
                                status_colors = {"待处理": "⚪", "进行中": "🟡", "已完成": "🟢", "已阻塞": "🔴"}
                                st.write(f"{status_colors.get(step['status'], '')} {step['status']}")
                            
                            with step_col3:
                                status_options = ["待处理", "进行中", "已完成", "已阻塞"]
                                current_idx = status_options.index(step['status']) if step['status'] in status_options else 0
                                    
                                new_status = st.selectbox(
                                    "更新状态", 
                                    status_options, 
                                    index=current_idx, 
                                    key=f"step_{step['id']}"
                                )
                                if new_status != step['status']:
                                    update_res = requests.put(
                                        f"{BASE_URL}/steps/{step['id']}/status?status={new_status}", 
                                        headers=headers
                                    )
                                    if update_res.status_code == 200:
                                        st.toast(f"'{step['name']}' 状态已更新！")
                                        st.rerun()
                            
                            # 🛠️ 核心文件上传与下载组件
                            with step_col4:
                                if step["file_name"]:
                                    st.write(f"📂 `{step['file_name']}`")
                                    # 提供下载按钮
                                    download_url = f"{BASE_URL}/steps/{step['id']}/download"
                                    st.link_button("⬇️ 下载/查看文件", download_url)
                                else:
                                    # 如果没有文件，提供上传接口
                                    uploaded_file = st.file_uploader(
                                        "上传步骤文件", 
                                        key=f"file_{step['id']}", 
                                        label_visibility="collapsed"
                                    )
                                    if uploaded_file is not None:
                                        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                                        upload_res = requests.post(f"{BASE_URL}/steps/{step['id']}/upload", files=files)
                                        if upload_res.status_code == 200:
                                            st.success("文件上传成功！")
                                            st.rerun()
                                            
                            st.write("---")
        else:
            st.error("获取合同数据失败，请检查登录权限。")
    except Exception as e:
        st.error(f"加载数据时发生错误: {e}")

# ------------------------------------------
# Tab 2: 录入新合同
# ------------------------------------------
with tab2:
    st.subheader("📥 录入/导入新合同与流程骨架")
    
    with st.form("create_contract_form"):
        c_number = st.text_input("合同编号 (例如: HT-2026-002)")
        c_category = st.selectbox("合同类别", ["销售合同", "采购合同", "技术服务合同", "租赁合同", "其他"])
        c_payment = st.radio("初始付款状态", ["未付款", "已付款"], horizontal=True)
        w_name = st.text_input("流程模版名称 (例如: 交付流程)")
        
        st.write("---")
        st.write("🛠️ **配置该合同的操作步骤流程**")
        
        step_count = st.number_input("该流程包含的步骤总数", min_value=1, max_value=10, value=3)
        
        steps_data = []
        for i in range(int(step_count)):
            st.write(f"第 {i+1} 步：")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                s_name = st.text_input(f"步骤名称", key=f"in_sname_{i}", placeholder="如：合同审批/财务对账/商品发货")
            with col_s2:
                s_op = st.text_input(f"步骤负责人", key=f"in_sop_{i}", placeholder="如：alex")
            steps_data.append({"name": s_name, "operator": s_op})
            
        submit_btn = st.form_submit_button("🚀 提交并导入系统")
        
        if submit_btn:
            if not c_number or not w_name or any(not s["name"] or not s["operator"] for s in steps_data):
                st.error("请把所有合同信息和步骤填写完整后再提交！")
            else:
                payload = {
                    "contract_number": c_number,
                    "category": c_category,
                    "payment_status": c_payment,
                    "workflow_name": w_name,
                    "steps": steps_data
                }
                post_res = requests.post(f"{BASE_URL}/contracts/", json=payload, headers=headers)
                if post_res.status_code == 200:
                    st.success(f"🎉 合同 {c_number} 已成功创建！进度已重置为自动检测。")
