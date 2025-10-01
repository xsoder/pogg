import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import requests
import yt_dlp
import io
import os
import webbrowser
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

class DownloadManager:
    def __init__(self):
        self.active_downloads = {}
        self.download_queue = queue.Queue()
        
    def add_download(self, video_id, cancel_event):
        self.active_downloads[video_id] = {
            'cancel_event': cancel_event,
            'status': 'downloading'
        }
    
    def cancel_download(self, video_id):
        if video_id in self.active_downloads:
            self.active_downloads[video_id]['cancel_event'].set()
            self.active_downloads[video_id]['status'] = 'cancelled'
            return True
        return False
    
    def remove_download(self, video_id):
        if video_id in self.active_downloads:
            del self.active_downloads[video_id]
    
    def is_downloading(self, video_id):
        return video_id in self.active_downloads

class VideoCard(ttk.Frame):
    def __init__(self, parent, video_info, download_callback, cancel_callback, open_channel_callback, theme, **kwargs):
        super().__init__(parent, **kwargs)
        self.video_info = video_info
        self.download_callback = download_callback
        self.cancel_callback = cancel_callback
        self.open_channel_callback = open_channel_callback
        self.theme = theme
        self.thumbnail_img = None
        self.is_downloading = False
        self.progress_var = tk.DoubleVar()
        
        self.config(style='Card.TFrame', padding=10)
        
        # Left side - Thumbnail
        self.thumbnail_label = tk.Label(self, bg=self.theme['card_bg'])
        self.thumbnail_label.grid(row=0, column=0, rowspan=5, padx=(0, 15), sticky='n')
        
        # Right side - Info
        title_text = video_info.get('title', 'No title')
        if len(title_text) > 80:
            title_text = title_text[:77] + '...'
        
        self.title_label = ttk.Label(
            self, 
            text=title_text, 
            wraplength=450, 
            font=('Iosevka', 12, 'bold'),
            foreground=self.theme['title_fg'],
            style='CardTitle.TLabel'
        )
        self.title_label.grid(row=0, column=1, sticky='w', pady=(0, 5))
        
        channel = video_info.get('uploader', 'Unknown')
        self.channel_label = ttk.Label(
            self, 
            text=f"Channel: {channel}", 
            font=('Iosevka', 10),
            foreground=self.theme['accent'],
            cursor='hand2',
            style='CardText.TLabel'
        )
        self.channel_label.grid(row=1, column=1, sticky='w', pady=2)
        self.channel_label.bind('<Button-1>', lambda e: self.on_channel_click())
        
        # Duration and views
        duration = video_info.get('duration')
        if duration:
            mins, secs = divmod(duration, 60)
            duration_str = f"Duration: {mins}m {secs}s"
        else:
            duration_str = "Duration: Unknown"
            
        view_count = video_info.get('view_count', 0)
        if view_count:
            views_str = f"Views: {view_count:,}"
        else:
            views_str = ""
        
        info_text = f"{duration_str}   {views_str}"
        self.info_label = ttk.Label(
            self, 
            text=info_text, 
            font=('Iosevka', 10),
            foreground=self.theme['text_fg'],
            style='CardText.TLabel'
        )
        self.info_label.grid(row=2, column=1, sticky='w', pady=2)
        
        # Progress bar (initially hidden)
        self.progress_frame = ttk.Frame(self, style='Card.TFrame')
        self.progress_frame.grid(row=3, column=1, sticky='ew', pady=(5, 5))
        self.progress_frame.grid_remove()
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            mode='determinate',
            variable=self.progress_var,
            length=400
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.progress_label = ttk.Label(
            self.progress_frame,
            text="0%",
            font=('Iosevka', 9),
            foreground=self.theme['text_fg'],
            style='CardText.TLabel'
        )
        self.progress_label.pack(side=tk.LEFT)
        
        # Buttons frame
        btn_frame = ttk.Frame(self, style='Card.TFrame')
        btn_frame.grid(row=4, column=1, sticky='w', pady=(10, 0))
        
        self.download_btn = ttk.Button(
            btn_frame, 
            text="Download", 
            command=self.on_download,
            width=12,
            style='Accent.TButton'
        )
        self.download_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.cancel_btn = ttk.Button(
            btn_frame, 
            text="Cancel", 
            command=self.on_cancel,
            width=12,
            style='Danger.TButton'
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.cancel_btn.pack_forget()  # Initially hidden
        
        self.channel_btn = ttk.Button(
            btn_frame, 
            text="Visit Channel", 
            command=self.on_channel_click,
            width=12
        )
        self.channel_btn.pack(side=tk.LEFT)
        
        # Load thumbnail
        self.load_thumbnail()
        
    def load_thumbnail(self):
        thumb_url = self.video_info.get('thumbnail')
        if thumb_url:
            try:
                response = requests.get(thumb_url, timeout=5)
                image = Image.open(io.BytesIO(response.content))
                image = image.resize((200, 112))
                self.thumbnail_img = ImageTk.PhotoImage(image)
                self.thumbnail_label.config(image=self.thumbnail_img)
            except Exception:
                self.thumbnail_label.config(text='No Image', width=20, height=8)
    
    def show_progress(self):
        self.is_downloading = True
        self.progress_frame.grid()
        self.download_btn.pack_forget()
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 5))
        
    def hide_progress(self):
        self.is_downloading = False
        self.progress_frame.grid_remove()
        self.cancel_btn.pack_forget()
        self.download_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
    
    def update_progress(self, percent):
        self.progress_var.set(percent)
        self.progress_label.config(text=f"{int(percent)}%")
    
    def on_download(self):
        self.download_callback(self.video_info, self)
    
    def on_cancel(self):
        self.cancel_callback(self.video_info)
    
    def on_channel_click(self):
        self.open_channel_callback(self.video_info)

