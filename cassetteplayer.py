import os
from pathlib import Path
from pygame import mixer                # Handles the actual audio playback
from mutagen import File as MutagenFile # Extracts metadata (artist/title/length) from audio files
from rich.markup import escape          # Prevents Textual/Rich from crashing if a song title contains brackets like [ or ]
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Static, ListItem, ListView
from textual.binding import Binding

# Retro Color Palette used throughout the Textual CSS and Rich markup
COLORS = {
    "bg": "#1a1b26", 
    "border": "#7aa2f7", 
    "accent": "#bb9af7", 
    "green": "#9ece6a",
    "tape": "#444444",
    "label": "#e0af68",
    "shell": "#555555"
}

# The default directory where the app will look for audio files
MUSIC_PATH = os.path.expanduser('~/Music')

# Custom Textual Widget representing the ASCII Cassette Tape
class Cassette(Static):
    def __init__(self):
        super().__init__()
        self.frame = 0                  # Tracks the current animation frame
        self.is_playing = False         # Tracks whether the tape should be spinning
        self.spokes = ["◐", "◓", "◑", "◒"] # The characters used to simulate spinning reels
        self.title = "NO TRACK"

    def on_mount(self):
        # Starts a timer when the widget loads. It calls self.animate() every 0.1 seconds.
        self.set_interval(0.1, self.animate)

    def animate(self):
        # Only advance the frame and redraw if the music is currently playing
        if self.is_playing:
            self.frame = (self.frame + 1) % 4 # Loops the frame index from 0 to 3
            self.update_widget()

    def update_widget(self, status="PLAYING", title=None):
        if title: self.title = title
        
        progress = 0.0
        try:
            # Safely calculate how far along we are in the song (0.0 to 1.0)
            curr = self.app._current_time()
            total = float(getattr(self.app, "song_length", 0) or 1)
            progress = min(curr / total, 1.0)
        except:
            pass

        # Calculate tape physical look: 
        # As progress goes up, the left spool shrinks and the right spool grows (max size is 5 chars)
        l_size = int(5 * (1 - progress))
        r_size = int(5 * progress)
        l_tape = "█" * l_size + "░" * (5 - l_size)
        r_tape = "░" * (5 - r_size) + "█" * r_size
        s = self.spokes[self.frame] # Get the current spinning animation character
        
        # Prepare safe strings to prevent Rich markup parsing errors
        st = escape(status)
        ti = escape(self.title[:28]) # Truncate title to fit the physical label width

        # Setup explicit Rich text color tags using our palette
        sh = f"[bold {COLORS['shell']}]"   # Shell tag
        lb = f"[bold {COLORS['label']}]"   # Label tag
        ac = f"[bold {COLORS['accent']}]"  # Accent tag
        gr = f"[bold {COLORS['green']}]"   # Green tag
        cl = "[/]"                         # Generic tag to close the previous color

        # The multi-line raw string defining the ASCII art shape and colors
        cassette_art = rf"""
{sh} _________________________________________________ {cl}
{sh}| {cl}[#333333]_______________________________________________[/#333333]{sh} |{cl}
{sh}| |{cl} {lb}  LAZY-LOCAL {cl}[#444444]■■■{cl}{lb} HIGH BIAS C-90 {cl} {sh}      | |{cl}
{sh}| |{cl} {lb}  {cl}[white]TITLE: {ti:<28}{cl} {sh} | |{cl}
{sh}| |{cl}[#333333]_______________________________________________[/#333333]{sh} |{cl}
{sh}|  {cl}[#222222]_____________________________________________  {cl}{sh}|{cl}
{sh}| | {cl}[#111111]      ({l_tape})             ({r_tape})      [/#111111] {sh}| |{cl}
{sh}| | {cl}[#111111]     (  \[{ac}{s}{cl}\]  )           (  \[{ac}{s}{cl}\]  )     [/#111111] {sh}| |{cl}
{sh}| | {cl}[#111111]      (_______)             (_______)      [/#111111] {sh}| |{cl}
{sh}| |_[cl][#222222]_____________________________________________[/#222222]{sh}_| |{cl}
{sh}|        {cl}[#333333]/      [#1a1b26]_____________________[/#1a1b26]      \ {cl}       {sh}|{cl}
{sh}| (O)   {cl}[#333333]|      | {gr}{st:^11}{cl} |      |{cl}   (O) {sh}|{cl}
{sh}|_______|______|_____________________|______|_______|{cl}
        """
        self.update(cassette_art) # Renders the art to the terminal

