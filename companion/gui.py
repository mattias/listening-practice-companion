"""The program's window: status, phone connection, language model and voice server, start and stop."""
import os
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from . import __version__, autostart, config, irodori, ollama
from .llm import LLM
from .runner import Service, lan_addresses, service_health

KINDS = {"Ollama on this computer": "ollama", "Other service with the OpenAI API (LM Studio, OpenRouter, Gemini ...)": "openai"}
REPO_URL = "https://github.com/mattias/listening-practice-companion"


class App(tk.Tk):
    def __init__(self, cfg, minimized=False):
        super().__init__()
        self.cfg = cfg
        self.service = Service()
        self.voice_proc = None
        self.busy = {"voice": False, "pull": False}
        self.title(f"Listening Practice Companion {__version__}")
        self.minsize(560, 0)
        self.protocol("WM_DELETE_WINDOW", self.quit_program)
        pad = {"padx": 10, "pady": 4}

        intro = ttk.Label(
            self,
            wraplength=540,
            text="This program makes sound training sentences for the Listening Practice app: a language model writes them from "
                 "the words you know, and the Irodori voice server speaks them. The phone connects to this computer with the "
                 "address and token below. Leave the program running while you make sentences.",
        )
        intro.pack(fill="x", **pad)

        self.status = {}
        box = ttk.LabelFrame(self, text="Status")
        box.pack(fill="x", **pad)
        for key in ("voice", "llm", "service"):
            label = ttk.Label(box, text="…", wraplength=520, justify="left")
            label.pack(anchor="w", padx=8, pady=1)
            self.status[key] = label

        # ---- phone connection
        phone = ttk.LabelFrame(self, text="Phone connection")
        phone.pack(fill="x", **pad)
        self.network = tk.BooleanVar(value=cfg["ALLOW_NETWORK"])
        ttk.Checkbutton(phone, text="Let my phone connect (listen on the local network)", variable=self.network,
                        command=self.show_address).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=2)
        ttk.Label(phone, text="Port").grid(row=1, column=0, sticky="w", padx=8)
        self.port = tk.StringVar(value=str(cfg["PORT"]))
        ttk.Entry(phone, textvariable=self.port, width=8).grid(row=1, column=1, sticky="w")
        self.port.trace_add("write", lambda *_: self.show_address())
        ttk.Label(phone, text="Address").grid(row=2, column=0, sticky="nw", padx=8, pady=2)
        self.address = tk.StringVar()
        ttk.Label(phone, textvariable=self.address, justify="left").grid(row=2, column=1, columnspan=2, sticky="w")
        ttk.Label(phone, text="Token").grid(row=3, column=0, sticky="w", padx=8, pady=2)
        self.token = tk.StringVar(value=cfg["TOKEN"])
        ttk.Entry(phone, textvariable=self.token, state="readonly", width=42).grid(row=3, column=1, sticky="we")
        buttons = ttk.Frame(phone)
        buttons.grid(row=3, column=2, padx=4)
        ttk.Button(buttons, text="Copy", width=6, command=self.copy_token).pack(side="left")
        ttk.Button(buttons, text="New", width=5, command=self.new_token).pack(side="left", padx=2)
        ttk.Label(
            phone, wraplength=520, justify="left", foreground="#555",
            text="Enter the address and the token in the app (Settings > Library > Sound training). The token keeps others on your "
                 "network out. If the phone can not connect, allow this program through the Windows firewall on private networks.",
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        phone.columnconfigure(1, weight=1)

        # ---- language model
        llm = ttk.LabelFrame(self, text="Language model (writes and translates the sentences)")
        llm.pack(fill="x", **pad)
        self.kind = tk.StringVar(value=next((k for k, v in KINDS.items() if v == cfg["LLM_KIND"]), next(iter(KINDS))))
        self.llm_url = tk.StringVar(value=cfg["LLM_URL"])
        self.model = tk.StringVar(value=cfg["LLM_MODEL"])
        self.translate_model = tk.StringVar(value=cfg["TRANSLATE_MODEL"])
        self.api_key = tk.StringVar(value=cfg["LLM_API_KEY"])
        rows = [("Service", ttk.Combobox(llm, textvariable=self.kind, values=list(KINDS), state="readonly", width=52)),
                ("Address", ttk.Entry(llm, textvariable=self.llm_url)),
                ("Model", None),
                ("Translation model", ttk.Entry(llm, textvariable=self.translate_model)),
                ("API key", ttk.Entry(llm, textvariable=self.api_key, show="*"))]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(llm, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=2)
            if label == "Model":
                self.model_box = ttk.Combobox(llm, textvariable=self.model, values=[])
                self.model_box.grid(row=i, column=1, sticky="we", padx=4)
            else:
                widget.grid(row=i, column=1, sticky="we", padx=4)
        bar = ttk.Frame(llm)
        bar.grid(row=5, column=0, columnspan=2, sticky="w", padx=8, pady=4)
        ttk.Button(bar, text="Find installed models", command=self.find_models).pack(side="left")
        self.pull_button = ttk.Button(bar, text=f"Download {ollama.RECOMMENDED_MODEL} (about 5 GB)", command=self.pull_model)
        self.pull_button.pack(side="left", padx=6)
        self.pull_status = ttk.Label(llm, text="")
        self.pull_status.grid(row=6, column=0, columnspan=2, sticky="w", padx=8)
        ttk.Label(
            llm, wraplength=520, justify="left", foreground="#555",
            text="Ollama (ollama.com) runs the model on this computer's graphics card: nothing is sent anywhere. With another service "
                 "the sentences are sent to it. The translation model is optional: a translategemma model in Ollama is used "
                 "automatically, otherwise the model above translates.",
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=8, pady=4)
        llm.columnconfigure(1, weight=1)

        # ---- voice server
        voice = ttk.LabelFrame(self, text="Voice server (Irodori)")
        voice.pack(fill="x", **pad)
        ttk.Label(voice, text="Address").grid(row=0, column=0, sticky="w", padx=8, pady=2)
        self.irodori_url = tk.StringVar(value=cfg["IRODORI_URL"])
        ttk.Entry(voice, textvariable=self.irodori_url).grid(row=0, column=1, sticky="we", padx=4)
        self.irodori_auto = tk.BooleanVar(value=cfg["IRODORI_AUTO_START"])
        ttk.Checkbutton(voice, text="Start the voice server together with this program (if it was installed by the Irodori Audio add-on)",
                        variable=self.irodori_auto).grid(row=1, column=0, columnspan=2, sticky="w", padx=8)
        self.voice_button = ttk.Button(voice, text="Start the voice server now", command=self.start_voice)
        self.voice_button.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=4)
        voice.columnconfigure(1, weight=1)

        # ---- the program
        prog = ttk.Frame(self)
        prog.pack(fill="x", **pad)
        self.on_launch = tk.BooleanVar(value=cfg["START_SERVICE_ON_LAUNCH"])
        ttk.Checkbutton(prog, text="Start the service when the program opens", variable=self.on_launch).pack(anchor="w")
        self.windows_start = tk.BooleanVar(value=autostart.is_enabled())
        if autostart.supported():
            ttk.Checkbutton(prog, text="Start the program when I log in to Windows", variable=self.windows_start).pack(anchor="w")
        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        self.toggle = ttk.Button(row, text="Save and start the service", command=self.toggle_service)
        self.toggle.pack(side="left")
        ttk.Button(row, text="Open the log", command=lambda: self.open_path(config.log_path())).pack(side="left", padx=6)
        ttk.Button(row, text="Help", command=lambda: webbrowser.open(REPO_URL)).pack(side="left")
        ttk.Button(row, text="Quit", command=self.quit_program).pack(side="right")

        self.show_address()
        self.refresh()
        self.after(300, self.on_open)
        if minimized:
            self.iconify()

    # ---- settings

    def apply(self):
        c = self.cfg
        c["ALLOW_NETWORK"] = self.network.get()
        try:
            c["PORT"] = int(self.port.get())
        except ValueError:
            pass
        c["LLM_KIND"] = KINDS[self.kind.get()]
        c["LLM_URL"] = self.llm_url.get().strip()
        c["LLM_MODEL"] = self.model.get().strip()
        c["TRANSLATE_MODEL"] = self.translate_model.get().strip()
        c["LLM_API_KEY"] = self.api_key.get().strip()
        c["IRODORI_URL"] = self.irodori_url.get().strip()
        c["IRODORI_AUTO_START"] = self.irodori_auto.get()
        c["START_SERVICE_ON_LAUNCH"] = self.on_launch.get()
        c["TOKEN"] = self.token.get()
        config.save(c)
        if autostart.supported() and self.windows_start.get() != autostart.is_enabled():
            autostart.set_enabled(self.windows_start.get())

    def show_address(self):
        try:
            port = int(self.port.get())
        except ValueError:
            port = self.cfg["PORT"]
        if not self.network.get():
            self.address.set(f"Not shared: only this computer can connect (http://127.0.0.1:{port}).")
            return
        ips = lan_addresses()
        self.address.set("\n".join(f"http://{ip}:{port}" for ip in ips) or "No network address was found.")

    def copy_token(self):
        self.clipboard_clear()
        self.clipboard_append(self.token.get())

    def new_token(self):
        if self.service.running and not messagebox.askyesno(
                "New token", "Phones that know the old token will be refused until you enter the new one. Continue?"):
            return
        self.token.set(config.new_token())
        self.apply()
        if self.service.running:
            self.restart_service()

    def open_path(self, path):
        if os.path.exists(path):
            os.startfile(path) if hasattr(os, "startfile") else webbrowser.open("file://" + path)

    # ---- the service

    def toggle_service(self):
        if self.service.running:
            self.service.stop()
            self.refresh()
            return
        self.apply()
        try:
            self.service.start(self.cfg)
        except RuntimeError as e:
            messagebox.showerror("Could not start the service", str(e))
        self.refresh()

    def restart_service(self):
        self.service.stop()
        self.apply()
        try:
            self.service.start(self.cfg)
        except RuntimeError as e:
            messagebox.showerror("Could not start the service", str(e))
        self.refresh()

    def on_open(self):
        if self.cfg["IRODORI_AUTO_START"]:
            self.start_voice(quiet=True)
        if self.cfg["START_SERVICE_ON_LAUNCH"]:
            try:
                self.service.start(self.cfg)
            except RuntimeError as e:
                self.status["service"].config(text="The service did not start: " + str(e))
        self.refresh()

    # ---- the voice server

    def start_voice(self, quiet=False):
        url = self.irodori_url.get().strip()
        root = self.cfg["IRODORI_DIR"] or irodori.default_dir()
        if self.busy["voice"] or irodori.health(url) or not irodori.is_installed(root):
            if not quiet and not irodori.is_installed(root) and not irodori.health(url):
                messagebox.showinfo(
                    "Voice server", "The voice server is not installed. Install it with the Irodori Audio add-on for Anki "
                    "(Tools > Irodori Audio > Set up local server), or follow the server's own instructions. See Help.")
            return
        self.busy["voice"] = True

        def work():
            try:
                self.voice_proc = irodori.start(root, url, print)
                error = ""
            except RuntimeError as e:
                error = str(e)
            self.busy["voice"] = False
            if error and not quiet:
                self.after(0, lambda: messagebox.showerror("Voice server", error))

        threading.Thread(target=work, daemon=True).start()

    # ---- models

    def llm(self):
        return LLM(self.llm_url.get().strip(), self.model.get().strip(), self.api_key.get().strip(), KINDS[self.kind.get()])

    def find_models(self):
        llm = self.llm()

        def work():
            names = llm.models()
            self.after(0, lambda: self.model_box.config(values=names))
            self.after(0, lambda: self.pull_status.config(text=f"{len(names)} models found." if names else
                                                          "No models found: is Ollama installed and running?"))

        threading.Thread(target=work, daemon=True).start()

    def pull_model(self):
        if self.busy["pull"] or KINDS[self.kind.get()] != "ollama":
            return
        self.busy["pull"] = True
        model = self.model.get().strip() or ollama.RECOMMENDED_MODEL
        url = self.llm_url.get().strip()
        self.pull_button.state(["disabled"])

        def progress(text):
            self.after(0, lambda: self.pull_status.config(text=f"{model}: {text}"))

        def work():
            try:
                ollama.pull(url, model, progress)
                self.after(0, lambda: self.pull_status.config(text=f"{model} is ready."))
            except RuntimeError as e:
                self.after(0, lambda: messagebox.showerror("Download", str(e)))
            self.busy["pull"] = False
            self.after(0, lambda: self.pull_button.state(["!disabled"]))
            self.after(0, self.find_models)

        threading.Thread(target=work, daemon=True).start()

    # ---- status

    def refresh(self):
        """Asks the parts how they are (off the window's thread) and shows it; repeats."""
        llm, url, port = self.llm(), self.irodori_url.get().strip(), self.cfg["PORT"]
        name = self.model.get().strip()

        def work():
            voice = irodori.health(url)
            models = llm.models()
            service = self.service.running and service_health(port)
            self.after(0, lambda: self.show_status(voice, models, name, service))

        threading.Thread(target=work, daemon=True).start()
        self.after(3000, self.refresh)

    def show_status(self, voice, models, model, service):
        ok, bad = "OK  ", "NOT OK  "
        self.status["voice"].config(
            text=(ok + "Voice server (Irodori) is running.") if voice else
            (bad + "Voice server (Irodori) is not running. Use Start the voice server now, or start it from the Irodori Audio add-on."))
        if not models:
            self.status["llm"].config(text=bad + "No language model found: is Ollama installed and running (ollama.com)?")
        elif model in models:
            self.status["llm"].config(text=ok + f"Language model {model} is installed.")
        else:
            self.status["llm"].config(text=bad + f"The language model {model} is not installed: press the Download button.")
        self.status["service"].config(
            text=(ok + "The service is running: the phone can connect.") if service else
            (bad + "The service is stopped: press Save and start the service."))
        self.toggle.config(text="Stop the service" if self.service.running else "Save and start the service")

    def quit_program(self):
        try:
            self.apply()
        finally:
            self.service.stop()
            irodori.kill_tree(self.voice_proc)
            self.destroy()
