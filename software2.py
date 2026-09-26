import os
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import shutil

app = FastAPI()

# 创建上传文件保存的根目录
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

import os
import requests  # 引入请求库用来调用第三方 API
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler


# ... (保持你原来的数据模型、DB_CONTRACTS、DB_STEPS 和 update_contract_metrics 函数不变) ...

# ==================== 🤖 核心修改：第三方 API 对接逻辑 ====================

def fetch_third_party_status(contract_number: str, step_name: str) -> str:
    """
    模拟/真实请求第三方 API 接口 (例如快递物流、财务到账系统、OA审批系统)
    """
    # 💡 替换为你实际的第三方 API 地址和参数
    THIRD_PARTY_API_URL = "https://api.example.com/v1/status-check" 
    
    try:
        # 发送请求给第三方系统
        # response = requests.get(THIRD_PARTY_API_URL, params={"contract": contract_number, "step": step_name}, timeout=5)
        # if response.status_code == 200:
        #     data = response.json()
        #     return data.get("status") # 假设第三方返回 "已完成", "进行中" 等
        
        # ----------------------------------------------------
        # 模拟返回逻辑（实际对接时把这几行删掉，用上面注释的代码）
        # ----------------------------------------------------
        return "已完成" 
    except Exception as e:
        print(f"⚠️ 无法连接第三方 API: {e}")
        return None

def auto_check_third_party_job():
    """后台巡检任务：定期询问第三方 API，自动更新状态"""
    for step in DB_STEPS:
        # 只自动监控那些“未完成”的步骤
        if step["status"] not in ["已完成"]:
            contract = next((c for c in DB_CONTRACTS if c["id"] == step["contract_id"]), None)
            if not contract:
                continue

            # 1. 调用第三方 API 查询最新状态
            api_status = fetch_third_party_status(contract["contract_number"], step["name"])

            # 2. 如果第三方返回的状态和本地不一致，自动更新本地状态
            if api_status and api_status != step["status"]:
                step["status"] = api_status
                # 3. 重新计算该合同的总进度与阶段
                update_contract_metrics(step["contract_id"])
                print(f"🤖 [自动监控] 合同 {contract['contract_number']} - 步骤 '{step['name']}' 已被第三方 API 更新为【{api_status}】")

