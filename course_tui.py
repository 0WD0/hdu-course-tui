import httpx
import shutil
import subprocess
import uuid
import json
import argparse
import sys
import os
import asyncio
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
        print(f"Error: Configuration file '{config_path}' not found.")
        print("Please create a JSON file with 'cookies' and 'headers' fields.")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        cookies = config.get("cookies", {})

        # Support raw cookie string (Simpler for users)
        if isinstance(cookies, str):
            cookie_dict = {}
            for item in cookies.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookie_dict[k.strip()] = v.strip()
            cookies = cookie_dict

        headers = config.get("headers", {})
        downloader = config.get("downloader", None)
        if isinstance(downloader, str) and downloader.lower() in {"aria2", "aria2c"}:
            downloader = "aria2c"

        # New config for filtering angles: list of strings, e.g., ["Teacher", "PPT"]
        # Default is None, meaning download ALL angles.
        download_angles = config.get("download_angles", None)

        # Configurable date range (explicit start/end or days back/forward)
        # Priority: start_date/end_date > days_back/days_forward
        start_date = config.get("start_date", None)
        end_date = config.get("end_date", None)

        # Fallback to days_back/days_forward if explicit dates not set
        now = datetime.now()
        if not start_date:
            days_back = config.get("days_back", 150)
            start_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")

        if not end_date:
            days_forward = config.get("days_forward", 30)
            end_date = (now + timedelta(days=days_forward)).strftime("%Y-%m-%d")

        # Configurable Aria2 arguments (list of strings)
        aria2_args = config.get("aria2_args", None)

        download_dir = os.path.expanduser(config.get("download_dir", "Downloads"))

        # Validate download_angles
        if download_angles is not None:
            if isinstance(download_angles, str):
                download_angles = [download_angles]
            elif not isinstance(download_angles, list):
                print("Warning: 'download_angles' must be a list of strings. Ignoring.")
                download_angles = None

        if not cookies or not headers:
            print(
                f"Warning: 'cookies' or 'headers' missing or empty in '{config_path}'."
            )

        return (
            cookies,
            headers,
            downloader,
            download_angles,
            start_date,
            end_date,
            aria2_args,
            download_dir,
        )
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON configuration: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}")
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

    def __init__(
        self,
        cookies,
        headers,
        downloader=None,
        download_angles=None,
        start_date=None,
        end_date=None,
        aria2_args=None,
        download_dir="Downloads",
    ):
        super().__init__()
        self.cookies = cookies
        self.headers = headers
        self.preferred_downloader = downloader
        self.download_angles = download_angles
        self.start_date = start_date
        self.end_date = end_date
        self.aria2_args = aria2_args
        self.download_dir = download_dir
        self.course_data = defaultdict(list)
        self.current_course_name = None
        self.course_id_map = {}
        self.current_video_list = []
        self.downloader_manager = DownloaderManager(
            preferred_downloader=downloader, aria2_args=aria2_args
        )

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

    def _angle_suffix(self, video_item):
        raw_view_name = video_item.get("viewName", "")
        angle_index = video_item.get("_angle_index")

        if "PPT" in raw_view_name or angle_index == 2:
            return "PPT"
        if "学生" in raw_view_name or "Student" in raw_view_name or angle_index == 1:
            return "Student"
        if "教师" in raw_view_name or "Teacher" in raw_view_name or angle_index == 0:
            return "Teacher"
        if isinstance(angle_index, int):
            return f"Angle{angle_index + 1}"
        return "Angle"

    async def fetch_video_url(self, course_id, batch_mode=False, file_prefix=""):
        params = {"courseId": course_id}
        try:
            async with httpx.AsyncClient(
                cookies=self.cookies, headers=self.headers, verify=False
            ) as client:
                response = await client.get(DETAIL_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
                video_list = data.get("data", {}).get("courseVodViewList", [])

                if not video_list:
                    return []

                results = []

                for i, v in enumerate(video_list):
                    url = v.get("url")
                    if not url:
                        continue

                    v["_angle_index"] = i
                    suffix = self._angle_suffix(v)

                    if batch_mode and self.download_angles:
                        if suffix.lower() not in [
                            a.lower() for a in self.download_angles
                        ]:
                            continue

                    filename = f"{file_prefix}_{suffix}.mp4"
                    results.append({"url": url, "filename": filename})

                return results

        except Exception:
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

        with open(list_file, "w", encoding="utf-8") as f:
            for item in all_downloads:
                url = item["url"]
                filename = item["filename"]
                f.write(f"{url}\n")
                f.write(f"  out={filename}\n")

        self.notify(f"Generated list ({len(all_downloads)} files): {list_file}")

        destination_dir = f"{self.download_dir}/{safe_name}"
        self.downloader_manager.download_batch(
            download_list_file=list_file,
            destination_dir=destination_dir,
            notify_callback=self.notify,
        )

    async def load_video_urls(self, course_id, action="browser"):
        self.query_one("#status_bar", Static).update(
            f"Fetching video URLs for course {course_id}..."
        )
        params = {"courseId": course_id}

        try:
            async with httpx.AsyncClient(
                cookies=self.cookies, headers=self.headers, verify=False
            ) as client:
                response = await client.get(DETAIL_API_URL, params=params)
                response.raise_for_status()
                data = response.json()

                video_list = data.get("data", {}).get("courseVodViewList", [])

                if not video_list:
                    self.notify(
                        "No videos available for this course", severity="warning"
                    )
                    return

                for i, v in enumerate(video_list):
                    v["_angle_index"] = i

                if len(video_list) > 1:
                    self.push_screen(
                        AngleSelectionModal(video_list),
                        lambda v: self.perform_video_action(v, action, course_id),
                    )
                else:
                    self.perform_video_action(video_list[0], action, course_id)

        except Exception as e:
            self.query_one("#status_bar", Static).update(f"Error fetching video: {e}")
            self.notify(f"Error: {e}", severity="error")

    def _record_by_id(self, course_id):
        if not self.current_course_name:
            return None
        recordings = self.course_data.get(self.current_course_name, [])
        for rec in recordings:
            if str(rec.get("id")) == str(course_id):
                return rec
        return None

    def perform_video_action(self, target_video, action, course_id=None):
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
            if self.current_course_name:
                safe_name = "".join(
                    [c if c.isalnum() else "_" for c in self.current_course_name]
                )
                destination_dir = os.path.join(self.download_dir, safe_name)
            else:
                destination_dir = self.download_dir

            output_filename = None
            if course_id is not None:
                record = self._record_by_id(course_id)
                if record:
                    raw_time = record.get("courBeginTime", "UnknownTime")
                    safe_time = "".join([c if c.isalnum() else "_" for c in raw_time])
                    suffix = self._angle_suffix(target_video)
                    output_filename = f"{safe_time}_{suffix}.mp4"

            self.downloader_manager.download_video(
                video_url=video_url,
                destination_dir=destination_dir,
                output_filename=output_filename,
                notify_callback=self.notify,
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

        start_date = self.start_date
        end_date = self.end_date

        # Fallback safeguard if somehow None (should be handled by load_config)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        try:
            all_records = []
            page_index = 1
            page_size = 500  # We use 500 to be safe, or 1000 if supported. User said 1000 is max.

            async with httpx.AsyncClient(
                cookies=self.cookies, headers=self.headers, verify=False
            ) as client:
                while True:
                    self.query_one("#status_bar", Static).update(
                        f"Loading curriculum (Page {page_index})..."
                    )

                    params = {
                        "page.pageIndex": page_index,
                        "page.pageSize": page_size,
                    }

                    response = await client.get(CURRICULUM_API_URL, params=params)
                    response.raise_for_status()
                    data = response.json()

                    new_records = data.get("data", {}).get("records", [])
                    if not new_records:
                        break

                    all_records.extend(new_records)

                    # If we got fewer records than requested, we've reached the last page
                    if len(new_records) < page_size:
                        break

                    page_index += 1

            # Client-side filtering to ensure strict date range adherence
            # (API might be loose or ignore params)
            filtered_records = []
            for record in all_records:
                # courBeginTime format is typically "YYYY-MM-DD HH:MM:SS"
                begin_time = record.get("courBeginTime", "")
                if not begin_time:
                    continue

                # Compare string prefixes (YYYY-MM-DD)
                # start_date/end_date are "YYYY-MM-DD"
                # We simply check if the date part is within range
                rec_date = begin_time.split(" ")[0]
                if start_date <= rec_date <= end_date:
                    filtered_records.append(record)

            self.course_data.clear()
            self.course_id_map.clear()
            for record in filtered_records:
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
                f"Loaded {len(filtered_records)} recordings (filtered from {len(all_records)}) across {len(self.course_data)} courses."
            )

            if sorted_courses:
                list_view.index = 0
                first_item = list_view.children[0]
                if first_item and first_item.id in self.course_id_map:
                    course_name = self.course_id_map[first_item.id]
                    self.current_course_name = course_name
                    self.update_recordings_table(course_name)

        except Exception as e:
            self.query_one("#status_bar", Static).update(f"Error: {e}")
            self.notify(f"Error loading courses: {e}", severity="error")

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
                response.raise_for_status()
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
    parser = argparse.ArgumentParser(description="HDU Course TUI")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )
    args = parser.parse_args()

    (
        cookies,
        headers,
        downloader,
        download_angles,
        start_date,
        end_date,
        aria2_args,
        download_dir,
    ) = load_config(args.config)

    app = CourseApp(
        cookies=cookies,
        headers=headers,
        downloader=downloader,
        download_angles=download_angles,
        start_date=start_date,
        end_date=end_date,
        aria2_args=aria2_args,
        download_dir=download_dir,
    )
    app.run()
