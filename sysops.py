#!/usr/bin/env python3
"""
Python SysOps CLI Tool (Course Final Project)
Combines Task Automation, System Monitoring, Web API integration, and CLI tooling.
"""

import os
import sys
import time
import zipfile
import fnmatch
import argparse
import json
from datetime import datetime, timedelta

# Try importing external dependencies and show helpful messages if missing
try:
    import psutil
except ImportError:
    print("Error: The 'psutil' package is required. Run 'pip install -r requirements.txt'")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: The 'requests' package is required. Run 'pip install -r requirements.txt'")
    sys.exit(1)

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    # Minimal fallback class if colorama is not present
    class DummyColor:
        def __getattr__(self, name):
            return ""
    Fore = DummyColor()
    Style = DummyColor()


class APIConnector:
    """Handles communication with external Web APIs and Webhook services."""
    
    @staticmethod
    def get_public_ip_info():
        """Fetches public IP address and geolocation info using a public API."""
        url = "https://ipapi.co/json/"
        try:
            # Setting a reasonable timeout to prevent hanging
            response = requests.get(url, timeout=5, headers={"User-Agent": "SysOps-CLI/1.0"})
            if response.status_code == 200:
                data = response.json()
                return {
                    "ip": data.get("ip", "N/A"),
                    "city": data.get("city", "N/A"),
                    "region": data.get("region", "N/A"),
                    "country": data.get("country_name", "N/A"),
                    "org": data.get("org", "N/A")
                }
        except Exception:
            pass
        return {"ip": "Unknown (Offline)", "city": "N/A", "region": "N/A", "country": "N/A", "org": "N/A"}

    @staticmethod
    def send_webhook(webhook_url, title, message, color_hex="3498db", fields=None):
        """
        Sends an alert or status update to a Discord/Slack or generic Webhook.
        If a standard URL is used, it POSTs standard JSON.
        """
        if not webhook_url:
            return False

        # Support Discord webhook format natively if URL contains discordapp.com or discord.com
        is_discord = "discord.com" in webhook_url or "discordapp.com" in webhook_url
        
        payload = {}
        if is_discord:
            embed = {
                "title": title,
                "description": message,
                "color": int(color_hex, 16),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            if fields:
                embed["fields"] = [{"name": k, "value": str(v), "inline": True} for k, v in fields.items()]
            payload = {"embeds": [embed]}
        else:
            # Generic webhook payload format
            payload = {
                "event": title,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "details": fields or {}
            }

        try:
            response = requests.post(webhook_url, json=payload, timeout=5)
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"{Fore.RED}Failed to send webhook notification: {e}")
            return False