# ==================== 配置后台自动定时器 ====================
scheduler = BackgroundScheduler()
# 设置每 30 秒自动调用一次第三方 API 巡检（时间可自由调整，如 minutes=5）
scheduler.add_job(auto_check_third_party_job, 'interval', seconds=30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 后端启动时，自动开启监控
    scheduler.start()
    yield
    # 后端关闭时，自动停止监控
    scheduler.shutdown()

# 替换你原来的 app = FastAPI() 为这一行：
app = FastAPI(lifespan=lifespan)

# ... (保持你原来的 @app.get, @app.post 等 API 接口代码不变) ...


# ==================== 数据模型 ====================
class StepSchema(BaseModel):
    name: str
    operator: str

class ContractCreateSchema(BaseModel):
    contract_number: str
    category: str
    payment_status: str
    workflow_name: str
    steps: List[StepSchema]

# ==================== 模拟数据库 ====================
# 实际开发中会连接 SQLite/MySQL，这里用内存变量模拟
DB_CONTRACTS = []
DB_STEPS = []

# 为了测试方便，预置一些初始数据
if not DB_CONTRACTS:
    # 模拟一个默认合同
    contract_id = 1
    steps = [
        {"id": 1, "contract_id": contract_id, "name": "1. 方案审批", "operator": "alex", "status": "已完成", "file_path": None, "file_name": None},
        {"id": 2, "contract_id": contract_id, "name": "2. 财务对账", "operator": "alex", "status": "进行中", "file_path": None, "file_name": None},
        {"id": 3, "contract_id": contract_id, "name": "3. 商品发货", "operator": "bob", "status": "待处理", "file_path": None, "file_name": None},
    ]
    DB_STEPS.extend(steps)
    DB_CONTRACTS.append({
        "id": contract_id,
        "contract_number": "HT-2026-001",
        "category": "销售合同",
        "payment_status": "未付款",
        "workflow_name": "标准交付流",
        "stage": "进行中",
        "progress": "33%", # 自动计算
        "steps": steps
    })

# ==================== 辅助函数：自动检测和更新进度 ====================
def update_contract_metrics(contract_id: int):
    """自动检测合同步骤，重新计算进度(Progress)和阶段(Stage)"""
    contract = next((c for c in DB_CONTRACTS if c["id"] == contract_id), None)
    if not contract:
        return
    
    contract_steps = [s for s in DB_STEPS if s["contract_id"] == contract_id]
    total_steps = len(contract_steps)
    if total_steps == 0:
        contract["progress"] = "0%"
        contract["stage"] = "未开始"
        return
    
    completed_steps = sum(1 for s in contract_steps if s["status"] == "已完成")
    blocked_steps = sum(1 for s in contract_steps if s["status"] == "已阻塞")
    
    # 1. 自动计算进度百分比
    progress_val = int((completed_steps / total_steps) * 100)
    contract["progress"] = f"{progress_val}%"
    
    # 2. 自动检测和判定合同阶段
    if blocked_steps > 0:
        contract["stage"] = "遇到阻塞"
    elif completed_steps == total_steps:
        contract["stage"] = "全部完成"
    elif completed_steps > 0:
        contract["stage"] = "进行中"
    else:
        contract["stage"] = "未开始"

# ==================== API 接口 ====================

@app.get("/contracts/")
def get_contracts():
    # 组装最新数据返回
    for c in DB_CONTRACTS:
        c["steps"] = [s for s in DB_STEPS if s["contract_id"] == c["id"]]
    return DB_CONTRACTS

@app.post("/contracts/")
def create_contract(payload: ContractCreateSchema):
    new_contract_id = len(DB_CONTRACTS) + 1
    
    # 解析并保存步骤
    saved_steps = []
    for idx, step_data in enumerate(payload.steps):
        step_id = len(DB_STEPS) + 1
        step_dict = {
            "id": step_id,
            "contract_id": new_contract_id,
            "name": f"{idx+1}. {step_data.name}",
            "operator": step_data.operator,
            "status": "待处理",
            "file_path": None,
            "file_name": None
        }
        DB_STEPS.append(step_dict)
        saved_steps.append(step_dict)
    
    # 创建合同
    contract_dict = {
        "id": new_contract_id,
        "contract_number": payload.contract_number,
        "category": payload.category,
        "payment_status": payload.payment_status,
        "workflow_name": payload.workflow_name,
        "stage": "未开始",
        "progress": "0%",
        "steps": saved_steps
    }
    DB_CONTRACTS.append(contract_dict)
    update_contract_metrics(new_contract_id)
    return {"status": "success", "contract_id": new_contract_id}

@app.put("/steps/{step_id}/status")
def update_step_status(step_id: int, status: str):
    step = next((s for s in DB_STEPS if s["id"] == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="步骤不存在")
    step["status"] = status
    # 只要步骤状态变了，自动重新计算合同进度
    update_contract_metrics(step["contract_id"])
    return {"status": "success"}

@app.put("/contracts/{contract_id}/payment")
def update_payment(contract_id: int, payment_status: str):
    contract = next((c for c in DB_CONTRACTS if c["id"] == contract_id), None)
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    contract["payment_status"] = payment_status
    return {"status": "success"}

# ==================== 🛠️ 新增：文件上传接口 ====================
@app.post("/steps/{step_id}/upload")
async def upload_step_file(step_id: int, file: UploadFile = File(...)):
    step = next((s for s in DB_STEPS if s["id"] == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="步骤未找到")
    
    contract = next((c for c in DB_CONTRACTS if c["id"] == step["contract_id"]), None)
    contract_num = contract["contract_number"] if contract else "unknown"
    
    # 建立对应合同的文件目录：uploaded_files/HT-2026-001/
    contract_dir = os.path.join(UPLOAD_DIR, contract_num)
    os.makedirs(contract_dir, exist_ok=True)
    
    # 保存文件到本地
    file_path = os.path.join(contract_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 将路径保存至模拟数据库
    step["file_path"] = file_path
    step["file_name"] = file.filename
    
    return {"status": "success", "file_name": file.filename}

# ==================== 🛠️ 新增：文件下载接口 ====================
@app.get("/steps/{step_id}/download")
def download_step_file(step_id: int):
    step = next((s for s in DB_STEPS if s["id"] == step_id), None)
    if not step or not step["file_path"]:
        raise HTTPException(status_code=404, detail="该步骤未上传任何文件")
    
    if os.path.exists(step["file_path"]):
        return FileResponse(path=step["file_path"], filename=step["file_name"])
    raise HTTPException(status_code=404, detail="本地文件丢失")

from fastapi.security import OAuth2PasswordRequestForm

# 模拟的用户数据库
USER_DB = {
    "boss": "boss123",
    "alex": "alex123"
}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username
    password = form_data.password
    
    if username in USER_DB and USER_DB[username] == password:
        # 登录成功，返回一个模拟的 token
        return {"access_token": f"token-{username}", "token_type": "bearer"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="用户名或密码错误"
    )