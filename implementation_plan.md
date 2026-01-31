# IBM watsonx Orchestrate SaaS 环境配置方案

> **项目**：GridKey BESS Optimizer (IBM Dev Day Hackathon)  
> **目标**：在新 repo 中从零配置 watsonx Orchestrate SaaS 环境，实现 Module E (WatsonX Agent Layer) 的开发

---

## 问题诊断

之前配置失败的可能原因：
1. **认证类型不匹配** - 使用了 `--type mcsp`，但 IBM Cloud 托管实例应使用 `ibm_iam`
2. **API Key 来源错误** - 可能使用了 IBM Cloud IAM API Key 而非 watsonx Orchestrate 专属 API Key
3. **环境冲突** - 已存在同名环境导致交互式确认

---

## 环境配置方案（两种路径）

### 路径 A：连接 SaaS 实例（推荐）

适用于：你有 watsonx Orchestrate SaaS 实例访问权限

### 路径 B：本地 Developer Edition

适用于：无法访问 SaaS 或网络问题，需要离线开发

---

## 路径 A：SaaS 实例配置

### 前置条件

| 条件 | 验证方式 |
|------|----------|
| Python 3.11/3.12/3.13 | `python --version` |
| pip 已安装 | `pip --version` |
| watsonx Orchestrate 实例访问权限 | 能登录 UI 界面 |

### 步骤 1：创建新项目目录

```bash
# 在你希望创建项目的位置
mkdir wtsx_hackkey
cd wtsx_hackkey
```

### 步骤 2：创建并激活虚拟环境

```bash
# 使用 Python 3.12（推荐）
python3.13 -m venv venv
source venv/bin/activate
```

### 步骤 3：安装 watsonx Orchestrate ADK

```bash
# 升级 pip
pip install --upgrade pip

# 安装 ADK
pip install ibm-watsonx-orchestrate
```

### 步骤 4：获取正确的凭据

> [!CAUTION]
> **这是最关键的一步** - 必须从 watsonx Orchestrate UI 获取凭据，而非 IBM Cloud 控制台

1. 登录你的 **watsonx Orchestrate 实例**（不是 IBM Cloud 控制台）
2. 点击右上角 **头像/Profile** → **Settings**
3. 进入 **API details** 标签页
4. **复制 Service instance URL** - 格式类似：
   - IBM Cloud: `https://api.{region}.watson-orchestrate.cloud.ibm.com/instances/{instance-id}`
   - AWS: `https://api.dl.watson-orchestrate.ibm.com/instances/{instance-id}`
5. 点击 **Generate API key** → **复制并安全保存**

### 步骤 5：确定认证类型

| URL 特征 | 认证类型 | 命令参数 |
|----------|----------|----------|
| `*.watson-orchestrate.cloud.ibm.com` | IBM Cloud IAM | `--type ibm_iam` 或 **不指定** |
| `*.watson-orchestrate.ibm.com` (非 cloud) | MCSP | `--type mcsp` |
| `*.watsonx.cpd.*.com` | CPD | `--type cpd` |

### 步骤 6：添加环境（清理旧环境后）

```bash
# 首先列出现有环境
orchestrate env list

# 如果存在同名环境，先删除
orchestrate env remove -n gridkey-env

# 添加新环境（根据你的 URL 类型选择）
# 选项 A：IBM Cloud 实例（推荐先不指定类型，让系统自动推断）
orchestrate env add \
  -n gridkey-env \
  -u "你的Service_Instance_URL" \
  --activate

# 选项 B：如果自动推断失败，明确指定 ibm_iam
orchestrate env add \
  -n gridkey-env \
  -u "你的Service_Instance_URL" \
  --type ibm_iam \
  --activate
```

当提示 `Please enter WXO API key:` 时，粘贴你从 UI 获取的 API Key

### 步骤 7：验证连接

```bash
# 验证环境激活
orchestrate env list

# 测试连接（查看可用 agents）
orchestrate agent list
```

---

## 路径 B：本地 Developer Edition（备选方案）

如果 SaaS 连接持续失败，可以考虑本地运行 Developer Edition。

### 系统要求

- 16GB RAM（启用 Document Processing 需 19GB）
- 8 CPU 核心
- 25GB 磁盘空间
- Docker Engine（推荐 Rancher Desktop 或 Colima）

### 配置步骤概述

1. 获取 **IBM Entitlement Key**：[https://myibm.ibm.com/products-services/containerlibrary](https://myibm.ibm.com/products-services/containerlibrary)
2. 创建 watsonx.ai Space 并关联 Runtime
3. 生成 watsonx API Key
4. 创建 `.env` 文件配置凭据
5. 运行 `orchestrate server start`

> [!NOTE]
> 此方案更复杂，建议优先尝试路径 A

---

## 项目集成方案

配置成功后，按照你的 `repo_structure_plan.md`，创建以下文件：

### `.env.template`（提交到 Git）

```bash
# watsonx Orchestrate 凭据
WXO_SERVICE_URL=
WXO_API_KEY=

# 外部 API 凭据
OPENWEATHER_API_KEY=
ENTSOE_API_KEY=

# 可选：watsonx.ai（如需直接调用 LLM）
WATSONX_AI_API_KEY=
WATSONX_AI_PROJECT_ID=
```

### `.env`（添加到 .gitignore，本地使用）

```bash
WXO_SERVICE_URL=https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/xxx
WXO_API_KEY=ApiKey-xxx-xxx
OPENWEATHER_API_KEY=xxx
ENTSOE_API_KEY=xxx
```

### `src/backend/agent/client.py` 骨架

```python
"""watsonx Orchestrate SDK 客户端封装"""
import os
from ibm_watsonx_orchestrate import OrchestrateClient

def get_client():
    """获取已认证的 Orchestrate 客户端"""
    return OrchestrateClient(
        url=os.getenv("WXO_SERVICE_URL"),
        api_key=os.getenv("WXO_API_KEY")
    )
```

---

## 故障排除清单

| 错误信息 | 可能原因 | 解决方案 |
|----------|----------|----------|
| `Error getting MCSP_V2 Token` | 认证类型不匹配 | 使用 `--type ibm_iam` 或不指定类型 |
| `Bad Request 400` | API Key 格式错误或来源错误 | 确保从 WXO UI 的 Settings → API details 生成 |
| `401 Unauthorized` | API Key 过期或无效 | 重新生成 API Key |
| `Would you like to update` 卡住 | 交互式提示未响应 | 先 `orchestrate env remove -n <name>` 再添加 |

---

## 验证清单

- [ ] 虚拟环境已创建并激活
- [ ] `ibm-watsonx-orchestrate` 已安装
- [ ] API Key 从 watsonx Orchestrate UI 获取（非 IBM Cloud IAM）
- [ ] Service Instance URL 已复制
- [ ] 认证类型与 URL 匹配
- [ ] `orchestrate env list` 显示已激活环境
- [ ] `orchestrate agent list` 成功返回

---

## 下一步

配置成功后：
1. 根据 `repo_structure_plan.md` 初始化项目结构
2. 创建 `src/backend/agent/tools.py` 定义 Agent 工具
3. 将 Weather/Price/Battery/Optimizer 服务注册为 Skills
4. 测试自然语言交互流程
