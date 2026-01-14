# HDU Course TUI

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
    *   **断点续传**：已下载的文件自动跳过，不会重复下载。
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
*   **Windows**: 下载 [aria2](https://github.com/aria2/aria2/releases) 并添加到环境变量，或使用 WSL。

### 2. 克隆与依赖安装
```bash
git clone https://github.com/0wd0/hdu-course-tui.git
cd hdu-course-tui
pip install -r requirements.txt
```

### 3. 配置账号 (获取 Cookie)
由于杭电统一认证系统的复杂性，本工具需要你提供登录后的凭证。

#### 🌟 方案 A：使用浏览器插件 (最简单)
1.  安装 **Cookie-Editor** 插件：[Chrome/Edge](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) | [Firefox](https://addons.mozilla.org/zh-CN/firefox/addon/cookie-editor/)
2.  登录 [HDU 智慧教室平台](https://course.hdu.edu.cn/)。
3.  点击插件图标，搜索 `jy`，找到 **`jy-application-vod-he`**，复制其 Value。

> ⚠️ 如果插件中**找不到**这个 Cookie，请使用下面的方案 B。

#### 🔧 方案 B：F12 开发者工具 (备选)
1.  登录 [HDU 智慧教室平台](https://course.hdu.edu.cn/)。
2.  按 `F12` 打开开发者工具，点击 **"网络 (Network)"** 标签。
3.  刷新页面，点击任意一个 API 请求（如 `curriculum`）。
4.  在 **"请求标头 (Request Headers)"** 中找到 `Cookie:` 字段，复制整个字符串。

### 4. 填写配置文件
在项目根目录创建 `config.json`。

**最简配置 (直接粘贴整个 Cookie 字符串)：**
```json
{
    "cookies": "jy-application-vod-he=xxx; route=xxx; ..."
}
```

**完整配置 (可选，用于自定义行为)：**
```json
{
    "cookies": "jy-application-vod-he=...",
    "download_angles": ["Teacher", "PPT"],
    "start_date": "2024-09-01",
    "end_date": "2025-01-31",
    "aria2_args": [
        "-j", "16",
        "-x", "16",
        "-s", "16",
        "-k", "1M"
    ]
}
```

<details>
<summary>📚 配置项说明 (点击展开)</summary>

| 配置项                    | 必填 | 说明                                                                          |
|---------------------------|------|-------------------------------------------------------------------------------|
| `cookies`                 | ✅   | 核心凭证。只需 `jy-application-vod-he` 即可。支持字符串或字典格式。           |
| `download_angles`         | ❌   | 批量下载时过滤视角。可选值：`"Teacher"`, `"Student"`, `"PPT"`。默认下载全部。 |
| `start_date` / `end_date` | ❌   | 过滤课程日期范围 (YYYY-MM-DD)。默认：过去 150 天到未来 30 天。                |
| `download_dir`            | ❌   | 下载目录。默认：`"Downloads"`。                                               |
| `downloader`              | ❌   | 指定下载器：`"aria2c"`, `"fdm"`, `"wget"`。默认自动检测。                     |
| `aria2_args`              | ❌   | 自定义 aria2c 参数。默认包含自动重试与断点续传。                          |

**aria2 参数说明（默认）**
- `--auto-file-renaming=false`: 文件存在时不自动改名（避免生成 .1.mp4）。
- `-c`: 断点续传；文件已完整时会跳过。
- `--max-tries=5`: 失败时最多重试 5 次。
- `-j 16`: 同时下载的文件数上限是 16，超过会排队依次下载。
- `-x 16`: 单个文件的最大连接数（每个服务器）。
- `-s 16`: 单个文件的分片数。
- `-k 1M`: 分片最小大小。

</details>

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
2.  移动光标选中你要下载的课（如"ACM程序设计"）。
3.  按 `d` 键。
4.  程序会自动抓取该课程下所有的视频链接（包含不同视角），生成下载列表。
5.  自动调用 `aria2c` 开启 16 线程飞速下载到 `Downloads/课程名/` 目录下。

## ❓ 常见问题 (FAQ)

<details>
<summary><b>Q: 提示 401 Unauthorized 或无法加载课程？</b></summary>

**A:** Cookie 已过期。请重新登录网站，按照上面的步骤重新获取 Cookie 并更新 `config.json`。
> 💡 Cookie 通常在 **24 小时** 左右过期，或者在你退出登录后失效。
</details>

<details>
<summary><b>Q: 下载速度很慢？</b></summary>

**A:** 确保你安装了 `aria2`。它支持多线程下载，速度比 wget/curl 快很多。
</details>

<details>
<summary><b>Q: Windows 上运行有问题？</b></summary>

**A:** 推荐使用 **WSL (Windows Subsystem for Linux)** 或 **Windows Terminal**。原生 CMD 可能存在编码问题。
</details>

## ⚠️ 注意事项
*   **不要分享你的 `config.json`**，其中包含你的登录凭证。
*   本工具仅供学习交流使用，请勿用于非法用途或对学校服务器造成过大压力。

## 🤖 关于开发

本项目是 **Vibe Coding** 产物，从零开始到功能完备（包括 TUI 界面、批量下载、多视角支持），初版耗时约 **2 小时**。

---
*Happy Coding & Learning!*