# Custom Textual Widget for the single-line "Now Playing" text
class NowPlaying(Static):
    def update_track(self, artist: str, title: str):
        # Formats the track details with colors
        self.update(f"[bold {COLORS['accent']}]{escape(title)}[/]  [dim]by[/]  [bold]{escape(artist)}[/]")

# Custom Textual Widget for the horizontal time/progress bar
class ProgressBar(Static):
    def on_mount(self):
        # Refreshes the progress bar every 0.2 seconds
        self.set_interval(0.2, self.update_bar)

    def update_bar(self):
        try:
            # Check if pygame audio engine is running and actively playing a song
            if mixer.get_init() and mixer.music.get_busy():
                curr = self.app._current_time()
                total = float(getattr(self.app, "song_length", 0) or 0)
                if total > 0:
                    percent = min(curr / total, 1.0)
                    width = max(self.size.width - 15, 10) # Calculate available terminal width
                    filled = int(width * percent)
                    
                    # Create the physical bar string (e.g., ━━━╸──────)
                    bar = "━" * filled + "╸" + "─" * (width - filled - 1)
                    
                    # Convert raw seconds into Minutes:Seconds format
                    m1, s1 = divmod(int(curr), 60)
                    m2, s2 = divmod(int(total), 60)
                    
                    self.update(f"[{COLORS['accent']}]{bar}[/] {m1}:{s1:02d}/{m2}:{s2:02d}")
                    return
            
            # Fallback display if no music is playing
            self.update(f"[grey37]{'─' * (self.size.width - 15)}[/] 0:00/0:00")
        except: pass

