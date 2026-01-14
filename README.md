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

1.  在项目根目录创建一个 `config.json` 文件。
2.  用浏览器登录 [HDU 智慧教室平台](https://course.hdu.edu.cn/)。
3.  按 `F12` 打开开发者工具，点击“网络 (Network)”标签。
4.  刷新页面，找到任意一个 API 请求（如 `curriculum` 或 `course_vod_urls`）。
5.  复制请求头中的 `Cookie` 和必要的 `Headers`（如 `Authorization`, `User-Agent`）。
6.  参考下面的格式填入 `config.json`：

```json
{
    "cookies": {
        "JSESSIONID": "你的JSESSIONID...",
        "route": "..."
    },
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://course.hdu.edu.cn/?type=cas"
    },
    "downloader": "aria2c",
    "download_angles": ["Teacher", "PPT"],
    "start_date": "2024-09-01",
    "end_date": "2025-01-31"
}
```
> **提示**:
> *   `downloader`: 可选，支持 `"aria2c"`, `"fdm"`, `"wget"`。默认为自动检测。
> *   `download_angles`: 可选，用于批量下载时过滤视角。可选值：`"Teacher"`, `"Student"`, `"PPT"`。
> *   `start_date` / `end_date`: 可选，精确过滤课程日期范围 (YYYY-MM-DD)。
> *   如果不配置具体日期，默认抓取过去 150 天到未来 30 天的课程。
> *   `aria2_args`: 可选，自定义 aria2c 下载参数列表。默认为 `["-j", "16", "-x", "16", "-s", "16", "-k", "1M"]`。

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

## 🤖 关于开发

本项目是 **Vibe Coding** 产物，从零开始到功能完备（包括 TUI 界面、批量下载、多视角支持），初版耗时约 **2 小时**。

---
*Happy Coding & Learning!*
