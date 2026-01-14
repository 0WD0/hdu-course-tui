# HDU Course TUI (杭电课堂回放下载终端)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

专门为杭电 (HDU) 同学开发的**命令行课堂回放浏览与下载工具**。

告别繁琐的网页点击，在终端中优雅地浏览课程，支持**一键批量下载**某门课程的所有回放视频（包括教师、学生、PPT 全视角），并利用 **Aria2** 进行多线程高速下载。

---

## ✨ 功能特点

*   🖥 **极客范 TUI 界面**：基于 `Textual` 框架，支持鼠标点击与 Vim 风格快捷键 (`j`/`k` 上下移动)。
*   🚀 **批量高速下载**：
    *   自动抓取某门课本学期**所有**回放。
    *   **全视角支持**：自动下载 **Teacher (教师全景)**、**Student (学生全景)** 和 **PPT** 画面。
    *   **智能命名**：文件自动按 `时间_视角.mp4` 命名，不再覆盖冲突。
*   ⚡ **多下载器支持**：
    *   **Aria2c** (推荐): 多线程、断点续传、批量处理，速度极快。
    *   **FDM (Free Download Manager)**: 支持调用本地 FDM 客户端下载。
    *   **Wget / Curl**: 系统自带工具保底支持。
*   🎬 **多播放方式**：支持调用本地 `VLC` 播放器直接观看，或在浏览器中打开。

## 🛠️ 安装指南

### 1. 环境准备
你需要安装 Python 3.8 或以上版本。

推荐安装 **aria2** 以获得最佳下载体验：
*   **Ubuntu/Debian**: `sudo apt install aria2`
*   **MacOS**: `brew install aria2`
*   **Windows**: 下载 aria2 并在环境变量中配置。

### 2. 克隆与依赖安装
```bash
# 克隆仓库
git clone https://github.com/your-username/hdu-course-tui.git
cd hdu-course-tui

# 安装 Python 依赖
pip install httpx textual
```

### 3. 配置账号 (Config)

由于杭电统一认证系统的复杂性，本工具采用**手动抓取 Cookie** 的方式（最安全稳定）。

#### 详细配置步骤

##### 步骤 1: 创建配置文件
在项目根目录下，复制 `config.json.example` 为 `config.json`：
```bash
cp config.json.example config.json
```

