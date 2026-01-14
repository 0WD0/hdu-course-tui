import httpx
import shutil
import subprocess
import uuid
import json
import argparse
import sys
import os
import asyncio
import traceback
from downloader import DownloaderManager
from datetime import datetime, timedelta
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Static, ListView, ListItem, Label
from textual.binding import Binding
import webbrowser
from collections import defaultdict

# Endpoints
CURRICULUM_API_URL = (
    "https://course.hdu.edu.cn/jy-application-vod-he-hdu/v1/myself/curriculum"
)
DETAIL_API_URL = (
    "https://course.hdu.edu.cn/jy-application-vod-he-hdu/v1/course_vod_urls"
)


def load_config(config_path):
    """Load configuration from a JSON file."""
    if not os.path.exists(config_path):
        print(f"错误: 配置文件 '{config_path}' 不存在")
        print("请参考 config.json.example 创建配置文件")
        print("详细说明请查看 README.md")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        cookies = config.get("cookies", {})
        headers = config.get("headers", {})
        downloader = config.get("downloader", None)

        # New config for filtering angles: list of strings, e.g., ["Teacher", "PPT"]
        # Default is None, meaning download ALL angles.
        download_angles = config.get("download_angles", None)

        # Validate download_angles
        if download_angles is not None:
            if isinstance(download_angles, str):
                download_angles = [download_angles]
            elif not isinstance(download_angles, list):
                print("Warning: 'download_angles' must be a list of strings. Ignoring.")
                download_angles = None

        if not cookies:
            print(f"错误: 配置文件中缺少 'cookies' 字段")
            print("请在 config.json 中添加 cookies 配置")
            sys.exit(1)
        
        if not headers:
            print(f"警告: 配置文件中缺少 'headers' 字段")
            print("建议添加 headers 配置以提高兼容性")
        
        # Validate required cookies
        required_cookies = ["jy-application-vod-he", "route"]
        missing_cookies = [c for c in required_cookies if c not in cookies]
        if missing_cookies:
            print(f"错误: 缺少必需的 Cookie: {', '.join(missing_cookies)}")
            print(f"当前 cookies 包含: {', '.join(cookies.keys())}")
            print("\n请确保从浏览器的【请求标头】中复制了以下 Cookie:")
            for cookie_name in required_cookies:
                print(f"  - {cookie_name}")
            sys.exit(1)
        
        print(f"配置加载成功:")
        print(f"  - Cookies: {len(cookies)} 项 ({', '.join(cookies.keys())})")
        print(f"  - Headers: {len(headers)} 项")
        if downloader:
            print(f"  - 下载器: {downloader}")
        if download_angles:
            print(f"  - 视角过滤: {', '.join(download_angles)}")

        return cookies, headers, downloader, download_angles
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件 JSON 格式错误: {e}")
        print(f"请检查 {config_path} 的格式是否正确")
        print("提示: JSON 文件不支持注释，确保没有 // 或 /* */ 注释")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 加载配置文件失败: {type(e).__name__}: {e}")
        sys.exit(1)


