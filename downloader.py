import shutil
import subprocess
import os
import platform
from urllib.parse import urlparse


class DownloaderManager:
    def __init__(self, preferred_downloader=None, aria2_args=None):
        self.preferred_downloader = preferred_downloader
        self.aria2_args = aria2_args or ["-j", "16", "-x", "16", "-s", "16", "-k", "1M"]
        self.is_windows = platform.system() == "Windows"

        if self.is_windows:
            self.terminals = [
                ("wt", ["-d", ".", "cmd", "/c"]),
                ("cmd", ["/c", "start", "cmd", "/k"]),
            ]
        else:
            self.terminals = [
                ("gnome-terminal", ["--", "bash", "-c"]),
                ("kitty", ["-e", "bash", "-c"]),
                ("xterm", ["-e"]),
                ("konsole", ["-e", "bash", "-c"]),
                ("xfce4-terminal", ["-x", "bash", "-c"]),
                ("x-terminal-emulator", ["-e"]),
            ]

    def _launch_terminal_command(self, command, title="Download"):
        for term, args in self.terminals:
            if shutil.which(term):
                try:
                    if self.is_windows:
                        if term == "wt":
                            full_cmd = ["wt", "-d", ".", "cmd", "/k", command]
                        else:
                            full_cmd = ["cmd", "/c", "start", "cmd", "/k", command]
                    else:
                        full_args = [term] + args
                        final_cmd = f"{command}; echo 'Press Enter to exit'; read"
                        if term in ["xterm", "x-terminal-emulator"]:
                            full_cmd = [term, "-e", f"{command}; read"]
                        else:
                            full_cmd = list(full_args)
                            full_cmd.append(final_cmd)

                    subprocess.Popen(full_cmd)
                    return True, term
                except Exception:
                    continue

        return False, None

    def download_video(
        self,
        video_url,
        destination_dir=None,
        output_filename=None,
        notify_callback=None,
    ):
        def notify(msg, severity="information"):
            if notify_callback:
                notify_callback(msg, severity=severity)
            else:
                print(f"[{severity.upper()}] {msg}")

        if destination_dir:
            os.makedirs(destination_dir, exist_ok=True)

        output_path = None
        if output_filename:
            if destination_dir:
                output_path = os.path.join(destination_dir, output_filename)
            else:
                output_path = output_filename

        if self.preferred_downloader:
            preferred = self.preferred_downloader.lower()
            if preferred == "fdm":
                if shutil.which("fdm"):
                    subprocess.Popen(["fdm", "-d", video_url])
                    notify("Launched FDM (from config)")
                    return
                notify(
                    "FDM configured but not found, falling back...", severity="warning"
                )
            elif preferred in {"aria2c", "wget", "curl"}:
                if not shutil.which(preferred):
                    notify(
                        f"{preferred} configured but not found, falling back...",
                        severity="warning",
                    )
                else:
                    cli_tool = preferred
                    if preferred == "wget":
                        if output_path:
                            if self.is_windows:
                                cli_cmd = f'wget -O "{output_path}" "{video_url}"'
                            else:
                                cli_cmd = f"wget -O '{output_path}' '{video_url}'"
                        elif destination_dir:
                            if self.is_windows:
                                cli_cmd = f'wget -P "{destination_dir}" "{video_url}"'
                            else:
                                cli_cmd = f"wget -P '{destination_dir}' '{video_url}'"
                        else:
                            cli_cmd = (
                                f"wget '{video_url}'"
                                if not self.is_windows
                                else f'wget "{video_url}"'
                            )
                    elif preferred == "aria2c":
                        safety_args = ["--auto-file-renaming=false", "-c"]
                        final_args = safety_args + self.aria2_args
                        args_str = " ".join(final_args)
                        if output_filename:
                            if destination_dir:
                                if self.is_windows:
                                    cli_cmd = f'aria2c -d "{destination_dir}" -o "{output_filename}" "{video_url}" {args_str}'
                                else:
                                    cli_cmd = f"aria2c -d '{destination_dir}' -o '{output_filename}' '{video_url}' {args_str}"
                            else:
                                if self.is_windows:
                                    cli_cmd = f'aria2c -o "{output_filename}" "{video_url}" {args_str}'
                                else:
                                    cli_cmd = f"aria2c -o '{output_filename}' '{video_url}' {args_str}"
                        elif destination_dir:
                            if self.is_windows:
                                cli_cmd = f'aria2c -d "{destination_dir}" "{video_url}" {args_str}'
                            else:
                                cli_cmd = f"aria2c -d '{destination_dir}' '{video_url}' {args_str}"
                        else:
                            if self.is_windows:
                                cli_cmd = f'aria2c "{video_url}" {args_str}'
                            else:
                                cli_cmd = f"aria2c '{video_url}' {args_str}"
                    else:
                        if output_path:
                            if self.is_windows:
                                cli_cmd = f'curl -o "{output_path}" "{video_url}"'
                            else:
                                cli_cmd = f"curl -o '{output_path}' '{video_url}'"
                        elif destination_dir:
                            url_path = urlparse(video_url).path
                            filename = os.path.basename(url_path) or "downloaded_file"
                            output_path = os.path.join(destination_dir, filename)
                            if self.is_windows:
                                cli_cmd = f'curl -o "{output_path}" "{video_url}"'
                            else:
                                cli_cmd = f"curl -o '{output_path}' '{video_url}'"
                        else:
                            cli_cmd = (
                                f"curl -O '{video_url}'"
                                if not self.is_windows
                                else f'curl -O "{video_url}"'
                            )

                    success, term_used = self._launch_terminal_command(
                        cli_cmd, title=f"Download ({cli_tool})"
                    )
                    if success:
                        notify(f"Download started in {term_used}")
                        return

                    if preferred == "wget":
                        if output_path:
                            subprocess.Popen(["wget", "-O", output_path, video_url])
                        elif destination_dir:
                            subprocess.Popen(["wget", "-P", destination_dir, video_url])
                        else:
                            subprocess.Popen(["wget", video_url])
                        notify(
                            "Downloading in background (wget).", severity="information"
                        )
                        return
                    if preferred == "aria2c":
                        safety_args = ["--auto-file-renaming=false", "-c"]
                        final_args = safety_args + self.aria2_args
                        if output_filename:
                            if destination_dir:
                                subprocess.Popen(
                                    [
                                        "aria2c",
                                        "-d",
                                        destination_dir,
                                        "-o",
                                        output_filename,
                                        video_url,
                                    ]
                                    + final_args
                                )
                            else:
                                subprocess.Popen(
                                    ["aria2c", "-o", output_filename, video_url]
                                    + final_args
                                )
                        elif destination_dir:
                            subprocess.Popen(
                                ["aria2c", "-d", destination_dir, video_url]
                                + final_args
                            )
                        else:
                            subprocess.Popen(["aria2c", video_url] + final_args)
                        notify(
                            "Downloading in background (aria2c).",
                            severity="information",
                        )
                        return
                    if output_path:
                        subprocess.Popen(["curl", "-o", output_path, video_url])
                    else:
                        url_path = urlparse(video_url).path
                        filename = os.path.basename(url_path) or "downloaded_file"
                        output_path = os.path.join(
                            destination_dir or os.getcwd(), filename
                        )
                        subprocess.Popen(["curl", "-o", output_path, video_url])
                    notify("Downloading in background (curl).", severity="information")
                    return
            else:
                notify(
                    f"Unknown downloader configured: {self.preferred_downloader}",
                    severity="warning",
                )

        if self.preferred_downloader is None and shutil.which("fdm"):
            subprocess.Popen(["fdm", "-d", video_url])
            notify("Launched FDM")
            return

        # 3. Terminal Downloaders (Wget -> Aria2c -> Curl)
        # Try to launch in a new terminal window first

        # Determine the best CLI tool available
        cli_tool = None
        cli_cmd = None

        if shutil.which("wget"):
            cli_tool = "wget"
            if output_path:
                if self.is_windows:
                    cli_cmd = f'wget -O "{output_path}" "{video_url}"'
                else:
                    cli_cmd = f"wget -O '{output_path}' '{video_url}'"
            elif destination_dir:
                if self.is_windows:
                    cli_cmd = f'wget -P "{destination_dir}" "{video_url}"'
                else:
                    cli_cmd = f"wget -P '{destination_dir}' '{video_url}'"
            else:
                cli_cmd = (
                    f"wget '{video_url}'"
                    if not self.is_windows
                    else f'wget "{video_url}"'
                )
        elif shutil.which("aria2c"):
            cli_tool = "aria2c"
            safety_args = ["--auto-file-renaming=false", "-c"]
            final_args = safety_args + self.aria2_args
            args_str = " ".join(final_args)
            if output_filename:
                if destination_dir:
                    if self.is_windows:
                        cli_cmd = f'aria2c -d "{destination_dir}" -o "{output_filename}" "{video_url}" {args_str}'
                    else:
                        cli_cmd = f"aria2c -d '{destination_dir}' -o '{output_filename}' '{video_url}' {args_str}"
                else:
                    if self.is_windows:
                        cli_cmd = (
                            f'aria2c -o "{output_filename}" "{video_url}" {args_str}'
                        )
                    else:
                        cli_cmd = (
                            f"aria2c -o '{output_filename}' '{video_url}' {args_str}"
                        )
            elif destination_dir:
                if self.is_windows:
                    cli_cmd = f'aria2c -d "{destination_dir}" "{video_url}" {args_str}'
                else:
                    cli_cmd = f"aria2c -d '{destination_dir}' '{video_url}' {args_str}"
            else:
                if self.is_windows:
                    cli_cmd = f'aria2c "{video_url}" {args_str}'
                else:
                    cli_cmd = f"aria2c '{video_url}' {args_str}"
        elif shutil.which("curl"):
            cli_tool = "curl"
            if output_path:
                if self.is_windows:
                    cli_cmd = f'curl -o "{output_path}" "{video_url}"'
                else:
                    cli_cmd = f"curl -o '{output_path}' '{video_url}'"
            elif destination_dir:
                url_path = urlparse(video_url).path
                filename = os.path.basename(url_path) or "downloaded_file"
                output_path = os.path.join(destination_dir, filename)
                if self.is_windows:
                    cli_cmd = f'curl -o "{output_path}" "{video_url}"'
                else:
                    cli_cmd = f"curl -o '{output_path}' '{video_url}'"
            else:
                cli_cmd = (
                    f"curl -O '{video_url}'"
                    if not self.is_windows
                    else f'curl -O "{video_url}"'
                )

        if cli_tool:
            success, term_used = self._launch_terminal_command(
                cli_cmd, title=f"Download ({cli_tool})"
            )
            if success:
                notify(f"Download started in {term_used}")
                return
            else:
                notify(
                    "Terminal not found, attempting background download...",
                    severity="warning",
                )

        # 4. Background Fallback (if no terminal found or launch failed)
        if shutil.which("wget"):
            try:
                if output_path:
                    subprocess.Popen(["wget", "-O", output_path, video_url])
                    notify("Downloading in background (wget).", severity="information")
                elif destination_dir:
                    subprocess.Popen(["wget", "-P", destination_dir, video_url])
                    notify("Downloading in background (wget).", severity="information")
                else:
                    subprocess.Popen(["wget", video_url])
                    notify(
                        "Downloading in background (wget). Check working directory.",
                        severity="information",
                    )
            except Exception as e:
                notify(f"Background download failed: {e}", severity="error")
        elif shutil.which("aria2c"):
            try:
                safety_args = ["--auto-file-renaming=false", "-c"]
                final_args = safety_args + self.aria2_args
                if output_filename:
                    if destination_dir:
                        subprocess.Popen(
                            [
                                "aria2c",
                                "-d",
                                destination_dir,
                                "-o",
                                output_filename,
                                video_url,
                            ]
                            + final_args
                        )
                    else:
                        subprocess.Popen(
                            ["aria2c", "-o", output_filename, video_url] + final_args
                        )
                elif destination_dir:
                    subprocess.Popen(
                        ["aria2c", "-d", destination_dir, video_url] + final_args
                    )
                else:
                    subprocess.Popen(["aria2c", video_url] + final_args)
                notify("Downloading in background (aria2c).", severity="information")
            except Exception as e:
                notify(f"Background download failed: {e}", severity="error")
        elif shutil.which("curl"):
            try:
                if output_path:
                    subprocess.Popen(["curl", "-o", output_path, video_url])
                elif destination_dir:
                    url_path = urlparse(video_url).path
                    filename = os.path.basename(url_path) or "downloaded_file"
                    output_path = os.path.join(destination_dir, filename)
                    subprocess.Popen(["curl", "-o", output_path, video_url])
                else:
                    subprocess.Popen(["curl", "-O", video_url])
                notify("Downloading in background (curl).", severity="information")
            except Exception as e:
                notify(f"Background download failed: {e}", severity="error")
        else:
            notify(
                "No suitable downloader found (fdm, wget, aria2c, curl)",
                severity="error",
            )

    def download_batch(self, download_list_file, destination_dir, notify_callback=None):
        """
        Download a batch of files from a list.

        Args:
            download_list_file (str): Path to file containing URLs.
            destination_dir (str): Path to save downloads.
            notify_callback (func): Optional UI notifier.
        """

        def notify(msg, severity="information"):
            if notify_callback:
                notify_callback(msg, severity=severity)
            else:
                print(f"[{severity.upper()}] {msg}")

        # Ensure destination exists
        os.makedirs(destination_dir, exist_ok=True)
        abs_list_file = os.path.abspath(download_list_file)

        # 1. Aria2c (Best for batch)
        if shutil.which("aria2c"):
            safety_args = ["--auto-file-renaming=false", "-c"]
            final_args = safety_args + self.aria2_args

            args_str = " ".join(final_args)
            if self.is_windows:
                cmd = f'aria2c -i "{abs_list_file}" -d "{destination_dir}" {args_str}'
            else:
                cmd = f"aria2c -i '{abs_list_file}' -d '{destination_dir}' {args_str}"

            success, term = self._launch_terminal_command(
                cmd, title="Batch Download (aria2c)"
            )
            if success:
                notify(f"Batch download started in {term} (aria2c)")
            else:
                # Fallback background
                full_args = [
                    "aria2c",
                    "-i",
                    abs_list_file,
                    "-d",
                    destination_dir,
                ] + final_args
                subprocess.Popen(full_args)
                notify("Batch download started in background (aria2c)")
            return

        # 2. Wget
        if shutil.which("wget"):
            cmd = f"wget -i '{abs_list_file}' -P '{destination_dir}'"
            success, term = self._launch_terminal_command(
                cmd, title="Batch Download (wget)"
            )
            if success:
                notify(f"Batch download started in {term} (wget)")
            else:
                # Fallback background
                subprocess.Popen(["wget", "-i", abs_list_file, "-P", destination_dir])
                notify("Batch download started in background (wget)")
            return

        # 3. Curl
        if shutil.which("curl"):
            # Curl is tricky for batch list without xargs loop
            cmd = f"cd '{destination_dir}' && xargs -n 1 curl -O < '{abs_list_file}'"
            success, term = self._launch_terminal_command(
                cmd, title="Batch Download (curl)"
            )
            if success:
                notify(f"Batch download started in {term} (curl)")
            else:
                subprocess.Popen(["bash", "-c", cmd])
                notify("Batch download started in background (curl)")
            return

        notify(
            "No suitable batch downloader found (aria2c, wget, curl)", severity="error"
        )