class TaskAutomator:
    """Automates administrative operations like backups and cleaning logs."""
    
    @staticmethod
    def backup(src_dir, dest_dir, keep=5, webhook_url=None):
        """
        Creates a zip backup of the src_dir, places it in dest_dir,
        and retains only the most recent 'keep' backups.
        """
        print(f"\n{Fore.CYAN}--- Executing Automated Backup ---")
        
        if not os.path.exists(src_dir):
            print(f"{Fore.RED}Error: Source directory '{src_dir}' does not exist.")
            return False
            
        os.makedirs(dest_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        src_name = os.path.basename(os.path.abspath(src_dir)) or "backup"
        zip_filename = f"backup_{src_name}_{timestamp}.zip"
        zip_filepath = os.path.join(dest_dir, zip_filename)
        
        print(f"Compressing {Fore.YELLOW}{src_dir}{Style.RESET_ALL} to {Fore.YELLOW}{zip_filepath}{Style.RESET_ALL}...")
        
        try:
            start_time = time.time()
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(src_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        # Store relative path inside the zip file
                        rel_path = os.path.relpath(full_path, src_dir)
                        zipf.write(full_path, rel_path)
            
            elapsed = time.time() - start_time
            file_size_mb = os.path.getsize(zip_filepath) / (1024 * 1024)
            print(f"{Fore.GREEN}Backup created successfully: {zip_filename} ({file_size_mb:.2f} MB) in {elapsed:.2f}s")
            
            # Rotate backups
            TaskAutomator._rotate_backups(dest_dir, src_name, keep)
            
            # Send Notification
            if webhook_url:
                fields = {
                    "Source Directory": src_dir,
                    "Backup File": zip_filename,
                    "Size": f"{file_size_mb:.2f} MB",
                    "Duration": f"{elapsed:.2f}s"
                }
                APIConnector.send_webhook(
                    webhook_url, 
                    "Backup Complete", 
                    f"Successfully backed up '{src_name}' directory.",
                    color_hex="2ecc71",
                    fields=fields
                )
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Backup failed: {e}")
            if webhook_url:
                APIConnector.send_webhook(
                    webhook_url,
                    "Backup FAILED",
                    f"Failed to create backup for '{src_name}': {e}",
                    color_hex="e74c3c"
                )
            return False

    @staticmethod
    def _rotate_backups(dest_dir, src_name, keep):
        """Deletes older backups in dest_dir to maintain only the 'keep' newest files."""
        pattern = f"backup_{src_name}_*.zip"
        files = [
            os.path.join(dest_dir, f) for f in os.listdir(dest_dir) 
            if fnmatch.fnmatch(f, pattern) and os.path.isfile(os.path.join(dest_dir, f))
        ]
        
        # Sort by modification time ascending (oldest first)
        files.sort(key=os.path.getmtime)
        
        if len(files) > keep:
            to_delete = files[:-keep]
            print(f"Rotating backups: keeping last {keep}. Deleting {len(to_delete)} old backup(s)...")
            for filepath in to_delete:
                try:
                    os.remove(filepath)
                    print(f" - Deleted: {os.path.basename(filepath)}")
                except Exception as e:
                    print(f"{Fore.RED} - Error deleting {filepath}: {e}")

    @staticmethod
    def clean(directory, pattern="*.log", age_days=7):
        """
        Deletes files matching 'pattern' in 'directory' if they are
        older than 'age_days'.
        """
        print(f"\n{Fore.CYAN}--- Executing Directory Cleanup ---")
        if not os.path.exists(directory):
            print(f"{Fore.RED}Error: Target directory '{directory}' does not exist.")
            return False
            
        now = datetime.now()
        threshold = now - timedelta(days=age_days)
        deleted_count = 0
        freed_bytes = 0
        
        print(f"Scanning {Fore.YELLOW}{directory}{Style.RESET_ALL} for files matching {Fore.YELLOW}'{pattern}'{Style.RESET_ALL} older than {age_days} days...")
        
        for root, _, files in os.walk(directory):
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    filepath = os.path.join(root, file)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if mtime < threshold:
                            size = os.path.getsize(filepath)
                            os.remove(filepath)
                            deleted_count += 1
                            freed_bytes += size
                            print(f" - Deleted: {os.path.relpath(filepath, directory)} (Last modified: {mtime.strftime('%Y-%m-%d')})")
                    except Exception as e:
                        print(f"{Fore.RED} - Error checking/deleting {file}: {e}")
                        
        freed_mb = freed_bytes / (1024 * 1024)
        print(f"{Fore.GREEN}Cleanup completed. Removed {deleted_count} file(s). Freed {freed_mb:.2f} MB of space.")
        return True


class SystemMonitor:
    """Gathers, displays, and logs system metrics. Triggers alerts on breaches."""
    
    def __init__(self, metrics_file="metrics_log.json"):
        self.metrics_file = metrics_file
        # Throttle webhook notifications to prevent spam (max once every 5 minutes per metric)
        self.last_alert_times = {"cpu": 0, "memory": 0, "disk": 0}

    def gather_metrics(self):
        """Collects current system resource usages."""
        net_before = psutil.net_io_counters()
        time.sleep(0.5)  # Quick interval to calculate CPU usage & network delta
        cpu_percent = psutil.cpu_percent(interval=None)
        net_after = psutil.net_io_counters()
        
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        bytes_sent_sec = (net_after.bytes_sent - net_before.bytes_sent) * 2
        bytes_recv_sec = (net_after.bytes_recv - net_before.bytes_recv) * 2
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu_percent,
            "memory_percent": mem.percent,
            "memory_used_gb": mem.used / (1024**3),
            "memory_total_gb": mem.total / (1024**3),
            "disk_percent": disk.percent,
            "disk_used_gb": disk.used / (1024**3),
            "disk_total_gb": disk.total / (1024**3),
            "net_sent_kb_s": bytes_sent_sec / 1024,
            "net_recv_kb_s": bytes_recv_sec / 1024
        }

    def log_metrics(self, metrics):
        """Appends metrics to a local JSON file for history tracking."""
        data = []
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
            except Exception:
                data = []
                
        data.append(metrics)
        
        # Limit history log to the last 100 entries to save disk space
        if len(data) > 100:
            data = data[-100:]
            
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"{Fore.RED}Could not write metrics to log file: {e}")

    def render_dashboard(self, metrics, ip_info):
        """Renders a beautiful visual dashboard in the console."""
        # Clean terminal screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(f"{Fore.BLUE}{Style.BRIGHT}====================================================")
        print(f"            SYSTEM OPS MONITOR DASHBOARD            ")
        print(f"{Fore.BLUE}{Style.BRIGHT}====================================================")
        print(f"Time: {Fore.YELLOW}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Public IP: {Fore.GREEN}{ip_info['ip']} {Style.DIM}({ip_info['city']}, {ip_info['country']})")
        print(f"Network ISP: {Fore.CYAN}{ip_info['org']}")
        print(f"{Fore.BLUE}----------------------------------------------------")
        
        # Progress Bar Generator helper
        def make_bar(pct, color):
            filled = int(pct / 5)
            bar = "#" * filled + "-" * (20 - filled)
            return f"{color}[{bar}] {pct:.1f}%{Style.RESET_ALL}"

        # Select color based on percentage
        def get_color(pct):
            if pct > 85:
                return Fore.RED
            elif pct > 70:
                return Fore.YELLOW
            return Fore.GREEN

        print(f"CPU Usage:    {make_bar(metrics['cpu_percent'], get_color(metrics['cpu_percent']))}")
        print(f"Memory Usage: {make_bar(metrics['memory_percent'], get_color(metrics['memory_percent']))} "
              f"({metrics['memory_used_gb']:.1f}/{metrics['memory_total_gb']:.1f} GB)")
        print(f"Disk Usage:   {make_bar(metrics['disk_percent'], get_color(metrics['disk_percent']))} "
              f"({metrics['disk_used_gb']:.1f}/{metrics['disk_total_gb']:.1f} GB)")
        
        print(f"{Fore.BLUE}----------------------------------------------------")
        print(f"Network I/O:  {Fore.YELLOW}TX Upload: {metrics['net_sent_kb_s']:.1f} KB/s  "
              f"{Fore.CYAN}RX Download: {metrics['net_recv_kb_s']:.1f} KB/s")
        print(f"{Fore.BLUE}====================================================")
        print("Press Ctrl+C to terminate the monitor loop.")

    def check_alerts(self, metrics, webhook_url, cpu_limit, mem_limit, disk_limit):
        """Evaluates metrics against alert rules and dispatches Webhooks if needed."""
        if not webhook_url:
            return

        now = time.time()
        cooldown = 300  # 5 minutes in seconds

        # Helper to send alert
        def trigger_alert(metric_key, current_val, limit_val, metric_name):
            if current_val >= limit_val:
                if now - self.last_alert_times[metric_key] > cooldown:
                    self.last_alert_times[metric_key] = now
                    alert_title = f"[ALERT] SYSTEM ALERT: High {metric_name} Usage"
                    alert_msg = (f"The system has breached the configured threshold.\n"
                                 f"Current {metric_name}: {current_val:.1f}%\n"
                                 f"Threshold: {limit_val:.1f}%")
                    print(f"\n{Fore.RED}!!! BREACH DETECTED: Sending {metric_name} Webhook Alert !!!")
                    APIConnector.send_webhook(
                        webhook_url, 
                        alert_title, 
                        alert_msg, 
                        color_hex="e74c3c", 
                        fields={
                            "Metric": metric_name, 
                            "Current Value": f"{current_val:.1f}%", 
                            "Threshold": f"{limit_val:.1f}%"
                        }
                    )

        trigger_alert("cpu", metrics["cpu_percent"], cpu_limit, "CPU")
        trigger_alert("memory", metrics["memory_percent"], mem_limit, "Memory")
        trigger_alert("disk", metrics["disk_percent"], disk_limit, "Disk Space")