class AngleSelectionModal(Screen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, video_list):
        super().__init__()
        self.video_list = video_list

    def compose(self) -> ComposeResult:
        angle_map = {0: "Teacher", 1: "Student", 2: "PPT"}
        yield Container(
            Label("Select Camera Angle:", id="modal-title"),
            ListView(
                *[
                    ListItem(
                        Label(
                            f"{v.get('viewName', f'Angle {i + 1}')} ({angle_map.get(i, 'Unknown')})"
                        ),
                        id=f"angle-{i}",
                    )
                    for i, v in enumerate(self.video_list)
                ],
                id="angle-list",
            ),
            id="modal-dialog",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not event.item or not event.item.id:
            return

        try:
            parts = event.item.id.split("-")
            if len(parts) > 1:
                index = int(parts[1])
                self.dismiss(self.video_list[index])
            else:
                self.dismiss(None)
        except (ValueError, IndexError):
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class CourseApp(App):
    CSS = """
    #main-container {
        height: 100%;
        layout: horizontal;
    }
    #sidebar {
        width: 30%;
        height: 100%;
        border-right: solid green;
        background: $surface;
    }
    #content {
        width: 70%;
        height: 100%;
    }
    #course-list {
        height: 100%;
    }
    DataTable {
        height: 100%;
        border: solid green;
    }
    #status_bar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
    }

    /* Modal Styling */
    AngleSelectionModal {
        align: center middle;
    }
    #modal-dialog {
        padding: 0 1;
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }
    #modal-title {
        content-align: center middle;
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh List"),
        ("v", "play_vlc", "Play in VLC"),
        ("d", "download", "Download Video"),
        ("b", "browser", "Open in Browser"),
        ("h", "focus_sidebar", "Focus Courses"),
        ("l", "focus_content", "Focus Recordings"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]

    def __init__(self, cookies, headers, downloader=None, download_angles=None):
        super().__init__()
        self.cookies = cookies
        self.headers = headers
        self.preferred_downloader = downloader
        self.download_angles = (
            download_angles  # List of allowed angles (Teacher, Student, PPT)
        )
        self.course_data = defaultdict(list)
        self.current_course_name = None
        self.course_id_map = {}
        self.current_video_list = []
        self.downloader_manager = DownloaderManager(preferred_downloader=downloader)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            with Vertical(id="sidebar"):
                yield Label("Courses", id="courses-header")
                yield ListView(id="course-list")
            with Vertical(id="content"):
                yield DataTable(cursor_type="row")
        yield Static("Ready", id="status_bar")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Time", "Classroom", "Teacher", "Play Count", "ID")
        await self.load_courses()

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle course highlight (cursor move) in the left sidebar."""
        if event.item is None:
            return

        safe_id = event.item.id
        if safe_id and safe_id in self.course_id_map:
            course_name = self.course_id_map[safe_id]
            # Update only if changed to avoid unnecessary redraws
            if self.current_course_name != course_name:
                self.current_course_name = course_name
                self.update_recordings_table(course_name)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle course selection (Enter) from the left sidebar."""
        # Ranger-style: Enter on a directory (course) moves focus into it (video list)
        self.query_one(DataTable).focus()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle recording selection (Enter key) from the right table."""
        course_id = event.row_key.value
        await self.load_video_urls(course_id, action="browser")

    async def action_play_vlc(self):
        """Play selected video in VLC."""
        if self.query_one(DataTable).cursor_row is not None:
            row_key = (
                self.query_one(DataTable)
                .coordinate_to_cell_key(self.query_one(DataTable).cursor_coordinate)
                .row_key.value
            )
            await self.load_video_urls(row_key, action="vlc")
        else:
            self.notify("No recording selected", severity="warning")

    async def action_download(self):
        """Download selected video or batch download depending on focus."""
        focused = self.focused

        # If Course List (sidebar) is focused, download ALL videos for that course
        if isinstance(focused, ListView) and self.current_course_name:
            await self.download_all_course_videos(self.current_course_name)

        # If Data Table (content) is focused, download just the selected video
        elif isinstance(focused, DataTable) and focused.cursor_row is not None:
            row_key = focused.coordinate_to_cell_key(
                focused.cursor_coordinate
            ).row_key.value
            await self.load_video_urls(row_key, action="download")
        else:
            self.notify("No selection to download", severity="warning")

    async def action_browser(self):
        """Open selected video in browser."""
        if self.query_one(DataTable).cursor_row is not None:
            row_key = (
                self.query_one(DataTable)
                .coordinate_to_cell_key(self.query_one(DataTable).cursor_coordinate)
                .row_key.value
            )
            await self.load_video_urls(row_key, action="browser")
        else:
            self.notify("No recording selected", severity="warning")

    async def fetch_video_url(self, course_id, batch_mode=False, file_prefix=""):
        """
        Helper to fetch video URL(s) for a given course ID.
        Returns a list of dictionaries: [{'url': url, 'filename': filename}, ...]
        """
        params = {"courseId": course_id}
        try:
            async with httpx.AsyncClient(
                cookies=self.cookies, headers=self.headers, verify=False, timeout=30.0
            ) as client:
                response = await client.get(DETAIL_API_URL, params=params)
                
                # Check HTTP status  
                if response.status_code != 200:
                    return []
                    
                data = response.json()
                video_list = data.get("data", {}).get("courseVodViewList", [])

                if not video_list:
                    return []

                results = []

                for i, v in enumerate(video_list):
                    url = v.get("url")
                    if not url:
                        continue

                    # Determine angle suffix
                    raw_view_name = v.get("viewName", "")

                    if "PPT" in raw_view_name or i == 2:
                        suffix = "PPT"
                    elif (
                        "学生" in raw_view_name or "Student" in raw_view_name or i == 1
                    ):
                        suffix = "Student"
                    elif (
                        "教师" in raw_view_name or "Teacher" in raw_view_name or i == 0
                    ):
                        suffix = "Teacher"
                    else:
                        suffix = f"Angle{i + 1}"

                    # Check if this angle is allowed by configuration
                    # Only apply filter in batch mode, or if user strictly wants to filter always (usually batch)
                    if batch_mode and self.download_angles:
                        # Case-insensitive check
                        if suffix.lower() not in [
                            a.lower() for a in self.download_angles
                        ]:
                            continue

                    filename = f"{file_prefix}_{suffix}.mp4"
                    results.append({"url": url, "filename": filename})

                return results

        except httpx.TimeoutException:
            self.notify(f"获取视频 {course_id} 超时", severity="warning")
            return []
        except httpx.ConnectError:
            self.notify(f"获取视频 {course_id} 连接失败", severity="warning")
            return []
        except Exception as e:
            self.notify(f"获取视频 {course_id} 失败: {str(e)}", severity="warning")
            return []

    async def download_all_course_videos(self, course_name):
        """Concurrent download of all videos (filtered by angles) for the current course."""
        recordings = self.course_data.get(course_name, [])
        if not recordings:
            self.notify("No recordings to download", severity="warning")
            return

        self.query_one("#status_bar", Static).update(
            f"Preparing batch download for {len(recordings)} recordings..."
        )

        tasks = []
        for rec in recordings:
            course_id = str(rec.get("id"))
            raw_time = rec.get("courBeginTime", "UnknownTime")
            safe_time = "".join([c if c.isalnum() else "_" for c in raw_time])
            tasks.append(
                self.fetch_video_url(course_id, batch_mode=True, file_prefix=safe_time)
            )

        results = await asyncio.gather(*tasks)

        all_downloads = []
        for item_list in results:
            if item_list:
                all_downloads.extend(item_list)

        if not all_downloads:
            self.notify("No videos found (check config angles?)", severity="warning")
            return

        safe_name = "".join([c if c.isalnum() else "_" for c in course_name])
        list_file = f"urls_{safe_name}.txt"

        with open(list_file, "w") as f:
            for item in all_downloads:
                url = item["url"]
                filename = item["filename"]
                f.write(f"{url}\n")
                f.write(f"  out={filename}\n")

        self.notify(f"Generated list ({len(all_downloads)} files): {list_file}")

        destination_dir = f"Downloads/{safe_name}"
        self.downloader_manager.download_batch(
            download_list_file=list_file,
            destination_dir=destination_dir,
            notify_callback=self.notify,
        )

    async def load_video_urls(self, course_id, action="browser"):
        """Fetch video URLs and perform action."""
        self.query_one("#status_bar", Static).update(
            f"Fetching video URLs for course {course_id}..."
        )
        params = {"courseId": course_id}

        try:
            async with httpx.AsyncClient(
                cookies=self.cookies, headers=self.headers, verify=False, timeout=30.0
            ) as client:
                response = await client.get(DETAIL_API_URL, params=params)
                
                # Check HTTP status
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    self.query_one("#status_bar", Static).update(f"Error: {error_msg}")
                    self.notify(
                        f"获取视频失败 (HTTP {response.status_code})\n请检查 Cookie 是否正确",
                        severity="error"
                    )
                    return
                
                data = response.json()

                video_list = data.get("data", {}).get("courseVodViewList", [])

                if not video_list:
                    self.notify(
                        "No videos available for this course", severity="warning"
                    )
                    return

                # Handle multiple angles or single video
                if len(video_list) > 1:
                    self.push_screen(
                        AngleSelectionModal(video_list),
                        lambda v: self.perform_video_action(v, action),
                    )
                else:
                    self.perform_video_action(video_list[0], action)

        except httpx.TimeoutException:
            error_msg = "请求超时"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(error_msg, severity="error")
        except httpx.ConnectError:
            error_msg = "无法连接到服务器"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(error_msg, severity="error")
        except json.JSONDecodeError as e:
            error_msg = f"API 返回数据格式错误"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(f"{error_msg}，Cookie 可能已过期", severity="error")
        except Exception as e:
            error_msg = f"Error: {type(e).__name__}: {str(e)}"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(error_msg, severity="error")

    def perform_video_action(self, target_video, action):
        """Execute the requested action on the selected video."""
        if not target_video:
            self.notify("Selection cancelled", severity="information")
            return

        video_url = target_video.get("url")
        if not video_url:
            self.notify("No URL found in video record", severity="warning")
            return

        if action == "browser":
            self.query_one("#status_bar", Static).update(
                f"Opening in browser: {video_url}"
            )
            webbrowser.open(video_url)
            self.notify("Opened in browser")

        elif action == "vlc":
            self.query_one("#status_bar", Static).update(f"Opening in VLC: {video_url}")
            if shutil.which("vlc"):
                subprocess.Popen(["vlc", video_url])
                self.notify("Launched VLC")
            else:
                self.notify("VLC not found on system path", severity="error")

        elif action == "download":
            self.query_one("#status_bar", Static).update(
                f"Starting download: {video_url}"
            )
            self.downloader_manager.download_video(
                video_url=video_url, notify_callback=self.notify
            )

    def update_recordings_table(self, course_name):
        """Update the right pane with recordings for the selected course."""
        table = self.query_one(DataTable)
        table.clear()

        recordings = self.course_data.get(course_name, [])
        recordings.sort(key=lambda x: x.get("courBeginTime", ""), reverse=True)

        for rec in recordings:
            teacher = (
                rec.get("teacNames", ["Unknown"])[0]
                if rec.get("teacNames")
                else "Unknown"
            )
            row_key = str(rec.get("id"))
            table.add_row(
                rec.get("courBeginTime", "Unknown"),
                rec.get("clroName", "Unknown"),
                teacher,
                str(rec.get("courPlayCount", 0)),
                row_key,
                key=row_key,
            )

        self.query_one("#status_bar", Static).update(
            f"Showing {len(recordings)} recordings for {course_name}"
        )

    async def load_courses(self):
        self.query_one("#status_bar", Static).update("Loading curriculum...")

        now = datetime.now()
        start_date = (now - timedelta(days=150)).strftime("%Y-%m-%d")
        end_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")

        params = {
            "beginTime": start_date,
            "endTime": end_date,
            "page.pageIndex": 1,
            "page.pageSize": 500,
        }

        try:
            async with httpx.AsyncClient(
                cookies=self.cookies, headers=self.headers, verify=False, timeout=30.0
            ) as client:
                response = await client.get(CURRICULUM_API_URL, params=params)
                
                # Check HTTP status
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    self.query_one("#status_bar", Static).update(f"Error: {error_msg}")
                    self.notify(
                        f"认证失败或网络错误 (HTTP {response.status_code})\n请检查 Cookie 是否正确或已过期",
                        severity="error",
                        timeout=10
                    )
                    return
                
                data = response.json()

                # Validate response structure
                if not isinstance(data, dict) or "data" not in data:
                    error_msg = f"API 返回格式错误: {str(data)[:100]}"
                    self.query_one("#status_bar", Static).update(error_msg)
                    self.notify(error_msg, severity="error")
                    return

                records = data.get("data", {}).get("records", [])
                
                if not records:
                    self.query_one("#status_bar", Static).update("未找到课程记录")
                    self.notify(
                        "未找到任何课程\n可能原因：\n1. Cookie 已过期，请重新获取\n2. 时间范围内没有课程\n3. 账号权限不足",
                        severity="warning",
                        timeout=10
                    )
                    return

                self.course_data.clear()
                self.course_id_map.clear()
                for record in records:
                    subj_name = record.get("subjName", "Unknown Course")
                    self.course_data[subj_name].append(record)

                list_view = self.query_one("#course-list", ListView)
                await list_view.clear()

                sorted_courses = sorted(self.course_data.keys())
                for index, course in enumerate(sorted_courses):
                    count = len(self.course_data[course])
                    safe_id = f"course-{uuid.uuid4().hex}"
                    self.course_id_map[safe_id] = course

                    list_view.append(ListItem(Label(f"{course} ({count})"), id=safe_id))

                self.query_one("#status_bar", Static).update(
                    f"Loaded {len(records)} recordings across {len(self.course_data)} courses."
                )

                if sorted_courses:
                    list_view.index = 0
                    first_item = list_view.children[0]
                    if first_item and first_item.id in self.course_id_map:
                        course_name = self.course_id_map[first_item.id]
                        self.current_course_name = course_name
                        self.update_recordings_table(course_name)

        except httpx.TimeoutException:
            error_msg = "请求超时，请检查网络连接"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(error_msg, severity="error", timeout=10)
        except httpx.ConnectError:
            error_msg = "无法连接到服务器，请检查网络或 VPN"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(error_msg, severity="error", timeout=10)
        except json.JSONDecodeError as e:
            error_msg = f"API 返回数据格式错误: {str(e)}"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(f"{error_msg}\n可能 Cookie 已过期", severity="error", timeout=10)
        except Exception as e:
            error_msg = f"加载课程失败: {type(e).__name__}: {str(e)}"
            self.query_one("#status_bar", Static).update(error_msg)
            self.notify(
                f"{error_msg}\n\n请检查：\n1. Cookie 是否正确\n2. 网络连接是否正常\n3. 是否需要使用 VPN",
                severity="error",
                timeout=15
            )

    async def action_refresh(self):
        await self.load_courses()

    def action_focus_sidebar(self):
        self.query_one("#course-list").focus()

    def action_focus_content(self):
        self.query_one(DataTable).focus()

    def action_cursor_down(self):
        focused = self.focused
        if isinstance(focused, ListView):
            focused.action_cursor_down()
        elif isinstance(focused, DataTable):
            focused.action_cursor_down()

    def action_cursor_up(self):
        focused = self.focused
        if isinstance(focused, ListView):
            focused.action_cursor_up()
        elif isinstance(focused, DataTable):
            focused.action_cursor_up()

    async def open_course_video(self, course_id):
        self.query_one("#status_bar", Static).update(
            f"Fetching video URL for course {course_id}..."
        )
        params = {"courseId": course_id}

        try:
            async with httpx.AsyncClient(
                cookies=self.cookies, headers=self.headers, verify=False
            ) as client:
                response = await client.get(DETAIL_API_URL, params=params)
                
                # Check HTTP status
                if response.status_code != 200:
                    self.notify(
                        f"获取视频失败 (HTTP {response.status_code})",
                        severity="error"
                    )
                    return
                    
                data = response.json()

                video_list = data.get("data", {}).get("courseVodViewList", [])
                if video_list:
                    video_url = video_list[0].get("url")
                    if video_url:
                        self.query_one("#status_bar", Static).update(
                            f"Opening video: {video_url}"
                        )
                        webbrowser.open(video_url)
                        self.notify(f"Opened video in browser")
                    else:
                        self.notify(
                            "No video URL found in response", severity="warning"
                        )
                else:
                    self.notify(
                        "No videos available for this course", severity="warning"
                    )

        except Exception as e:
            self.query_one("#status_bar", Static).update(f"Error fetching video: {e}")
            self.notify(f"Error: {e}", severity="error")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="HDU Course TUI")
        parser.add_argument(
            "--config",
            default="config.json",
            help="Path to configuration file (default: config.json)",
        )
        args = parser.parse_args()

        cookies, headers, downloader, download_angles = load_config(args.config)

        app = CourseApp(
            cookies=cookies,
            headers=headers,
            downloader=downloader,
            download_angles=download_angles,
        )
        app.run()
    except KeyboardInterrupt:
        print("\n程序已被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序异常退出:")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        print("\n请检查:")
        print("1. config.json 配置是否正确")
        print("2. Cookie 是否已过期（需要重新获取）")
        print("3. 网络连接是否正常")
        print("4. 如果使用 VPN，确保 VPN 已连接")
        print("\n详细错误信息:")
        traceback.print_exc()
        sys.exit(1)