class YouTubeDownloader(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Pogg - YouTube Downloader")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # Configure grid weight for proper resizing
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.download_type = tk.StringVar(value="video")
        self.download_quality = tk.StringVar(value="best")
        self.download_folder = os.path.join(os.path.expanduser("~"), "media", "Videos", "Downloads")
        self.video_cards = []
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.num_results = tk.StringVar(value="50")
        self.dark_mode = tk.BooleanVar(value=True)
        self.download_manager = DownloadManager()

        # Create download folder if it doesn't exist
        os.makedirs(self.download_folder, exist_ok=True)

        # Define themes
        self.themes = {
            'dark': {
                'bg': '#1e1e1e',
                'fg': '#e0e0e0',
                'card_bg': '#2d2d2d',
                'input_bg': '#3c3c3c',
                'input_fg': '#ffffff',
                'accent': '#64b5f6',
                'accent_hover': '#42a5f5',
                'danger': '#ef5350',
                'danger_hover': '#e53935',
                'title_fg': '#ffffff',
                'text_fg': '#b0b0b0',
                'border': '#404040',
                'button_bg': '#424242',
                'button_fg': '#ffffff'
            },
            'light': {
                'bg': '#f5f5f5',
                'fg': '#212121',
                'card_bg': '#ffffff',
                'input_bg': '#ffffff',
                'input_fg': '#000000',
                'accent': '#1976D2',
                'accent_hover': '#1565C0',
                'danger': '#d32f2f',
                'danger_hover': '#c62828',
                'title_fg': '#212121',
                'text_fg': '#666666',
                'border': '#e0e0e0',
                'button_bg': '#e0e0e0',
                'button_fg': '#000000'
            }
        }
        
        self.current_theme = self.themes['dark']
        self.apply_theme()
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def apply_theme(self):
        theme = self.current_theme
        self.configure(bg=theme['bg'])
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('TFrame', background=theme['bg'])
        style.configure('TLabel', background=theme['bg'], foreground=theme['fg'], font=('Iosevka', 11))
        style.configure('TLabelframe', background=theme['bg'], foreground=theme['fg'], bordercolor=theme['border'])
        style.configure('TLabelframe.Label', background=theme['bg'], foreground=theme['fg'], font=('Iosevka', 11, 'bold'))
        
        style.configure('TButton', 
                       background=theme['button_bg'], 
                       foreground=theme['button_fg'],
                       bordercolor=theme['border'],
                       font=('Iosevka', 10),
                       relief='flat',
                       borderwidth=0)
        style.map('TButton',
                 background=[('active', theme['accent_hover'])],
                 foreground=[('active', '#ffffff')])
        
        style.configure('Accent.TButton',
                       background=theme['accent'],
                       foreground='#ffffff',
                       font=('Iosevka', 10, 'bold'))
        style.map('Accent.TButton',
                 background=[('active', theme['accent_hover'])])
        
        style.configure('Danger.TButton',
                       background=theme['danger'],
                       foreground='#ffffff',
                       font=('Iosevka', 10, 'bold'))
        style.map('Danger.TButton',
                 background=[('active', theme['danger_hover'])])
        
        style.configure('TRadiobutton', 
                       background=theme['bg'], 
                       foreground=theme['fg'],
                       font=('Iosevka', 10))
        style.map('TRadiobutton',
                 background=[('active', theme['bg'])],
                 foreground=[('active', theme['fg'])])
        
        style.configure('TEntry',
                       fieldbackground=theme['input_bg'],
                       foreground=theme['input_fg'],
                       bordercolor=theme['border'],
                       font=('Iosevka', 11))
        
        style.configure('TSpinbox',
                       fieldbackground=theme['input_bg'],
                       foreground=theme['input_fg'],
                       bordercolor=theme['border'],
                       font=('Iosevka', 10))
        
        # Enhanced Combobox styling
        style.configure('TCombobox',
                       fieldbackground=theme['input_bg'],
                       foreground=theme['input_fg'],
                       background=theme['button_bg'],
                       bordercolor=theme['border'],
                       arrowcolor=theme['fg'],
                       selectbackground=theme['accent'],
                       selectforeground='#ffffff',
                       padding=5,
                       relief='flat',
                       font=('Iosevka', 10))
        
        style.map('TCombobox',
                 fieldbackground=[('readonly', theme['input_bg']), ('disabled', theme['bg'])],
                 selectbackground=[('readonly', theme['input_bg'])],
                 selectforeground=[('readonly', theme['input_fg'])],
                 background=[('readonly', theme['button_bg']), ('active', theme['accent'])],
                 foreground=[('readonly', theme['input_fg']), ('active', '#ffffff')],
                 bordercolor=[('focus', theme['accent'])])
        
        # Dropdown list styling
        self.option_add('*TCombobox*Listbox.background', theme['input_bg'])
        self.option_add('*TCombobox*Listbox.foreground', theme['input_fg'])
        self.option_add('*TCombobox*Listbox.selectBackground', theme['accent'])
        self.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        self.option_add('*TCombobox*Listbox.font', ('Iosevka', 10))
        
        # Card styles
        style.configure('Card.TFrame',
                       background=theme['card_bg'],
                       relief='solid',
                       borderwidth=1,
                       bordercolor=theme['border'])
        
        style.configure('CardTitle.TLabel',
                       background=theme['card_bg'],
                       foreground=theme['title_fg'],
                       font=('Iosevka', 12, 'bold'))
        
        style.configure('CardText.TLabel',
                       background=theme['card_bg'],
                       foreground=theme['text_fg'],
                       font=('Iosevka', 10))
        
        style.configure('TCheckbutton',
                       background=theme['bg'],
                       foreground=theme['fg'],
                       font=('Iosevka', 10))
        style.map('TCheckbutton',
                 background=[('active', theme['bg'])],
                 foreground=[('active', theme['fg'])])
        
        style.configure('TProgressbar',
                       background=theme['accent'],
                       troughcolor=theme['input_bg'],
                       bordercolor=theme['border'])

    def toggle_theme(self):
        if self.dark_mode.get():
            self.current_theme = self.themes['dark']
        else:
            self.current_theme = self.themes['light']
        
        self.apply_theme()
        
        # Update canvas background
        if hasattr(self, 'canvas'):
            self.canvas.config(bg=self.current_theme['card_bg'])
        
        # Recreate all video cards with new theme
        if self.video_cards:
            video_infos = [card.video_info for card in self.video_cards]
            
            for card in self.video_cards:
                card.destroy()
            self.video_cards.clear()
            
            for video in video_infos:
                card = VideoCard(
                    self.scrollable_frame,
                    video,
                    self.download_video,
                    self.cancel_download,
                    self.open_channel,
                    self.current_theme
                )
                card.pack(fill=tk.X, pady=5, padx=5)
                self.video_cards.append(card)

    def create_widgets(self):
        # Main container with grid
        main_container = ttk.Frame(self, padding=20)
        main_container.grid(row=0, column=0, sticky='nsew')
        main_container.grid_rowconfigure(3, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        
        # Header with theme toggle
        header_frame = ttk.Frame(main_container)
        header_frame.grid(row=0, column=0, sticky='ew', pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ttk.Label(
            header_frame, 
            text="Pogg", 
            font=('Iosevka', 26, 'bold'),
            foreground=self.current_theme['accent']
        )
        title_label.grid(row=0, column=0)
        
        theme_toggle = ttk.Checkbutton(
            header_frame,
            text="Dark Mode",
            variable=self.dark_mode,
            command=self.toggle_theme,
            style='TCheckbutton'
        )
        theme_toggle.grid(row=0, column=1, padx=10)

        # Search section
        search_frame = ttk.LabelFrame(main_container, text="Search", padding=15)
        search_frame.grid(row=1, column=0, sticky='ew', pady=(0, 15))
        search_frame.grid_columnconfigure(0, weight=1)

        search_input_frame = ttk.Frame(search_frame)
        search_input_frame.grid(row=0, column=0, sticky='ew')
        search_input_frame.grid_columnconfigure(0, weight=1)

        search_entry = ttk.Entry(
            search_input_frame, 
            textvariable=self.search_var,
            font=('Iosevka', 11)
        )
        search_entry.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        search_entry.bind("<Return>", lambda e: self.search_video())
        search_entry.bind("<Control-a>", self.select_all)
        search_entry.bind("<Control-A>", self.select_all)
        search_entry.focus()

        search_btn = ttk.Button(
            search_input_frame, 
            text="Search", 
            command=self.search_video,
            width=15,
            style='Accent.TButton'
        )
        search_btn.grid(row=0, column=1)
        
        # Number of results
        results_count_frame = ttk.Frame(search_frame)
        results_count_frame.grid(row=1, column=0, sticky='w', pady=(10, 0))
        
        ttk.Label(results_count_frame, text="Number of results:", font=('Iosevka', 10)).pack(side=tk.LEFT, padx=(0, 10))
        
        results_spinbox = ttk.Spinbox(
            results_count_frame,
            from_=10,
            to=100,
            textvariable=self.num_results,
            width=10,
            font=('Iosevka', 10)
        )
        results_spinbox.pack(side=tk.LEFT)

        # Options section
        options_frame = ttk.LabelFrame(main_container, text="Download Options", padding=15)
        options_frame.grid(row=2, column=0, sticky='ew', pady=(0, 15))
        options_frame.grid_columnconfigure(1, weight=1)

        # Format selection
        format_frame = ttk.Frame(options_frame)
        format_frame.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))
        
        ttk.Label(format_frame, text="Format:", font=('Iosevka', 11, 'bold')).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(
            format_frame, 
            text="Video", 
            variable=self.download_type, 
            value="video"
        ).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(
            format_frame, 
            text="Audio (MP3)", 
            variable=self.download_type, 
            value="audio"
        ).pack(side=tk.LEFT, padx=10)
        
        # Quality selection
        ttk.Label(format_frame, text="Quality:", font=('Iosevka', 11, 'bold')).pack(side=tk.LEFT, padx=(30, 10))
        
        quality_frame = ttk.Frame(format_frame, style='TFrame')
        quality_frame.pack(side=tk.LEFT, padx=5)
        
        quality_combo = ttk.Combobox(
            quality_frame,
            textvariable=self.download_quality,
            values=["best", "1080p", "720p", "480p", "360p"],
            state="readonly",
            width=12,
            font=('Iosevka', 10),
            style='TCombobox'
        )
        quality_combo.pack(side=tk.LEFT)

        # Download location
        ttk.Label(
            options_frame, 
            text="Download Folder:", 
            font=('Iosevka', 11, 'bold')
        ).grid(row=1, column=0, sticky='w', padx=(0, 10))

        self.folder_label = ttk.Label(
            options_frame, 
            text=self.download_folder, 
            relief='sunken',
            padding=5,
            foreground=self.current_theme['accent'],
            font=('Iosevka', 10)
        )
        self.folder_label.grid(row=1, column=1, sticky='ew', padx=(0, 10))

        folder_btn = ttk.Button(
            options_frame, 
            text="Browse", 
            command=self.choose_folder,
            width=12
        )
        folder_btn.grid(row=1, column=2)

        # Results section with scrollbar
        results_label_frame = ttk.LabelFrame(main_container, text="Search Results", padding=10)
        results_label_frame.grid(row=3, column=0, sticky='nsew', pady=(0, 15))
        results_label_frame.grid_rowconfigure(0, weight=1)
        results_label_frame.grid_columnconfigure(0, weight=1)

        # Create canvas and scrollbar
        self.canvas = tk.Canvas(
            results_label_frame, 
            bg=self.current_theme['card_bg'], 
            highlightthickness=0,
            highlightbackground=self.current_theme['border']
        )
        scrollbar = ttk.Scrollbar(results_label_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.bind('<Configure>', self.on_canvas_configure)

        self.canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')

        # Bind mouse wheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        # Status bar
        status_frame = ttk.Frame(main_container)
        status_frame.grid(row=4, column=0, sticky='ew', pady=(5, 0))
        status_frame.grid_columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(
            status_frame, 
            text="Ready to search...", 
            foreground=self.current_theme['accent'],
            font=('Iosevka', 10)
        )
        self.status_label.pack(side=tk.LEFT)

    def on_canvas_configure(self, event):
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def select_all(self, event):
        event.widget.select_range(0, tk.END)
        event.widget.icursor(tk.END)
        return 'break'

    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.folder_label.config(text=self.download_folder)
            os.makedirs(self.download_folder, exist_ok=True)

    def search_video(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Warning", "Please enter a search term.")
            return

        for card in self.video_cards:
            card.destroy()
        self.video_cards.clear()

        self.status_label.config(text="Searching...", foreground=self.current_theme['accent'])
        self.update()

        try:
            num_results = int(self.num_results.get())
        except ValueError:
            num_results = 50

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(f"ytsearch{num_results}:{query}", download=False)
                videos = result.get("entries", [])
                
                if not videos:
                    self.status_label.config(text="No results found", foreground="red")
                    return
                
                for idx, video in enumerate(videos):
                    if video:
                        card = VideoCard(
                            self.scrollable_frame, 
                            video, 
                            self.download_video,
                            self.cancel_download,
                            self.open_channel,
                            self.current_theme
                        )
                        card.pack(fill=tk.X, pady=5, padx=5)
                        self.video_cards.append(card)
                
                self.status_label.config(
                    text=f"Found {len(self.video_cards)} results!", 
                    foreground="green"
                )
                
                self.canvas.yview_moveto(0)
                
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", foreground="red")

    def open_channel(self, video_info):
        channel_url = video_info.get('channel_url') or video_info.get('uploader_url')
        if channel_url:
            webbrowser.open(channel_url)
        else:
            messagebox.showinfo("Info", "Channel URL not available")

    def cancel_download(self, video_info):
        video_id = video_info.get('id')
        if self.download_manager.cancel_download(video_id):
            self.status_label.config(text="Download cancelled", foreground="orange")

    def download_video(self, video_info, card):
        video_id = video_info.get('id')
        
        if self.download_manager.is_downloading(video_id):
            messagebox.showinfo("Info", "This video is already being downloaded")
            return
        
        card.show_progress()
        self.status_label.config(
            text=f"Downloading: {video_info['title'][:50]}...", 
            foreground=self.current_theme['accent']
        )
        self.update()

        quality = self.download_quality.get()
        if self.download_type.get() == "audio":
            format_choice = "bestaudio"
        else:
            if quality == "best":
                format_choice = "best"
            else:
                height = quality.rstrip('p')
                format_choice = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"

        ydl_opts = {
            "format": format_choice,
            "outtmpl": os.path.join(self.download_folder, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [lambda d: self.progress_hook(d, card)],
        }

        if self.download_type.get() == "audio":
            ydl_opts["postprocessors"] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        cancel_event = threading.Event()
        self.download_manager.add_download(video_id, cancel_event)

        def download_task():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if not cancel_event.is_set():
                        ydl.download([video_info["webpage_url"]])
                    
                    if cancel_event.is_set():
                        self.after(0, lambda: card.hide_progress())
                        self.download_manager.remove_download(video_id)
                        return
                    
                    self.after(0, lambda: card.hide_progress())
                    self.after(0, lambda: self.status_label.config(
                        text="Download completed!", 
                        foreground="green"
                    ))
                    self.after(0, lambda: messagebox.showinfo(
                        "Success", 
                        f"Downloaded: {video_info['title'][:60]}\n\nSaved to: {self.download_folder}"
                    ))
                    self.download_manager.remove_download(video_id)
                    
            except Exception as e:
                if not cancel_event.is_set():
                    self.after(0, lambda: card.hide_progress())
                    self.after(0, lambda: self.status_label.config(
                        text=f"Error: {str(e)}", 
                        foreground="red"
                    ))
                    self.after(0, lambda: messagebox.showerror(
                        "Error", 
                        f"Download failed: {str(e)}"
                    ))
                self.download_manager.remove_download(video_id)

        self.executor.submit(download_task)

    def progress_hook(self, d, card):
        if d['status'] == 'downloading':
            try:
                percent = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
                self.after(0, lambda: card.update_progress(percent))
            except:
                pass
        elif d['status'] == 'finished':
            self.after(0, lambda: card.update_progress(100))

    def on_closing(self):
        # Cancel all active downloads
        for video_id in list(self.download_manager.active_downloads.keys()):
            self.download_manager.cancel_download(video_id)
        
        self.executor.shutdown(wait=False)
        self.destroy()


if __name__ == "__main__":
    app = YouTubeDownloader()
    app.mainloop()

