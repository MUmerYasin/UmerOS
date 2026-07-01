import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import os
import urllib.request
import urllib.error

# ── Host OS Integration Bridge ──
class HostBridge:
    """Bridges Umer OS VFS with the host Windows OS."""
    HOST_DIR = os.path.join(os.getcwd(), "HostFiles")

    @classmethod
    def extract_and_open(cls, kernel, vfs_path: str):
        if not os.path.exists(cls.HOST_DIR):
            os.makedirs(cls.HOST_DIR, exist_ok=True)
            
        try:
            # Read from VFS
            data = kernel.vfs.read_file(vfs_path)
            if data is None:
                raise Exception("File not found in Virtual File System.")
            
            # Write to real host disk
            filename = vfs_path.strip('/').split('/')[-1]
            host_path = os.path.join(cls.HOST_DIR, filename)
            
            with open(host_path, "wb") as f:
                f.write(data)
                
            # Ask Windows to open it with the default app
            if os.name == 'nt':
                os.startfile(host_path)
            else:
                # Fallback for linux/mac if run there
                import subprocess
                subprocess.call(('xdg-open' if os.name == 'posix' else 'open', host_path))
                
            return True, f"Successfully handed off '{filename}' to Host OS."
        except Exception as e:
            return False, str(e)


# ── Umer Apps ──
class UmerFiles(tk.Toplevel):
    def __init__(self, master, kernel):
        super().__init__(master)
        self.kernel = kernel
        self.title("UmerFiles - File Browser")
        self.geometry("600x400")
        self.configure(bg="#1e1e2e")
        
        self.current_path = "/"
        
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Up", command=self.go_up).pack(side=tk.LEFT)
        self.path_lbl = ttk.Label(toolbar, text=self.current_path, font=("Consolas", 10, "bold"))
        self.path_lbl.pack(side=tk.LEFT, padx=10)
        
        # File List
        columns = ("name", "type", "size")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("name", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size/Dedup")
        self.tree.column("name", width=250)
        self.tree.column("type", width=100)
        self.tree.column("size", width=150)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tree.bind("<Double-1>", self.on_double_click)
        self.refresh()
        
    def refresh(self):
        self.path_lbl.config(text=self.current_path)
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            items = self.kernel.vfs.ls(self.current_path)
            for item in items:
                path = f"{self.current_path.rstrip('/')}/{item}"
                stat = self.kernel.vfs.stat(path)
                if stat:
                    itype = stat['type']
                    if itype == "dir":
                        size = "<DIR>"
                    else:
                        size = f"{stat['size']} B"
                    self.tree.insert("", tk.END, values=(item, itype.upper(), size))
        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    def go_up(self):
        if self.current_path != "/":
            parts = self.current_path.rstrip('/').split('/')
            self.current_path = "/".join(parts[:-1])
            if not self.current_path:
                self.current_path = "/"
            self.refresh()
            
    def on_double_click(self, event):
        item = self.tree.selection()[0]
        name = self.tree.item(item, "values")[0]
        itype = self.tree.item(item, "values")[1]
        
        if itype == "DIR":
            self.current_path = f"{self.current_path.rstrip('/')}/{name}"
            self.refresh()
        else:
            path = f"{self.current_path.rstrip('/')}/{name}"
            # Open natively!
            success, msg = HostBridge.extract_and_open(self.kernel, path)
            if not success:
                messagebox.showerror("Host Error", msg)


class UmerDownloader(tk.Toplevel):
    def __init__(self, master, kernel):
        super().__init__(master)
        self.kernel = kernel
        self.title("UmerDownloader - Media Fetcher")
        self.geometry("500x200")
        self.configure(bg="#1e1e2e")
        
        ttk.Label(self, text="URL:").pack(pady=(10,0))
        # Default to a small test image just in case
        self.url_var = tk.StringVar(value="https://www.google.com/favicon.ico")
        ttk.Entry(self, textvariable=self.url_var, width=50).pack(pady=5)
        
        ttk.Label(self, text="Save to (VFS path):").pack()
        self.path_var = tk.StringVar(value="/user/downloads/file.ico")
        ttk.Entry(self, textvariable=self.path_var, width=50).pack(pady=5)
        
        self.btn = ttk.Button(self, text="Download", command=self.download)
        self.btn.pack(pady=10)
        
    def download(self):
        url = self.url_var.get()
        path = self.path_var.get()
        self.btn.config(state="disabled", text="Downloading...")
        
        def _dl():
            try:
                # Ensure VFS dir exists
                dir_path = "/".join(path.rstrip('/').split('/')[:-1])
                if dir_path:
                    try:
                        self.kernel.vfs.mkdir(dir_path)
                    except: pass
                    
                req = urllib.request.Request(url, headers={'User-Agent': 'UmerOS/2.0'})
                with urllib.request.urlopen(req) as response:
                    data = response.read()
                
                # Save to VFS
                self.kernel.vfs.write_file(path, data)
                self.after(0, lambda: messagebox.showinfo("Success", f"Downloaded {len(data)} bytes to VFS: {path}\nYou can now open it in UmerFiles or UmerMedia!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to download:\n{e}"))
            finally:
                self.after(0, lambda: self.btn.config(state="normal", text="Download"))
                
        threading.Thread(target=_dl, daemon=True).start()


class UmerMedia(tk.Toplevel):
    def __init__(self, master, kernel):
        super().__init__(master)
        self.kernel = kernel
        self.title("UmerMedia - Native Player Bridge")
        self.geometry("500x200")
        self.configure(bg="#1e1e2e")
        
        ttk.Label(self, text="VFS Media File Path (.mp4, .mp3, etc):").pack(pady=(20, 5))
        self.path_var = tk.StringVar(value="")
        ttk.Entry(self, textvariable=self.path_var, width=50).pack(pady=5)
        
        ttk.Button(self, text="▶ Play via Host OS", command=self.play).pack(pady=10)
        
    def play(self):
        path = self.path_var.get()
        if not path:
            return
        success, msg = HostBridge.extract_and_open(self.kernel, path)
        if success:
            messagebox.showinfo("Playing", msg)
        else:
            messagebox.showerror("Playback Error", msg)


class UmerDocs(tk.Toplevel):
    def __init__(self, master, kernel):
        super().__init__(master)
        self.kernel = kernel
        self.title("UmerDocs - Native Document Bridge")
        self.geometry("500x200")
        self.configure(bg="#1e1e2e")
        
        ttk.Label(self, text="VFS Document Path (.pdf, .docx, .xlsx):").pack(pady=(20, 5))
        self.path_var = tk.StringVar(value="")
        ttk.Entry(self, textvariable=self.path_var, width=50).pack(pady=5)
        
        ttk.Button(self, text="📄 Open via Host OS", command=self.open_doc).pack(pady=10)
        
    def open_doc(self):
        path = self.path_var.get()
        if not path:
            return
        success, msg = HostBridge.extract_and_open(self.kernel, path)
        if success:
            messagebox.showinfo("Opened", msg)
        else:
            messagebox.showerror("Viewer Error", msg)


class UmerDE:
    """
    Umer Desktop Environment (UmerDE).
    A graphical shell for Umer OS built using Tkinter.
    """
    def __init__(self, kernel):
        self.kernel = kernel
        self.root = None
        
    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("Umer OS - Desktop Environment")
        self.root.geometry("900x650")
        self.root.configure(bg="#1e1e2e")
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Consolas", 10))
        style.configure("TButton", font=("Consolas", 10, "bold"), background="#89b4fa", foreground="#11111b")
        style.configure("Header.TLabel", font=("Consolas", 14, "bold"), foreground="#a6e3a1")

        # Top Bar (System Tray)
        tray_frame = ttk.Frame(self.root, padding=10)
        tray_frame.pack(side=tk.TOP, fill=tk.X)
        
        self.lbl_sysname = ttk.Label(tray_frame, text="Umer OS v2.0-Quantum", style="Header.TLabel")
        self.lbl_sysname.pack(side=tk.LEFT)
        
        self.lbl_memory = ttk.Label(tray_frame, text="Mem: 0 MB / 4096 MB")
        self.lbl_memory.pack(side=tk.RIGHT, padx=10)
        
        self.lbl_tasks = ttk.Label(tray_frame, text="Tasks: 0")
        self.lbl_tasks.pack(side=tk.RIGHT, padx=10)
        
        # App Launcher (Dock)
        dock_frame = ttk.Frame(self.root, padding=5)
        dock_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Label(dock_frame, text="Dock:").pack(side=tk.LEFT, padx=10)
        ttk.Button(dock_frame, text="📁 UmerFiles", command=lambda: UmerFiles(self.root, self.kernel)).pack(side=tk.LEFT, padx=5)
        ttk.Button(dock_frame, text="⬇️ Downloader", command=lambda: UmerDownloader(self.root, self.kernel)).pack(side=tk.LEFT, padx=5)
        ttk.Button(dock_frame, text="▶️ UmerMedia", command=lambda: UmerMedia(self.root, self.kernel)).pack(side=tk.LEFT, padx=5)
        ttk.Button(dock_frame, text="📄 UmerDocs", command=lambda: UmerDocs(self.root, self.kernel)).pack(side=tk.LEFT, padx=5)

        # Main Content Area
        content_frame = ttk.Frame(self.root)
        content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left Panel (AI Chat)
        ai_frame = ttk.Frame(content_frame, width=400)
        ai_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(ai_frame, text="AI Assistant", font=("Consolas", 12, "bold"), foreground="#f38ba8").pack(anchor=tk.W)
        self.chat_display = scrolledtext.ScrolledText(ai_frame, bg="#11111b", fg="#cdd6f4", font=("Consolas", 10), state="disabled")
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=5)
        
        input_frame = ttk.Frame(ai_frame)
        input_frame.pack(fill=tk.X)
        self.chat_input = ttk.Entry(input_frame, font=("Consolas", 10))
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind("<Return>", self._send_ai_msg)
        
        btn_send = ttk.Button(input_frame, text="Send", command=self._send_ai_msg)
        btn_send.pack(side=tk.RIGHT, padx=(5, 0))

        # Right Panel (Process Monitor)
        proc_frame = ttk.Frame(content_frame, width=300)
        proc_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        ttk.Label(proc_frame, text="Process Monitor", font=("Consolas", 12, "bold"), foreground="#89dceb").pack(anchor=tk.W)
        
        # Treeview for processes
        columns = ("pid", "name", "priority", "mem")
        self.proc_tree = ttk.Treeview(proc_frame, columns=columns, show="headings")
        self.proc_tree.heading("pid", text="PID")
        self.proc_tree.column("pid", width=50)
        self.proc_tree.heading("name", text="Name")
        self.proc_tree.column("name", width=120)
        self.proc_tree.heading("priority", text="Priority")
        self.proc_tree.column("priority", width=70)
        self.proc_tree.heading("mem", text="Memory")
        self.proc_tree.column("mem", width=70)
        self.proc_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Start background monitor thread
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._append_chat("System", "Umer AI Assistant initialized. How can I help you?")

    def _append_chat(self, sender, message):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, f"[{sender}] {message}\n")
        self.chat_display.yview(tk.END)
        self.chat_display.config(state="disabled")

    def _send_ai_msg(self, event=None):
        msg = self.chat_input.get().strip()
        if not msg:
            return
        self.chat_input.delete(0, tk.END)
        self._append_chat("User", msg)
        
        try:
            resp = self.kernel.ai_assistant.query(msg)
            self._append_chat("AI", resp)
        except Exception as e:
            self._append_chat("System Error", str(e))

    def _monitor_loop(self):
        while self.running:
            if self.root:
                try:
                    self.root.after(0, self._update_stats)
                except Exception:
                    break
            time.sleep(1)

    def _update_stats(self):
        mem_used = sum(self.kernel.memory.allocated.values())
        self.lbl_memory.config(text=f"Mem: {mem_used} MB / {self.kernel.memory.total} MB")
        
        queue_len = len(self.kernel.scheduler.task_queue)
        self.lbl_tasks.config(text=f"Tasks: {queue_len}")
        
        for item in self.proc_tree.get_children():
            self.proc_tree.delete(item)
            
        for task in self.kernel.scheduler.task_queue:
            mem = self.kernel.memory.allocated.get(task.pid, 0)
            self.proc_tree.insert("", tk.END, values=(task.pid, task.name, task.priority, f"{mem} MB"))

    def _on_close(self):
        self.running = False
        self.root.destroy()

    def start(self):
        self._build_ui()
        self.root.mainloop()
