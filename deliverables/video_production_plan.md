# GridKey Demo Video Production Plan

**时长**: 2-3 分钟 | **语言**: 英文 (可选中文字幕)

---

## 🎬 视频结构

| 时间段 | 内容 | 屏幕显示 |
|--------|------|----------|
| 0:00-0:20 | 开场介绍 | 标题动画 + Problem |
| 0:20-0:40 | 解决方案概述 | 架构图 |
| 0:40-2:20 | **WatsonX 实机演示** | 屏幕录制 |
| 2:20-2:40 | 总结 & Call to Action | 结束画面 |

---

## 📝 详细脚本

### Part 1: 开场 (0:00 - 0:20) 🎤

**画面**: 黑色背景 + GridKey Logo 动画

**旁白**:
> "Hey everyone! So here's the problem — if you're running a battery storage system, you've got to juggle a lot: weather forecasts, electricity prices, different markets... it's a lot to handle.
> 
> That's why we built **GridKey** — it's an AI assistant powered by IBM WatsonX Orchestrate that does all of this for you."

---

### Part 2: 解决方案概述 (0:20 - 0:40) 📊

**画面**: 简化架构图动画

```
User Question → WatsonX Agent → [Weather API] [Price API] [Optimizer] → Answer
```

**旁白**:
> "So how does it work? Pretty simple actually. You just ask a question in plain English, and behind the scenes, our agent calls different APIs — weather, prices, and our optimization engine — and puts it all together for you.
> 
> Let me show you what I mean."

---

### Part 3: WatsonX 实机演示 (0:40 - 2:20) 💻

#### Demo 1: 天气查询 (0:40 - 1:00)

**操作**: 在 WatsonX Orchestrate 对话框输入

```
What's the weather and expected solar generation in Munich tomorrow?
```

**旁白**:
> "Alright, let's start with something simple. I'm going to ask about tomorrow's weather in Munich.
> 
> And there we go — it's pulling real-time data from OpenWeatherMap and calculating how much solar power we can expect."

**等待响应** → 展示结果 (PV generation, temperature, cloud cover)

---

#### Demo 2: 电价查询 (1:00 - 1:20)

**操作**: 输入

```
Get current electricity prices for Germany
```

**旁白**:
> "Now let's check the electricity prices. We're getting data from four different markets — Day-Ahead, FCR, and aFRR.
> 
> As you can see, prices vary a lot throughout the day — and that's where the opportunity is."

**等待响应** → 展示价格数据

---

#### Demo 3: 核心优化 (1:20 - 2:00) ⭐ **重点**

**操作**: 输入

```
Optimize my battery schedule for tomorrow considering solar generation in Munich
```

**旁白**:
> "Okay, here's the cool part. With just one question, I'm asking the agent to figure out the best battery schedule for tomorrow.
> 
> Watch what happens — it's calling the weather API, getting prices, running our MILP optimizer... and boom! It tells me exactly when to charge, when to discharge, and how much money I can make.
> 
> Pretty neat, right?"

**展示响应** → 高亮关键信息:
- 充电时间窗口
- 放电时间窗口
- 预期收益

---

#### Demo 4: 追问 (2:00 - 2:20)

**操作**: 输入

```
What if I use a more aggressive C-rate?
```

**旁白**:
> "And because the agent remembers our conversation, I can ask follow-up questions. Like, what if I push the battery harder with a higher C-rate?
> 
> It re-runs the optimization and compares the results. Super useful for exploring different strategies."

**展示对比结果**

---

### Part 4: 总结 (2:20 - 2:40) 🎯

**画面**: 回到 GridKey Logo + 关键数据

**旁白**:
> "So that's GridKey — we're turning complicated optimization math into a simple conversation.
> 
> All built on IBM WatsonX Orchestrate, with real APIs and real market data.
> 
> Thanks for watching!"

**结束画面**:
```
GridKey - AI-Powered Battery Optimization
IBM WatsonX Orchestrate Hackathon 2026
```

---

## 🎥 录制准备清单

### 技术准备
- [ ] 确保 ngrok 隧道运行中
- [ ] 确保 FastAPI 服务器运行中
- [ ] 测试所有 API 端点正常
- [ ] WatsonX Agent 配置完成 (Quick Prompts 删除或更新)

### 录屏设置
- [ ] 分辨率: 1920x1080
- [ ] 隐藏浏览器书签栏
- [ ] 全屏 WatsonX Orchestrate 界面
- [ ] 关闭通知

### 工具推荐
| 用途 | 工具 |
|------|------|
| 屏幕录制 | OBS / QuickTime (Mac) / Loom |
| 视频剪辑 | iMovie / DaVinci Resolve (免费) |
| 旁白录制 | QuickTime / Audacity |
| 动画/标题 | Canva / Kapwing |

---

## ⚠️ 风险预案

| 问题 | 解决方案 |
|------|----------|
| API 响应慢 | 剪辑时加速或预先录制多次 |
| 错误响应 | 多录几次取最佳 |
| ngrok 断开 | 录制前确认稳定连接 |

---

## 📋 Demo 输入文本 (直接复制)

```
1️⃣ What's the weather and expected solar generation in Munich tomorrow?

2️⃣ Get current electricity prices for Germany

3️⃣ Optimize my battery schedule for tomorrow considering solar generation in Munich

4️⃣ What if I use a more aggressive C-rate?
```