##### 步骤 2: 登录并打开开发者工具
1. 使用浏览器（推荐 Chrome/Edge）访问 [HDU 智慧教室平台](https://course.hdu.edu.cn/)
2. 使用你的学号和密码完成登录
3. 登录成功后，按 `F12` 键打开浏览器开发者工具
4. 切换到 **"网络 (Network)"** 标签页

##### 步骤 3: 抓取 API 请求
1. 在开发者工具的网络标签页中，刷新页面 (`F5` 或点击刷新按钮)
2. 在网络请求列表中，找到以下任意一个 API 请求：
   - `curriculum` - 课程列表接口
   - `course_vod_urls` - 视频链接接口
   - 任何包含 `jy-application-vod-he-hdu` 路径的请求
3. 点击该请求，在右侧详情面板中选择 **"标头 (Headers)"** 选项卡

##### 步骤 4: 提取 Cookies
在请求标头中找到 **"Cookie"** 字段，你需要提取以下 Cookie 值：

| Cookie 名称 | 说明 | 是否必需 |
|------------|------|---------|
| `jy-application-vod-he` | 应用会话标识 | 必需 |
| `SESSION` | 用户会话 ID | 必需 |
| `route` | 路由信息 | 必需 |
| `cmbox` | 系统标识 | 可选 |
| `_webvpn_key` | VPN 密钥（如果通过 VPN 访问） | 可选 |
| `at_check` | 自动检测标记 | 可选 |

**提取方法**：
- 在 Cookie 字段中，每个 cookie 的格式为 `名称=值; `
- 例如：`jy-application-vod-he=abc123; SESSION=def456; route=xyz789`
- 将每个 cookie 的名称和值分别填入 `config.json` 的 `cookies` 对象中

##### 步骤 5: 提取 Headers
在同一个请求的标头中，还需要复制以下字段：

| Header 名称 | 说明 | 示例值 |
|------------|------|--------|
| `User-Agent` | 浏览器标识 | `Mozilla/5.0 (X11; Linux x86_64) ...` |
| `Accept` | 接受的内容类型 | `application/json, text/plain, */*` |
| `Referer` | 来源页面 | `https://course.hdu.edu.cn/?type=cas` |

##### 步骤 6: 填写配置文件
将提取的信息填入 `config.json`：

```json
{
    "cookies": {
        "jy-application-vod-he": "从浏览器复制的值",
        "SESSION": "从浏览器复制的值",
        "cmbox": "从浏览器复制的值",
        "route": "从浏览器复制的值",
        "_webvpn_key": "从浏览器复制的值（如果有）",
        "at_check": "true"
    },
    "headers": {
        "User-Agent": "从浏览器复制的 User-Agent",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://course.hdu.edu.cn/?type=cas"
    },
    "downloader": "aria2c",
    "download_angles": ["Teacher", "PPT"]
}
```

#### 配置参数详细说明

##### cookies 对象
包含用于身份验证的所有 Cookie 信息。这些 Cookie 会随着时间过期，如果程序提示"认证失败"或"无法获取课程列表"，请重新抓取。

##### headers 对象
HTTP 请求头信息，用于模拟浏览器请求：
- `User-Agent`: 浏览器标识字符串，建议使用你实际使用的浏览器的 User-Agent
- `Accept`: 告诉服务器客户端可以接受的内容类型
- `Referer`: 告诉服务器请求来自哪个页面

##### downloader 字段（可选）
指定下载工具，支持以下选项：

| 值 | 说明 | 特点 |
|----|------|------|
| `"aria2c"` | Aria2 命令行下载器 | **推荐**。支持多线程、断点续传、速度最快 |
| `"fdm"` | Free Download Manager | 图形界面下载管理器，适合 Windows 用户 |
| `"wget"` | Wget 命令行工具 | 系统自带，稳定但速度较慢 |
| `"curl"` | Curl 命令行工具 | 系统自带，基础下载功能 |
| 不填写 | 自动检测 | 程序会自动检测并选择最优工具（优先级：aria2c > fdm > wget > curl） |

**示例**：
```json
"downloader": "aria2c"
```

##### download_angles 字段（可选）
指定批量下载时要下载的视角，可以节省空间和时间。

| 值 | 说明 |
|----|------|
| `"Teacher"` | 教师全景视角（通常是教师讲课的画面） |
| `"Student"` | 学生全景视角（通常是教室整体画面） |
| `"PPT"` | PPT/屏幕分享视角（通常是 PPT 或教师屏幕内容） |

**使用方法**：
- 填写一个字符串数组，包含你想下载的视角
- 留空或不填写该字段，则下载所有可用视角

**示例**：
```json
// 只下载教师视角和 PPT
"download_angles": ["Teacher", "PPT"]

// 只下载 PPT
"download_angles": ["PPT"]

// 下载所有视角（默认行为）
// 方式1: 不写这个字段
// 方式2: 写成空数组或 null
"download_angles": null
```

> **⚠️ 重要提示**：
> - **不要分享你的 `config.json`**，其中包含你的登录凭证
> - Cookie 会过期，如果遇到认证问题，请重新抓取 Cookie
> - 如果使用 VPN 访问，确保抓取 Cookie 时和运行程序时都使用 VPN

## 📖 使用说明

运行工具：
```bash
python3 course_tui.py
```

### 快捷键
| 按键      | 功能                                                      |
|:----------|:----------------------------------------------------------|
| `j` / `k` | 上下移动光标                                              |
| `h`       | 焦点切换到左侧（课程列表）                                |
| `l`       | 焦点切换到右侧（视频列表）                                |
| `Enter`   | 选中课程 或 默认方式打开视频                              |
| `d`       | **下载** (左侧选中课程时批量下载全集；右侧选中时下载单集) |
| `v`       | 调用 VLC 播放器播放                                       |
| `b`       | 在浏览器中打开                                            |
| `q`       | 退出程序                                                  |

### 📥 关于批量下载
1.  按 `h` 切换到左侧课程列表。
2.  移动光标选中你要下载的课（如“ACM程序设计”）。
3.  按 `d` 键。
4.  程序会自动抓取该课程下所有的视频链接（包含不同视角），生成下载列表。
5.  自动调用 `aria2c` 开启 16 线程飞速下载到 `Downloads/课程名/` 目录下。

## ⚠️ 注意事项
*   **不要分享你的 `config.json`**，其中包含你的登录凭证。
*   本工具仅供学习交流使用，请勿用于非法用途或对学校服务器造成过大压力。



## 🔧 常见问题与解决方案

### 1. 程序提示"认证失败"或"无法获取课程列表"
**原因**：Cookie 已过期或无效。

**解决方案**：
- 重新登录 HDU 智慧教室平台
- 按照配置步骤重新抓取 Cookie
- 确保复制了所有必需的 Cookie 字段（`jy-application-vod-he`、`SESSION`、`route`）

### 2. 下载速度很慢
**原因**：使用的下载工具不支持多线程。

**解决方案**：
- 安装并配置 Aria2：`sudo apt install aria2`（Ubuntu/Debian）或 `brew install aria2`（MacOS）
- 在 `config.json` 中设置 `"downloader": "aria2c"`

### 3. 程序无法找到课程
**原因**：日期范围设置问题或 Cookie 权限不足。

**解决方案**：
- 检查你的账号是否有权限访问该课程
- 确保在浏览器中能够正常看到课程列表
- 重新抓取 Cookie

### 4. 下载的视频无法播放
**原因**：下载不完整或视频格式问题。

**解决方案**：
- 使用 Aria2 的断点续传功能重新下载
- 使用 VLC 播放器打开（支持更多格式）
- 检查下载的文件大小是否正常

### 5. 通过 VPN 访问时无法使用
**原因**：Cookie 是在 VPN 环境下获取的，但程序运行时未连接 VPN。

**解决方案**：
- 确保抓取 Cookie 和运行程序时都使用相同的网络环境
- 如果使用 VPN，需要在 Cookie 中包含 `_webvpn_key` 字段

### 6. 批量下载时只下载了部分视角
**原因**：`download_angles` 配置过滤了其他视角。

**解决方案**：
- 检查 `config.json` 中的 `download_angles` 设置
- 如果想下载所有视角，删除该字段或设置为 `null`

## 🤖 关于开发

本项目是 **Vibe Coding** 产物，从零开始到功能完备（包括 TUI 界面、批量下载、多视角支持），全程耗时约 **2 小时**。

---
*Happy Coding & Learning!*
