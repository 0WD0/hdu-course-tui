import shutil
import subprocess
import os
import sys


class DownloaderManager:
    def __init__(self, preferred_downloader=None, aria2_args=None):
        self.preferred_downloader = preferred_downloader
        self.aria2_args = aria2_args or ["-j", "16", "-x", "16", "-s", "16", "-k", "1M"]
        self.terminals = [
            ("gnome-terminal", ["--", "bash", "-c"]),
            ("kitty", ["-e", "bash", "-c"]),
            ("xterm", ["-e"]),
            ("konsole", ["-e", "bash", "-c"]),
            ("xfce4-terminal", ["-x", "bash", "-c"]),
            ("x-terminal-emulator", ["-e"]),
        ]

    def _launch_terminal_command(self, command, title="Download"):
        """Helper to launch a terminal with the given command."""
        # Special handling for terminals that need slightly different arg structures
        # The self.terminals list contains (binary, [prefix_args...])

        for term, args in self.terminals:
            if shutil.which(term):
                try:
                    # Construct full command
                    # If the terminal expects a single string for the command (like bash -c "cmd; read")
                    # we need to be careful.

                    full_args = [term] + args

                    # Add the command to execute
                    # We append a 'read' to keep the terminal open
                    final_cmd = f"{command}; echo 'Press Enter to exit'; read"

                    # For xterm and x-terminal-emulator which often take -e cmd args...
                    if term in ["xterm", "x-terminal-emulator"]:
                        # simple -e cmd
                        full_cmd = [term, "-e", f"{command}; read"]
                    else:
                        # gnome-terminal, kitty, etc usually work well with bash -c "..."
                        full_cmd = list(full_args)
                        full_cmd.append(final_cmd)

                    subprocess.Popen(full_cmd)
                    return True, term
                except Exception:
                    continue

        return False, None

    def download_video(self, video_url, notify_callback=None):
        """
        Download a single video.

        Args:
            video_url (str): The URL to download.
            notify_callback (func): Optional function to send notifications back to UI.
                                    Signature: notify_callback(message, severity="information")
        """

        def notify(msg, severity="information"):
            if notify_callback:
                notify_callback(msg, severity=severity)
            else:
                print(f"[{severity.upper()}] {msg}")

        # 1. Preferred Downloader (Configured)
        if self.preferred_downloader == "fdm":
            if shutil.which("fdm"):
                subprocess.Popen(["fdm", "-d", video_url])
                notify("Launched FDM (from config)")
                return
            else:
                notify(
                    "FDM configured but not found, falling back...", severity="warning"
                )

        # 2. FDM (Default Preference if installed)
        if shutil.which("fdm"):
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
            cli_cmd = f"wget '{video_url}'"
        elif shutil.which("aria2c"):
            cli_tool = "aria2c"
            cli_cmd = f"aria2c '{video_url}'"
        elif shutil.which("curl"):
            cli_tool = "curl"
            cli_cmd = f"curl -O '{video_url}'"

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
                subprocess.Popen(["wget", video_url])
                notify(
                    "Downloading in background (wget). Check working directory.",
                    severity="information",
                )
            except Exception as e:
                notify(f"Background download failed: {e}", severity="error")
        elif shutil.which("aria2c"):
            try:
                subprocess.Popen(["aria2c", video_url])
                notify("Downloading in background (aria2c).", severity="information")
            except Exception as e:
                notify(f"Background download failed: {e}", severity="error")
        elif shutil.which("curl"):
            try:
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