def main():
    parser = argparse.ArgumentParser(
        description="SysOps Command Line Tool for System Monitoring, Backups, and Cleanups.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples of usage:
  python sysops.py monitor --interval 5 --cpu-alert 85
  python sysops.py backup --src ./logs --dest ./backups --keep 3
  python sysops.py clean --dir ./temp --pattern "*.tmp" --age 5
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    # Subcommand: monitor
    monitor_parser = subparsers.add_parser("monitor", help="Monitor system resources in real-time.")
    monitor_parser.add_argument("--interval", type=int, default=3, help="Refresh interval in seconds (default: 3).")
    monitor_parser.add_argument("--once", action="store_true", help="Run once and exit instead of loop.")
    monitor_parser.add_argument("--webhook", type=str, help="Webhook URL to send resource alert notifications.")
    monitor_parser.add_argument("--cpu-alert", type=float, default=80.0, help="CPU warning threshold percentage (default: 80).")
    monitor_parser.add_argument("--mem-alert", type=float, default=80.0, help="Memory warning threshold percentage (default: 80).")
    monitor_parser.add_argument("--disk-alert", type=float, default=90.0, help="Disk warning threshold percentage (default: 90).")
    monitor_parser.add_argument("--log-file", type=str, default="metrics_log.json", help="Path to write JSON logging data.")
    
    # Subcommand: backup
    backup_parser = subparsers.add_parser("backup", help="Automate compressed ZIP directory backups.")
    backup_parser.add_argument("--src", type=str, required=True, help="Path of the directory to back up.")
    backup_parser.add_argument("--dest", type=str, required=True, help="Destination directory to save the ZIP backup.")
    backup_parser.add_argument("--keep", type=int, default=5, help="Number of backups to keep (default: 5).")
    backup_parser.add_argument("--webhook", type=str, help="Webhook URL to notify upon backup status updates.")
    
    # Subcommand: clean
    clean_parser = subparsers.add_parser("clean", help="Clean up old files from a directory.")
    clean_parser.add_argument("--dir", type=str, required=True, help="Target directory to scan and clean.")
    clean_parser.add_argument("--pattern", type=str, default="*.log", help="File matching pattern (default: '*.log').")
    clean_parser.add_argument("--age", type=int, default=7, help="Delete files older than this many days (default: 7).")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    if args.command == "monitor":
        # Get public IP data once at the start of monitoring
        print(f"{Fore.CYAN}Retrieving public network metadata...")
        ip_info = APIConnector.get_public_ip_info()
        
        monitor = SystemMonitor(metrics_file=args.log_file)
        
        if args.once:
            metrics = monitor.gather_metrics()
            monitor.log_metrics(metrics)
            monitor.render_dashboard(metrics, ip_info)
            monitor.check_alerts(metrics, args.webhook, args.cpu_alert, args.mem_alert, args.disk_alert)
        else:
            try:
                while True:
                    metrics = monitor.gather_metrics()
                    monitor.log_metrics(metrics)
                    monitor.render_dashboard(metrics, ip_info)
                    monitor.check_alerts(metrics, args.webhook, args.cpu_alert, args.mem_alert, args.disk_alert)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print(f"\n{Fore.GREEN}Monitoring stopped. Good bye!")
                
    elif args.command == "backup":
        TaskAutomator.backup(
            src_dir=args.src, 
            dest_dir=args.dest, 
            keep=args.keep, 
            webhook_url=args.webhook
        )
        
    elif args.command == "clean":
        TaskAutomator.clean(
            directory=args.dir, 
            pattern=args.pattern, 
            age_days=args.age
        )

if __name__ == "__main__":
    main()