# The Main Application Class
class CassettePlayer(App):
    TITLE = "CassettePlayer"
    
    # CSS definitions for layout and styling
    CSS = f"""
    Screen {{ background: {COLORS['bg']}; color: white; }}
    #main-container {{ height: 100%; padding: 1 2; }}
    #sidebar {{ width: 30%; border: double {COLORS['border']}; padding: 0 1; }}
    #player-view {{ width: 70%; align: center middle; }}
    #cassette-container {{ height: 16; align: center middle; }}
    #progress {{ height: 1; content-align: center middle; margin-bottom: 1; }}
    .list-header {{ background: {COLORS['accent']}; color: black; text-align: center; margin: 1 0; text-style: bold; }}
    #controls {{ height: 3; content-align: center middle; color: {COLORS['border']}; }}
    #now-playing {{ height: 1; text-align: center; margin-bottom: 1; }}
    ListItem {{ padding: 0 1; }}
    ListItem:focus {{ background: {COLORS['accent']}; color: black; }}
    """

    # Global keyboard shortcuts mappings
    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("q", "quit", "Quit"),
        Binding("right", "seek_forward", "+5s"),
        Binding("left", "seek_backward", "-5s"),
    ]

    # Defines the structure/layout of the application (DOM equivalent)
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Horizontal(): # Side-by-side layout
                # Left side: Playlist
                with Vertical(id="sidebar"):
                    yield Static("LIBRARY", classes="list-header")
                    self.track_list = ListView(id="track-queue")
                    yield self.track_list

                # Right side: Cassette player, Now Playing, and Progress bar
                with Vertical(id="player-view"):
                    with Container(id="cassette-container"):
                        self.cassette = Cassette()
                        yield self.cassette
                    
                    self.now_playing = NowPlaying(id="now-playing")
                    yield self.now_playing
                    
                    yield ProgressBar(id="progress")
                    yield Static("【 REW 】 【 PLAY 】 【 PAUSE 】 【 FF 】", id="controls")
        yield Footer()

    # Runs right after the UI finishes initializing
    def on_mount(self):
        mixer.init() # Initialize the pygame audio engine
        self.current_file = None
        self.play_offset = 0.0
        self.song_length = 0
        self.load_music() # Read directory files into the list
        self.track_list.focus() # Make the list keyboard-controllable immediately
        self.cassette.update_widget(status="READY")

    # Scans the MUSIC_PATH directory for audio files
    def load_music(self):
        extensions = ["*.mp3", "*.flac", "*.wav"]
        tracks = []
        for ext in extensions:
            # Find all files matching the extensions recursively
            tracks.extend(list(Path(MUSIC_PATH).rglob(ext)))
            
        for track in tracks:
            try:
                audio = MutagenFile(track)
                if not audio: continue
                artist = "Unknown Artist"
                title = track.stem # Default to filename if no metadata exists
                
                # Metadata tags are different for MP3 vs FLAC/WAV
                if track.suffix.lower() == ".mp3":
                    artist = audio.get('TPE1', ['Unknown Artist'])[0]
                    title = audio.get('TIT2', [track.stem])[0]
                else:
                    artist = audio.get('artist', ['Unknown Artist'])[0]
                    title = audio.get('title', [track.stem])[0]
                
                # Create a visual list item for the sidebar
                item = ListItem(Static(f"♫ {str(title)[:20]}"))
                # Attach custom data directly to the list item object for later retrieval
                item.file_path = str(track)
                item.track_title = str(title)
                item.track_artist = str(artist)
                self.track_list.append(item)
            except: 
                continue # Skip unreadable files silently

    # Helper method to calculate real time. Pygame resets time when seeking, 
    # so we add our offset to whatever pygame says its current time is.
    def _current_time(self) -> float:
        if not mixer.get_init() or not mixer.music.get_busy():
            if not self.cassette.is_playing: return self.play_offset
        return self.play_offset + max(mixer.music.get_pos() / 1000, 0.0)

    # Event handler: Runs when the user presses Enter on a song in the ListView
    def on_list_view_selected(self, event: ListView.Selected):
        file_path = event.item.file_path
        try:
            # Load and play the file via pygame
            mixer.music.load(file_path)
            mixer.music.play()
            
            # Extract duration metadata
            audio = MutagenFile(file_path)
            self.song_length = audio.info.length if audio and audio.info else 0
            
            # Reset player state variables
            self.current_file = file_path
            self.play_offset = 0.0
            
            # Update the UI components
            self.now_playing.update_track(event.item.track_artist, event.item.track_title)
            self.cassette.is_playing = True
            self.cassette.update_widget(status="PLAYING", title=event.item.track_title)
        except Exception as e:
            self.notify(str(e), severity="error")

    # Action mapped to "Spacebar"
    def action_toggle_play(self):
        if not self.current_file: return
        
        # Toggle between pause and unpause based on current state
        if self.cassette.is_playing:
            mixer.music.pause()
            self.cassette.is_playing = False
            self.cassette.update_widget(status="PAUSED")
        else:
            mixer.music.unpause()
            self.cassette.is_playing = True
            self.cassette.update_widget(status="PLAYING")

    # Action mapped to "Right Arrow"
    def action_seek_forward(self):
        self._seek_to(self._current_time() + 5)

    # Action mapped to "Left Arrow"
    def action_seek_backward(self):
        self._seek_to(self._current_time() - 5)

    # Internal method handling the complexities of fast-forwarding/rewinding
    def _seek_to(self, position: float):
        if not self.current_file: return
        # Clamp the seek target between 0 and the total song length
        pos = max(0, min(position, self.song_length))
        
        # Pygame requires stopping, reloading, and playing from a designated start time
        mixer.music.stop()
        mixer.music.load(self.current_file)
        mixer.music.play(start=pos)
        
        # Keep track of where we skipped to so the progress bar calculates correctly
        self.play_offset = pos
        self.cassette.is_playing = True

    # Action mapped to the "n" key
    def action_next_track(self):
        if self.track_list.children:
            # Calculate next index (looping back to 0 if at the end of the playlist)
            current_idx = self.track_list.index if self.track_list.index is not None else -1
            idx = (current_idx + 1) % len(self.track_list.children)
            
            # Update the UI focus/highlight to the new song
            self.track_list.index = idx
            
            # Get the specific ListItem object
            selected_item = self.track_list.children[idx]
            
            # Manually trigger your selection logic as if the user clicked it
            # We create the message with the required 'index' argument
            self.on_list_view_selected(ListView.Selected(self.track_list, selected_item, idx))

# Python entry point: Start the Textual app if script is run directly
if __name__ == "__main__":
    CassettePlayer().run()