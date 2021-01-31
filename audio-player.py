from functools import partial
import json
import os
from os import listdir
from os.path import join
import random
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
from tkinter import *
from tkinter import filedialog, messagebox, \
                    ttk, scrolledtext
import webbrowser

# Set this to not to print pygame message.
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import audio_metadata
from io import BytesIO
import lyricsgenius as lg
from mutagen.mp3 import MP3
from pygame import mixer
from PIL import ImageTk, Image, ImageFilter, \
                ImageFont, ImageDraw, ImageEnhance
import requests
from ttkthemes import themed_tk as thk


class MusicPlayer:

    def __init__(self, master):
        """Initialize and configure root window widgets"""

        # Connect to database of playlists and initialize a cursor.
        self.conn = sqlite3.connect('db/playlists.db')
        self.c = self.conn.cursor()

        # Define self.master with a value of the root window.
        self.master = master
        self.master.protocol('WM_DELETE_WINDOW', self.closing)

        # Initialize the top menubar
        self.menubar = Menu(self.master)
        self.master.config(menu=self.menubar)

        self.file_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label='File', menu=self.file_menu)
        self.file_menu.add_command(
            label='Open file...',
            command=partial(self.browse_file, 'Open file'),
            accelerator='Ctrl+O',
        )
        self.master.bind_all('<Control-o>', self.browse_file)
        self.file_menu.add_command(
            label='Open folder...',
            command=partial(self.browse_directory, 'Open directory'),
            accelerator='Ctrl+Shift+O',
        )
        self.master.bind_all('<Control-O>', self.browse_directory)
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Save now playing list as...',
            command=self.save_playlist,
            accelerator='Ctrl+S',
        )
        self.master.bind_all('<Control-s>', self.save_playlist)
        self.file_menu.add_command(
            label='My playlists',
            command=partial(self.show_playlists, 'My playlists'),
            accelerator='Ctrl+P',
        )
        self.master.bind_all('<Control-p>', self.show_playlists)
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label='Exit', command=self.master.destroy, accelerator='Ctrl+Q'
        )
        self.master.bind_all('<Control-q>', self.closing)

        self.helpmenu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label='Help', menu=self.helpmenu)
        self.helpmenu.add_command(label='About', command=self.about)

        # Initialize frames
        self.playing_list_frame = Frame(self.master)
        self.playing_list_frame.pack(side='right', padx=30)

        self.playing_listbox_frame = Frame(self.playing_list_frame)
        self.playing_listbox_frame.pack()

        self.playing_list_buttons_frame = Frame(self.playing_list_frame)

        self.playlist_buttons_frame = Frame(self.playing_list_frame)

        self.player_frame = Frame(self.master)
        self.player_frame.pack(pady=30)

        self.player_top_frame = Frame(self.player_frame)
        self.player_top_frame.pack()

        self.player_middle_frame = Frame(self.player_frame)
        self.player_middle_frame.pack(pady=15)

        self.player_bottom_frame = Frame(self.player_frame)
        self.player_bottom_frame.pack()

        # Get the default color of the root window.
        self.default_bg = self.master.cget('bg')

        # Initialize and configure a general style for label widgets.
        ttk.Style().configure(
            'playlist_name_label.TLabel',
            background=self.default_bg,
            font=('Nirmala UI', 12)
        )

        # Initialize playing list listbox, a label and some button
        # widgets related to the listbox.
        self.paused = False
        self.playing_list = []
        self.playing_song_ix = 0
        self.playing_listbox = Listbox(
            self.playing_listbox_frame, selectforeground='white',
            activestyle='dotbox', selectbackground='grey',
            foreground='black', width=50,
            selectmode='single', height=20,
        )
        self.playing_listbox.bind('<Double-1>', self.play_or_pause)
        self.playing_listbox.bind('<Button-3>', self.do_popup)
        self.playing_listbox.bind('<Down>', self.change_selection)
        self.playing_listbox.bind('<Up>', self.change_selection)
        self.playing_listbox.bind('<Return>', self.play_or_pause)
        self.playing_listbox.grid(row=0, column=0)

        self.y_scrollbar = ttk.Scrollbar(
            self.playing_listbox_frame, orient='vertical'
        )
        self.y_scrollbar.grid(row=0, column=1, sticky='nsew')
        self.x_scrollbar = ttk.Scrollbar(
            self.playing_listbox_frame, orient='horizontal'
        )
        self.x_scrollbar.grid(row=1, column=0, sticky='nsew')

        self.playing_listbox.config(
            yscrollcommand=self.y_scrollbar.set,
            xscrollcommand=self.x_scrollbar.set
        )

        self.y_scrollbar.config(command=self.playing_listbox.yview)
        self.x_scrollbar.config(command=self.playing_listbox.xview)

        self.playing_list_name = ttk.Label(
            self.playing_list_frame, text='', style='playlist_name_label.TLabel'
        )
        self.playing_list_name.pack(pady=10)

        self.add_file_button = ttk.Button(
            self.playing_list_buttons_frame,
            text='Add file',
            command=partial(self.browse_file, 'Open file'),
            width=14,
        )
        self.add_file_button.grid(row=0, column=1)

        self.add_directory_button = ttk.Button(
            self.playing_list_buttons_frame,
            text='Add folder',
            command=partial(self.browse_directory, 'Open directory'),
            width=14,
        )
        self.add_directory_button.grid(row=0, column=0)

        self.clear_list_button = ttk.Button(
            self.playing_list_buttons_frame,
            text='Clear list',
            command=self.clear_playing_list,
            width=14,
        )
        self.clear_list_button.grid(row=0, column=2)

        # Initialize two button widgets for saving the playing list
        # and showing saved playlists.
        self.save_list_button = ttk.Button(
            self.playlist_buttons_frame,
            text='Save list',
            command=self.save_playlist,
            width=23,
        )
        self.save_list_button.grid(row=0, column=0)

        self.load_list_button = ttk.Button(
            self.playlist_buttons_frame,
            text='My playlists',
            command=partial(self.show_playlists, 'My playlists'),
            width=23,
        )
        self.load_list_button.grid(row=0, column=1)

        # Initialize a menu that pops up on right clicking
        # on the listbox items.
        self.listbox_menu = Menu(root, tearoff=0)
        self.listbox_menu.add_command(label='Play', command=self.play_or_pause)
        self.listbox_menu.add_command(
            label='Add to playlist',
            command=partial(self.show_playlists, 'Add to playlist'),
        )
        self.listbox_menu.add_separator()
        self.listbox_menu.add_command(
            label='Remove from list', command=self.remove_song
        )
        self.listbox_menu.add_command(
            label='Move up', command=partial(self.move_item, 'Up')
        )
        self.listbox_menu.add_command(
            label='Move down', command=partial(self.move_item, 'Down')
        )
        self.listbox_menu.add_command(
            label='Clear list', command=self.clear_playing_list
        )
        self.listbox_menu.add_separator()
        self.listbox_menu.add_command(
            label='Open file location', command=self.open_directory
        )

        self.playing_list_buttons_frame.pack()
        self.playlist_buttons_frame.pack(pady=23)

        # Initialize song length and current time label widgets.
        self.music_ended = False
        self.timeline_changed = False
        
        ttk.Style().configure('Time.TLabel', background=self.default_bg)

        self.current_time_label = ttk.Label(
            self.player_middle_frame, text='__:__', style='Time.TLabel'
        )
        self.current_time_label.grid(row=0, column=0, padx=5)

        self.time_separator = ttk.Label(
            self.player_middle_frame, text='/', style='Time.TLabel'
        )
        self.time_separator.grid(row=0, column=1)

        self.total_length_label = ttk.Label(
            self.player_middle_frame, text='__:__', style='Time.TLabel'
        )
        self.total_length_label.grid(row=0, column=2, padx=5)

        # Initialize player panel widgets (the empty label widget is for
        # filling the white space on the right side of the buttons).
        self.playing = False
        self.playing_song = ''
        self.play_photoimage = PhotoImage(file='png/play-24.png')
        self.pause_photoimage = PhotoImage(file='png/pause-24.png')
        self.play_button = ttk.Button(
            self.player_middle_frame,
            image=self.play_photoimage,
            command=self.play_or_pause
        )
        self.play_button.grid(row=0, column=4, padx=0)

        self.file_name = ''
        self.next_photoimage = PhotoImage(file='png/next-16.png')
        self.next_button = ttk.Button(
            self.player_middle_frame,
            image=self.next_photoimage,
            command=self.next_music
        )
        self.next_button.grid(row=0, column=5, padx=5)

        self.previous_photoimage = PhotoImage(file='png/previous-16.png')
        self.previous_button = ttk.Button(
            self.player_middle_frame,
            image=self.previous_photoimage,
            command=self.previous_music
        )
        self.previous_button.grid(row=0, column=3, padx=5)

        self.empty_label = Label(self.player_middle_frame, text='') 
        self.empty_label.grid(row=0, column=6, padx=40)

        # Initialize Genius and Youtube buttons respectively
        # for showing the lyrics for playing song and searching
        # for the song in Youtube website in the browser.
        self.genius_photoimage = PhotoImage(file='png/genius-16.png')
        self.genius_button = ttk.Button(
            self.player_bottom_frame,
            image=self.genius_photoimage,
            command=self.show_lyrics,
            width=18,
        )
        self.genius_button.grid(row=0, column=0, padx=5)
        self.create_tooltip(
            widget=self.genius_button, text='Show Lyrics'
        )

        self.youtube_photoimage = PhotoImage(file='png/youtube-16.png')
        self.youtube_button = ttk.Button(
            self.player_bottom_frame,
            image=self.youtube_photoimage,
            command=self.video_search,
            width=18,
        )
        self.youtube_button.grid(row=0, column=1)
        self.create_tooltip(
            widget=self.youtube_button, text='Search for Video'
        )

        # Initialize widgets for volume adjustment.
        self.muted = False
        self.muted_photoimage = PhotoImage(file='png/muted-16.png')
        self.volume_high_photoimage = PhotoImage(file='png/volume-high-16.png')
        self.volume_low_photoimage = PhotoImage(file='png/volume-low-16.png')
        self.volume_button = ttk.Button(
            self.player_bottom_frame,
            image=self.volume_high_photoimage,
            command=self.mute_music
        )
        self.volume_button.grid(row=0, column=5, padx=5)

        ttk.Style().configure(
            'Horizontal.TScale', background=self.default_bg
        )

        self.volume_scale = ttk.Scale(
            self.player_bottom_frame, from_=0, to=100,
            orient='horizontal', command=self.set_volume,
        )
        self.volume_scale.set(50)
        mixer.music.set_volume(0.5)
        self.volume_scale.grid(row=0, column=6)

        # Initialize checkbutton widgets
        ttk.Style().configure(
            'Checkbutton.TCheckbutton', background=self.default_bg
        )

        self.shuffle = False
        self.shuffle_checkbutton_var = IntVar()
        self.shuffle_photo = PhotoImage(file='png/shuffle-16.png')
        self.shuffle_checkbutton = ttk.Checkbutton(
            self.player_bottom_frame, image=self.shuffle_photo,
            variable=self.shuffle_checkbutton_var, width=10,
            command=self.set_shuffle, offvalue=0,
            style='Checkbutton.TCheckbutton', onvalue=1,
        )
        self.shuffle_checkbutton.grid(row=0, column=3, padx=0)
        self.create_tooltip(
            self.shuffle_checkbutton, text='Turn Shuffle on'
        )

        self.repeat = False
        self.repeat_checkbutton_var = IntVar()
        self.repeat_photo = PhotoImage(file='png/repeat-16.png')
        self.repeat_checkbutton = ttk.Checkbutton(
            self.player_bottom_frame, image=self.repeat_photo,
            variable=self.repeat_checkbutton_var, width=10,
            command=self.set_repeat, offvalue=0,
            style='Checkbutton.TCheckbutton', onvalue=1,
        )
        self.repeat_checkbutton.grid(row=0, column=4, padx=0)
        self.create_tooltip(
            self.repeat_checkbutton, text='Turn repeat on'
        )

        self.tags_checkbutton_var = IntVar()
        self.tags_photo = PhotoImage(file='png/info-16.png')
        self.tags_checkbutton = ttk.Checkbutton(
            self.player_bottom_frame, image=self.tags_photo,
            variable=self.tags_checkbutton_var, width=10,
            command=self.show_file_tags, offvalue=0,
            style='Checkbutton.TCheckbutton', onvalue=1,
        )
        self.tags_checkbutton.grid(row=0, column=2, padx=5)
        self.create_tooltip(
            widget=self.tags_checkbutton, text='Show song tags'
        )

        # Initialize artwork, title and artists of the playing song
        # label widgets.
        ttk.Style().configure(
            'Filetitle.TLabel', foreground='black',
            font=('Nirmala UI', 14), background=self.default_bg,
        )
        ttk.Style().configure(
            'Fileartists.TLabel', foreground='grey',
            font=('Nirmala UI', 12), background=self.default_bg,
        )

        self.artwork_path = 'png/default-music-artwork-324.png'
        self.artwork_photoimage = PhotoImage(file=self.artwork_path)
        self.artwork_label = ttk.Label(
            self.player_top_frame, image=self.artwork_photoimage
        )
        self.artwork_label.grid(row=0, column=1)

        self.file_title_label = ttk.Label(
            self.player_top_frame,
            text='Nothing playing',
            style='Filetitle.TLabel'
        )
        self.file_title_label.grid(row=1, column=1, pady=10)

        self.file_artists_label = ttk.Label(
            self.player_top_frame,
            text='',
            style='Fileartists.TLabel'
        )
        self.file_artists_label.grid(row=2, column=1)

        self.tags_keys_list = [
            'title', 'album', 'albumartist', 'artist',
            'composer', 'date', 'tracknumber', 'genre',
        ]
        self.tags_names_list = [
            'Title', 'Album', 'Album Artist', 'Artist',
            'Composer', 'Year', 'Track Number', 'Genre',
        ]
        self.file_tags_dict = {}

        # Some variables with a value of errors that
        # will be used for error message boxes.
        self.file_not_found = 'Junkie player could not find the file. Please check and try again.'
        self.no_song_selected = 'Junkie player could not recognize any selected song. Please check and try again.'
        self.track_type_invalid = 'Junkie player does not support this track type. Please check and try again.'
        self.no_playlist_selected = 'Junkie player could not find the playlist. Please check and try again.'
        self.playlist_empty = 'Junkie player could not find any items in current playlist. Please check and try again.'
        self.file_info_not_found = 'Junkie player could not find the file info. Please check and try again.'
        self.api_access_error = 'Junkie player could not access to the API. Please check and try again.'
        self.connection_error = 'Junkie player could not connect to the internet. Please check your connection and try again.'
        self.lyrics_not_found = 'Junkie player could not find the lyrics. Please check and try again.'

        self.tip_window = None

    def add_to_playing_list(self, file_path):
        """Add songs to playing list."""
        file_name = os.path.basename(file_path)
        global index
        if self.playing_list == []:
            index = 0
        self.playing_listbox.insert(index, ' ' + file_name)
        if file_path != '':
            self.playing_list.insert(index, file_path)
            index += 1

    def browse_file(self, event):
        """Open file browser and add the selected file to playing list."""
        file_path = filedialog.askopenfilename()
        if file_path.endswith('.wav') or file_path.endswith('.mp3'):
            # Since filepath is not empty (File browse not cancelled)
            # and the type of selected file is MP3 Format Sound we can
            # add it to playing list.
            self.add_to_playing_list(file_path)
            self.playing_list_name['text'] = 'Unsaved list'

    def browse_directory(self, event):
        """
        Open directory browser and add all files of type mp3,
        inside the selected directory to playing list.
        """
        dir_path = filedialog.askdirectory()
        if dir_path != '':
            # Since filepath is not empty (File browse not cancelled)
            # we can pick the files of type mp3 and add them
            # to playing list.
            valid_files = [
                join(dir_path, f).replace('\\', '/')
                for f in listdir(dir_path)
                if f.endswith('.mp3') or f.endswith('.wav')
            ]
            for file in valid_files:
                self.add_to_playing_list(file)
            self.playing_list_name['text'] = 'Unsaved list'

    def remove_song(self):
        """Remove the selected song from playing list."""
        song_selection = self.playing_listbox.curselection()
        if len(song_selection) != 0:
            # Since a song is selected we can remove it from
            # playing list.
            selected_song_index = song_selection[0]
            self.playing_listbox.delete(selected_song_index)
            self.playing_list.pop(selected_song_index)
        else:
            # Otherwise we show an error message box.
            messagebox.showerror(
                'No song selected',
                self.no_song_selected,
            )

    def move_item(self, direction):
        """
        Move the song to upwards or downwards
        (according to the selected option) in
        playing list.
        """
        selected_song_index = self.playing_listbox.curselection()[0]
        if direction == 'Up':
            new_index = selected_song_index - 1
        elif direction == 'Down':
            new_index = selected_song_index + 1
        file_path = self.playing_list[selected_song_index]
        filename = os.path.basename(file_path)

        self.playing_listbox.delete(selected_song_index)
        self.playing_list.pop(selected_song_index)
        self.playing_listbox.insert(new_index, ' '+filename)
        self.playing_list.insert(new_index, file_path)
        self.playing_listbox.selection_set(new_index)

    def clear_playing_list(self, *args):
        """Clear playing list"""
        self.playing_listbox.delete(0, 'end')
        self.playing_list = []
        self.playing_list_name['text'] = 'Unsaved list'

    def set_repeat(self):
        """
        Set the value of self.repeat and the tooltip text according to
        repeat check button.
        """
        if self.repeat_checkbutton_var.get() == 0:
            self.repeat = False
            self.create_tooltip(
                widget=self.repeat_checkbutton, text='Turn repeat on'
            )
        elif self.repeat_checkbutton_var.get() == 1:
            self.repeat = True
            self.create_tooltip(
                widget=self.repeat_checkbutton, text='Turn repeat off'
            )

    def set_shuffle(self):
        """
        Set the value of self.shuffle and the tooltip text according to
        shuffle check button.
        """
        if self.shuffle_checkbutton_var.get() == 0:
            self.shuffle = False
            self.create_tooltip(
                widget=self.shuffle_checkbutton, text='Turn shuffle on'
            )
        elif self.shuffle_checkbutton_var.get() == 1:
            self.shuffle = True
            self.create_tooltip(
                widget=self.shuffle_checkbutton, text='Turn shuffle off'
            )

    def set_file_tags(self, file_metadata):
        """
        Define self.file_tags_dict, a dictionary containing tags of
        a song.
        """
        self.file_tags_dict = {}
        self.playing = True
        if self.playing:
            metadata_tags = file_metadata['tags']
            for key in self.tags_keys_list:
                if key in metadata_tags:
                    key_ix = self.tags_keys_list.index(key)
                    name = self.tags_names_list[key_ix]
                    self.file_tags_dict[name] = metadata_tags[key][0]

    def show_file_tags(self):
        """
        Show song tags (if there are any available) on the artwork of
        playing song according to file tags check button. (In details,
        the artwork is edited with PIL module and song tags are
        added as text on the image, and finally it shows the new
        (edited) artwork.)
        """
        if self.tags_checkbutton_var.get() == 1:
            self.create_tooltip(
                widget=self.tags_checkbutton, text='Hide song tags'
            )
            if self.artwork_path == 'png/default-music-artwork-324.png':
                img = Image.open('png/default-music-artwork-324.png')
                blur_img = img.filter(ImageFilter.GaussianBlur(radius=4))
                blur_path = 'png/default-music-artwork-324-blur.png'
                blur_img.save(blur_path)
                self.artwork_photoimage = PhotoImage(file=blur_path)
            elif self.artwork_path == 'png/artwork.png':
                img = Image.open('png/artwork.png')
                blur_img = img.filter(ImageFilter.GaussianBlur(radius=4))
                blur_path = 'png/artwork-blur.png'
                blur_img.save(blur_path)
                self.artwork_photoimage = PhotoImage(file=blur_path)
            blur_img = Image.open(blur_path)
            enhancer = ImageEnhance.Contrast(blur_img)
            enhence_output = enhancer.enhance(0.5)
            enhence_output.save(blur_path)
            if self.file_tags_dict != {}:
                blur_img = Image.open(blur_path)
                image_editable = ImageDraw.Draw(blur_img)
                keys_font = ImageFont.truetype('NIRMALA.TTF', 14)
                values_font = ImageFont.truetype('NIRMALAB.TTF', 14)
                for ix, key in enumerate(self.file_tags_dict):
                    value = self.file_tags_dict[key]
                    if len(value) > 26:
                        value = value[:26] + ' ...'
                    keys_coordinates = (15, 15+(20*ix))
                    values_coordinates = (108, 15+(20*ix))
                    image_editable.text(
                        xy=keys_coordinates, text=key,
                        fill=(255, 255, 255), font=keys_font,
                    )
                    image_editable.text(
                        xy=values_coordinates, text=value,
                        fill=(255, 255, 255), font=values_font,
                    )
                blur_img.save(blur_path)
            else:
                blur_img = Image.open(blur_path)
                image_editable = ImageDraw.Draw(blur_img)
                font = ImageFont.truetype('NIRMALAB.TTF', 14)
                coordinates = (108, 15)
                text = 'No tags available.'
                image_editable.text(
                    xy=coordinates, text=text,
                    fill=(255, 255, 255), font=font
                )
                blur_img.save(blur_path)

            self.artwork_photoimage = PhotoImage(file=blur_path)
            self.artwork_label.configure(image=self.artwork_photoimage)
        elif self.tags_checkbutton_var.get() == 0:
            self.create_tooltip(
                widget=self.tags_checkbutton, text='Show song tags'
            )
            self.artwork_photoimage = PhotoImage(file=self.artwork_path)
            self.artwork_label.configure(image=self.artwork_photoimage)

    def show_file_info(self, playing_song):
        """
        Get the metadata of playing song using audio_metadata module
        and set the artwork, song title and song artists label widgets
        using the metadata.
        """
        self.file_name = os.path.basename(playing_song)
        self.tags_checkbutton_var.set(0)
        if len(self.file_name) > 17:
            # To not to mess up widgets positions we put '...' in
            # the end of the file name, if it's long.
            self.file_name = textwrap.shorten(
                self.file_name, width=40, placeholder=" ..."
            )
        file_metadata = audio_metadata.load(playing_song)
        self.set_file_tags(file_metadata)
        try:
            artwork = file_metadata.pictures[0].data
            artwork_stream = BytesIO(artwork)
            img = Image.open(artwork_stream)
            # Check width and height of the image and resize it.
            if img.size[0] <= img.size[1]:
                base_height = 324
                resize_percent = base_height / float(img.size[1])
                width_size = int((float(img.size[0]) * float(resize_percent)))
                img = img.resize((width_size, base_height), Image.ANTIALIAS)
            elif img.size[0] > img.size[1]:
                base_width = 324
                resize_percent = base_width / float(img.size[0])
                height_size = int((float(img.size[1]) * float(resize_percent)))
                img = img.resize((base_width, height_size), Image.ANTIALIAS)
            img.save('png/artwork.png')
            self.artwork_path = 'png/artwork.png'
            with open(self.artwork_path, 'rb') as image:
                # convert image to byte array to make a stream with
                # BytesIO.
                f = image.read()
                b = bytearray(f)
            artwork_stream = BytesIO(b)
            self.artwork_photoimage = PhotoImage(file=self.artwork_path)
            self.artwork_label.configure(image=self.artwork_photoimage)

            file_title = file_metadata['tags']['title'][0]
            self.file_title_label.config(text=file_title)

            file_artists = file_metadata['tags']['artist'][0]
            self.file_artists_label.config(text=file_artists)
        except (IndexError, KeyError):
            # If either of artwork, title or artists were not found in
            # metadata, set the artwork label with the default value,
            # song title label with the value of file name and
            # song artists with the value of 'Unknown artist'.
            self.artwork_path = 'png/default-music-artwork-324.png'
            self.artwork_photoimage = PhotoImage(file=self.artwork_path)
            self.artwork_label.configure(image=self.artwork_photoimage)

            file_title = self.file_name
            self.file_title_label.config(text=file_title)

            file_artists = 'Unknown artist'
            self.file_artists_label.configure(text=file_artists)

    def show_details(self, playing_song):
        """Show details for the playing song."""
        def get_total_length(playing_song):
            """
            Get the total length of playing song using mutagen.mp3
            module for file of type MP3 and pygame.mixer module for
            files of type WAV, and return it.
            """
            if playing_song.endswith('.mp3'):
                mp3_file = MP3(playing_song)
                total_length = mp3_file.info.length
            elif playing_song.endswith('.wav'):
                wav_file = mixer.Sound(playing_song)
                total_length = wav_file.get_length()
            else:
                messagebox.showerror(
                    'Track type invalid',
                    self.track_type_invalid,
                )
            return total_length

        def start_count():
            """
            start counting and calculating the current time and
            show it every second.
            """
            current_time = 0
            while True:
                while (
                    current_time < round(total_length)
                    and mixer.music.get_busy()
                ):
                    if self.paused:
                        continue
                    else:
                        if self.current_time_label == self.total_length_label:
                            self.next_music()
                            return False
                        mins, secs = divmod(current_time, 60)
                        mins, secs = round(mins), round(secs)
                        time_format = '{:02d}:{:02d}'.format(mins, secs)
                        self.current_time_label['text'] = time_format
                        time.sleep(1)
                        current_time += 1
                        if self.timeline_changed:
                            return False
                else:
                    if self.paused:
                        self.current_time_label['text'] = '00:00'
                        return False
                    else:
                        self.current_time_label['text'] = '00:00'
                        self.playing = False
                        self.music_ended = True
                        self.play_or_pause()
                    return False

        total_length = get_total_length(playing_song)
        mins, secs = divmod(total_length, 60)
        mins, secs = round(mins), round(secs)
        time_format = '{:02d}:{:02d}'.format(mins, secs)
        self.total_length_label['text'] = time_format
        if self.timeline_changed:
            # if the playing song changed, set the current time label
            # with the default value and make a thread for counting
            # and calculating the current time.
            self.current_time_label['text'] = '__:__'
            time_calculator_thread = threading.Thread(
                target=start_count, daemon=True
            )
            time_calculator_thread.start()
            self.timeline_changed = False
        self.show_file_info(playing_song)

    def play_or_pause(self, *args):
        """
        Play or pause the music according to the action that
        calls this function.
        """
        def change_image(image_path):
            """Change image of play/pause button."""
            button_photoimage = PhotoImage(file=image_path)
            self.play_button.configure(image=button_photoimage)
            self.play_button.image = button_photoimage
        def unpause():
            """Unpause music"""
            mixer.music.unpause()
            time.sleep(1)
            self.paused = False
            self.playing = True
            change_image(pause_photo)
        def play():
            """Play music"""
            try:
                if len(listbox_selection) != 0:
                    if (
                        self.music_ended == True
                        and self.music_ended != 'This is my first time!'
                    ):
                        # Since the playing song has been ended we check
                        # if there is a song in queue or not.
                        if self.playing_song_ix == len(self.playing_list)-1:
                            if not self.repeat and not self.shuffle:
                                # Since the ended song was the last one
                                # in queue, and repeat and shuffle are
                                # not enabled we set everything with
                                # the default value.
                                self.artwork_path = 'png/default-music-artwork-324.png'
                                self.artwork_photoimage = PhotoImage(file=self.artwork_path)
                                self.artwork_label.configure(image=self.artwork_photoimage)
                                self.file_title_label['text'] = 'Nothing playing'
                                self.file_artists_label['text'] = ''

                                self.total_length_label['text'] = '__:__'
                                self.current_time_label['text'] = '__:__'
                                change_image(play_photo)
                                
                                self.playing_listbox.select_clear(0, END)
                                self.playing_listbox.selection_set(0)
                                self.playing_listbox.see(0)

                                self.playing = False
                                self.paused = False
                                self.music_ended = 'This is my first time!'
                            else:
                                self.music_ended = 'This is my first time!'
                                self.next_music()
                                self.music_ended = False
                        else:
                            # Since there is another song or songs in
                            # queue we play it.
                            # 
                            # Notice that in self.next_music(),
                            # self.play_or_pause() has been called; so
                            # we set the value of self.music_ended
                            # 'This is my first time' to not to play
                            # the song in that turn; but after calling
                            # self.next_music we set it to False to play
                            # the song in this turn.
                            self.music_ended = 'This is my first time!'
                            self.next_music()
                            self.music_ended = False

                    elif listbox_selection != self.playing_song_ix:
                        # Since the user has selected another song than
                        # the playing one, we set the selected song as
                        # the value of self.playing_song to play it.
                        self.playing_song_ix = self.playing_listbox.curselection()[0]
                        self.playing_song = self.playing_list[self.playing_song_ix]
                        self.timeline_changed = True
                    time.sleep(1)
                    if self.music_ended == 'This is my first time!':
                        # As explained in a comment above, we pass
                        # the function to not to play the song twice.
                        pass
                    else:
                        # As explained in a comment above, we play
                        # the next song in queue, when the current
                        # song has been ended.
                        mixer.music.load(self.playing_song)
                        mixer.music.play()
                        self.show_details(self.playing_song)
                        change_image(pause_photo)
                        self.playing = True
                    self.music_ended = ''
                elif (
                    len(listbox_selection) == 0
                    and len(self.playing_list) != 0
                ):
                    # Since the playing list is not empty but no song
                    # has been selected we play the first song of queue.
                    self.playing_song_ix = 0
                    self.playing_song = self.playing_list[self.playing_song_ix]
                    self.playing_listbox.selection_set(self.playing_song_ix)
                    self.timeline_changed = True
                    time.sleep(1)
                    mixer.music.load(self.playing_song)
                    mixer.music.play()
                    self.show_details(self.playing_song)
                    change_image(pause_photo)
                    self.playing = True
                else:
                    # Otherwise we raise a NameError to enter
                    # the exception.
                    raise NameError
            except NameError:
                # Get info of the error and print it; then show an error
                # message box.
                exc_type, exc_obj, exc_tb = sys.exc_info()
                del exc_obj
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print('File "{}", line {}, error {}'.format(
                        fname, exc_tb.tb_lineno, exc_type))
                messagebox.showerror(
                    'File not found',
                    self.file_not_found,
                )
        def pause():
            """Pause music"""
            try:
                time.sleep(1)
                self.timeline_changed = False
                mixer.music.pause()
                self.paused = True
                self.playing = False
                change_image(play_photo)
            except:
                messagebox.showerror(
                    'File not found',
                    self.file_not_found,
                )

        if len(args) > 0:
            self.playing = False
            self.timeline_changed = True
        if (
            self.playing_song != ''
            and self.playing_song in self.playing_list
        ):
            self.playing_song_ix = self.playing_list.index(self.playing_song)
        else:
            self.playing_song_ix = None
        listbox_selection = self.playing_listbox.curselection()
        if (
            len(listbox_selection) != 0
            and listbox_selection[0] != self.playing_song_ix
        ):
            self.timeline_changed = True
        play_photo = self.play_photoimage['file']
        pause_photo = self.pause_photoimage['file']
        if self.paused == True:
            if self.timeline_changed:
                # Since the music is paused but the playing song
                # has been changed we play the new song.
                self.paused = False
                play()
            else:
                # Since the music is paused and the playing song
                # has not been changed, we unpause it.
                unpause()
        elif not self.playing and not self.paused:
            # Since no song is being played and therefore
            # nothing is paused we play the new song
            # according to the action of user.
            play()
        elif self.playing and not self.paused:
            # Since a song is playing and not paused, we pause it.
            pause()

    def next_music(self):
        """Set the next song and play it."""
        def set_next(selected_song_ix, next_song_ix):
            """Set the next song"""
            self.playing_song = self.playing_list[next_song_ix]
            self.playing_listbox.select_clear(selected_song_ix, 'end')
            self.playing_listbox.selection_set(next_song_ix)
        listbox_selection = self.playing_listbox.curselection()
        if (
            self.playing_song != ''
            and self.playing_song in self.playing_list
        ):
            # Since the playing list is not empty and includes
            # the currently playing song, we set the next song
            # to play it.
            if len(listbox_selection) != 0:
                selected_song_ix = listbox_selection[0]
            else:
                selected_song_ix = None
            playing_song_ix = self.playing_list.index(self.playing_song)
            if selected_song_ix != None:
                if not self.repeat and not self.shuffle:
                    if playing_song_ix == len(self.playing_list)-1:
                        set_next(selected_song_ix, 0)
                    else:
                        set_next(selected_song_ix, playing_song_ix+1)
                else:
                    if self.repeat and not self.shuffle:
                        if playing_song_ix == len(self.playing_list)-1:
                            set_next(selected_song_ix, 0)
                        else:
                            set_next(selected_song_ix, playing_song_ix+1)
                    elif self.shuffle:
                        while True:
                            next_song_ix = random.randrange(len(self.playing_list))
                            if next_song_ix == playing_song_ix:
                                pass
                            else:
                                break
                        set_next(selected_song_ix, next_song_ix)
                self.playing = False
                if len(listbox_selection) > 0:
                    # if the next song is not in sight scroll listbox so
                    # the user can see it.
                    index = self.playing_listbox.curselection()[0]
                    self.playing_listbox.see(index)
                self.timeline_changed = True
                self.play_or_pause()

    def previous_music(self):
        """Set the previous song and play it."""
        def set_previous(selected_song_ix, previous_song_ix):
            """Set the previous song"""
            self.playing_song = self.playing_list[previous_song_ix]
            self.playing_listbox.select_clear(selected_song_ix, 'end')
            self.playing_listbox.selection_set(previous_song_ix)
        listbox_selection = self.playing_listbox.curselection()
        if (
            self.playing_song != ''
            and self.playing_song in self.playing_list
        ):
            # Since the playing list is not empty and includes
            # the currently playing song, we set the previous song
            # to play it.
            #
            # Notice that this function works the same as
            # self.next_music() when shuffle is enabled.
            if len(listbox_selection) != 0:
                selected_song_ix = listbox_selection[0]
            else:
                selected_song_ix = None
            playing_song_ix = self.playing_list.index(self.playing_song)
            if selected_song_ix != None:
                if not self.shuffle:
                    if playing_song_ix == 0:
                        set_previous(selected_song_ix, len(self.playing_list)-1)
                    else:
                        set_previous(selected_song_ix, playing_song_ix-1)
                else:
                    while True:
                        previous_song_ix = random.randrange(len(self.playing_list))
                        if previous_song_ix == playing_song_ix:
                            pass
                        else:
                            break
                    set_previous(selected_song_ix, previous_song_ix)
                self.playing = False
                if len(listbox_selection) > 0:
                    # if the next song is not in sight scroll listbox so
                    # the user can see it.
                    index = self.playing_listbox.curselection()[0]
                    self.playing_listbox.see(index)
                self.timeline_changed = True
                self.play_or_pause()

    def set_volume(self, val):
        """
        Set the volume of music according to the value of
        volume scale widget.
        """
        volume = float(val) / 100
        mixer.music.set_volume(volume)
        if volume == 0:
            self.volume_button.config(image=self.muted_photoimage)
        elif 0.5 > volume > 0:
            self.volume_button.config(image=self.volume_low_photoimage)
        else:
            self.volume_button.config(image=self.volume_high_photoimage)

    def mute_music(self):
        """Mute or unmute music according to the current state."""
        if not self.muted:
            self.last_volume = int(self.volume_scale.get())
            mixer.music.set_volume(0)
            self.volume_button.config(image=self.muted_photoimage)
            self.volume_scale.set(0)
            self.muted = True
        else:
            decimal_volume = float(self.last_volume) / 100
            mixer.music.set_volume(decimal_volume)
            self.volume_button.config(image=self.volume_high_photoimage)
            self.volume_scale.set(self.last_volume)
            self.muted = False

    def create_table(self):
        """
        Create table 'playlists' inside the database file
        'playlists.db', if it does not exist.
        """
        def check_table_existence():
            # Check if table 'playlists' exists.
            self.c.execute(
                """SELECT count(name) FROM sqlite_master
                   WHERE type=:type AND name=:name""",
                {'type': 'table', 'name': 'playlists'},
            )
            if self.c.fetchone()[0] == 1:
                return True
            else:
                return False

        table_exists = check_table_existence()
        if table_exists:
            pass
        else:
            with self.conn:
                self.c.execute(
                    """CREATE TABLE playlists (
                            name text,
                            files text)"""
                )
            print('DATABASE: TABLE "{}" CREATED.')

    def check_playlist_existence(self, name):
        """
        Check if the playlist with name 'name' parameter exists inside
        the database.
        """
        self.c.execute(
            'SELECT count(name) FROM playlists WHERE name=:name',
            {'name': name}
        )
        if self.c.fetchone()[0] == 1:
            return True
        else:
            return False

    def insert_playlist(self, name, files_list):
        """
        Insert a playlist with values 'name' and 'files_list'
        parameters into the database, if it does not exist.
        """
        playlist_exists = self.check_playlist_existence(name)
        if playlist_exists:
            pass
        else:
            files = json.dumps(files_list)
            with self.conn:
                self.c.execute(
                    'INSERT INTO playlists VALUES (:name, :files)',
                    {'name': name, 'files': files},
                )
            print('DATABASE: playlist "{}" INSERTED.'.format(name))

    def update_playlist(self, name, files_list):
        """
        Update the playlist with name 'name' parameter and set files
        'files_list' to it inside database. This function is called
        when user wants to add a song to a playlist.
        """
        files_str = json.dumps(files_list)
        with self.conn:
            self.c.execute(
                'UPDATE playlists SET files=:files WHERE name=:name',
                {'name': name, 'files': files_str},
            )
            print('DATABASE: playlist "{}" UPDATED.'.format(name))

    def get_playlist(self, name):
        """
        Get files list of the playlist with name 'name' parameter from
        database and return it, if it exists; Otherwise return None.
        """
        self.c.execute(
            'SELECT files FROM playlists WHERE name=:name',
            {'name': name}
        )
        files_str = self.c.fetchone()[0]
        if files_str == '[]':
            return []
        else:
            files_list = [
                i.replace('"', '')
                for i in files_str.strip('][').split(', ')
            ]
            return files_list

    def load_playlist(self, name, files_list):
        """
        Load playlist with name 'name' parameter and files
        'files_list' parameter.
        """
        self.clear_playing_list()
        for file in files_list:
            self.add_to_playing_list(file)
        self.playing_list_name['text'] = name
        if mixer.music.get_busy():
            self.timeline_changed = True
        self.stop_music()
        self.total_length_label['text'] = '__:__'
        self.current_time_label['text'] = '__:__'
        self.playing_listbox.selection_set(0)
        self.playing_song_ix = 0
        self.playing_song = ''
        self.playing = False
        self.play_or_pause()

    def open_directory(self):
        """Open location of the selected song in Windows Explorer."""
        selection_ix = self.playing_listbox.curselection()[0]
        path = self.playing_list[selection_ix].replace('/', '\\')
        subprocess.Popen(r'explorer /select,"{}"'.format(path))

    def change_selection(self, event):
        """Change selected song on pressing Up and Down arrow keys."""
        selection = self.playing_listbox.curselection()
        if len(selection) == 0:
            pass
        else:
            selection_index = selection[0]
            self.playing_listbox.select_clear(selection[0], 'end')
            if (
                event.keysym == 'Down'
                and selection_index < len(self.playing_list)-1
            ):
                self.playing_listbox.selection_set(selection_index+1)
            elif (
                event.keysym == 'Up'
                and selection_index != 0
            ):
                self.playing_listbox.selection_set(selection_index-1)
            else:
                self.playing_listbox.selection_set(selection_index)

    def show_playlists(self, *args):
        """Show saved playlists inside a top level window."""
        def load_list(*args):
            """Load the chosen playlist"""
            if len(playlists_listbox.curselection()) != 0:
                selected_listname_ix = playlists_listbox.curselection()[0]
                selected_listname = listnames[selected_listname_ix]
                files_list = self.get_playlist(selected_listname)
                new_window.grab_release()
                new_window.destroy()
                self.load_playlist(selected_listname, files_list)
            else:
                messagebox.showerror(
                    'No playlist selected',
                    self.no_playlist_selected,
                )
        def delete_playlist():
            """Delete the chosen playlist"""
            if len(playlists_listbox.curselection()) != 0:
                selected_listname_ix = playlists_listbox.curselection()[0]
                selected_listname = listnames[selected_listname_ix]
                self.c.execute(
                    'SELECT * FROM playlists WHERE name=:name',
                    {'name': selected_listname},
                )
                playlist = self.c.fetchone()
                with self.conn:
                    self.c.execute(
                        'DELETE from playlists WHERE name=? AND files=?',
                        playlist
                    )
                playlists_listbox.delete(selected_listname_ix)
            else:
                messagebox.showerror(
                    'No playlist selected',
                    self.no_playlist_selected,
                )
        def add_to_playlist(*args):
            """Add the selected song to the chosen playlist."""
            if len(playlists_listbox.curselection()) != 0:
                selected_listname_ix = playlists_listbox.curselection()[0]
                selected_listname = listnames[selected_listname_ix]
                files_list = self.get_playlist(selected_listname)
                files_list.append(selected_file)
                self.update_playlist(selected_listname, files_list)
                print('track "{}" added to playlist.'.format(selected_listname))
                new_window.grab_release()
                new_window.destroy()
        # Create a top level window and show playlists and
        # options inside it.
        new_window = Toplevel(self.master)
        new_window.title('Load playlist')
        new_window.iconbitmap('ico/junkie-audio-player-icon.ico')
        new_window.focus_force()
        new_window.grab_set()
        ttk.Style().configure(
            'Playlists.TLabel', foreground='black',
            font=('Nirmala UI', 14), background=self.default_bg,
        )
        playlists_label = ttk.Label(
            new_window, text='Your playlists', style='Playlists.TLabel'
        )
        playlists_label.pack(pady=10)
        playlists_listbox = Listbox(
            new_window, selectforeground='white',
            activestyle='dotbox', selectbackground='grey',
            selectmode='single', width=30,
            foreground='black', height=10,
        )
        playlists_listbox.pack(padx=15)
        if args[0] == 'Add to playlist':
            selected_file_ix = self.playing_listbox.curselection()[0]
            selected_file = self.playing_list[selected_file_ix]
            ttk.Button(
                new_window,
                text='Select playlist',
                command=add_to_playlist
            ).pack(pady=10)
            playlists_listbox.bind('<Double-1>', add_to_playlist)
        else:
            buttons_frame = Frame(new_window)
            buttons_frame.pack(pady=10)
            ttk.Button(
                buttons_frame,
                text='Delete playlist',
                command=delete_playlist
            ).grid(row=0, column=0)
            ttk.Button(
                buttons_frame,
                text='Load playlist',
                command=load_list
            ).grid(row=0, column=1)
            playlists_listbox.bind('<Double-1>', load_list)
        self.c.execute('SELECT name FROM playlists')
        fetched_data = self.c.fetchall()
        listnames = [i[0] for i in fetched_data]
        for listname in listnames:
            if listnames.index(listname) == 0:
                list_ix = 0
            playlists_listbox.insert(list_ix, ' ' + listname)
            list_ix += 1

    def save_playlist(self, *args):
        """Save the playing list inside the database."""
        def insert_list():
            """Insert the playing list into the database."""
            self.playing_list_name['text'] = name
            self.insert_playlist(name, self.playing_list)
            with self.conn:
                # Delete playlists which are the same, except one from
                # the database.
                self.c.execute(
                    """DELETE FROM playlists
                            WHERE ROWID NOT IN (SELECT MIN(ROWID)
                                                FROM playlists
                                                GROUP BY name)"""
                )
        def get_name():
            """
            Create a top level window and an entry widget inside it,
            to get a name for the playlist from user.
            """
            def set_name(var):
                # set the name of playlist according to
                # the text entered to the entry widget.
                if text.get() == '':
                    pass
                else:
                    global name
                    name = text.get()
                    insert_list()
                    new_window.grab_release()
                    new_window.destroy()

            new_window = Toplevel(self.master)
            new_window.title('Save playlist')
            new_window.iconbitmap('ico/junkie-audio-player-icon.ico')
            new_window.focus_force()
            new_window.grab_set()
            text = StringVar()
            ttk.Style().configure('new_window.TLabel', background=self.default_bg)
            ttk.Label(
                new_window, text='Choose a name for your playlist:', style='new_window.TLabel'
            ).grid(column=0, row=0, pady=10)
            entry = ttk.Entry(
                new_window, textvariable=text, width=30
            )
            entry.grid(column=0, row=1, padx=10)
            ttk.Button(
                new_window,
                text='Save',
                command=partial(set_name, text)
            ).grid(column=0, row=2, pady=10)
            entry.bind('<Return>', set_name)

        self.create_table()

        if len(self.playing_list) != 0:
            get_name()
        else:
            messagebox.showerror(
                'Playlist empty',
                self.playlist_empty,
            )

    def do_popup(self, event):
        """
        Open a pop up menu on right clicking on
        the playing listbox items.
        """
        try:
            self.playing_listbox.selection_clear(0, 'end')
            self.playing_listbox.selection_set(self.playing_listbox.nearest(event.y))
            self.playing_listbox.activate(self.playing_listbox.nearest(event.y))
            self.listbox_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.listbox_menu.grab_release()

    def show_lyrics(self):
        """
        Get the lyrics for the playing song from Genius API and
        display them in a top level window.
        """
        def get_lyrics():
            try:
                if (
                    'Artist' in self.file_tags_dict
                    and 'Title' in self.file_tags_dict
                ):
                    # Get lyrics from Genius API using client access token
                    # and display them in a top level window.
                    new_window = Toplevel(self.master)
                    new_window.title('Genius lyrics')
                    new_window.iconbitmap('ico/junkie-audio-player-icon.ico')

                    genius = lg.Genius(
                        self.token,
                        skip_non_songs=True,
                        excluded_terms=['(Remix)', '(Live)'],
                        remove_section_headers=True,
                    )
                    file_artist = self.file_tags_dict['Artist']
                    file_title = self.file_tags_dict['Title']
                    song = genius.search_song(file_title, file_artist)
                    song_lyrics = song.lyrics
                    Label(
                        self.new_window,
                        text='Lyrics for "{}" by {}'.format(file_title,
                                                            file_artist),
                        font=('Nirmala UI', 15),
                        background=self.default_bg,
                        foreground='#222',
                    ).pack(padx=10, pady=5)
                    text_area = scrolledtext.ScrolledText(
                        self.new_window, width=50,
                        font=('Nirmala UI', 12), height=30
                    )
                    text_area.pack(pady=10, padx=10)
                    text_area.insert(INSERT, song_lyrics)
                    text_area.configure(state='disabled')
                else:
                    messagebox.showerror(
                        'File info not found',
                        self.file_info_not_found,
                    )
            except (
                AttributeError,
                TypeError,
                requests.exceptions.ConnectionError,
            ) as e:
                new_window.destroy()
                if type(e) == TypeError:
                    messagebox.showwarning(
                        'API access error',
                        self.api_access_error,
                    )
                elif type(e) == requests.exceptions.ConnectionError:
                    messagebox.showwarning(
                        'Conneciton error',
                        self.connection_error,
                    )
                else:
                    messagebox.showwarning(
                        'Lyrics not found',
                        self.lyrics_not_found,
                    )

        def set_token(var):
            """Set the client access token and call get_lyrics()."""
            if text.get() == '':
                pass
            else:
                self.token = text.get()
                get_lyrics()
                new_window.destroy()

        if (
            'Artist' in self.file_tags_dict
            and 'Title' in self.file_tags_dict
        ):
            # Create a top level window and an entry widget to
            # get a entry of access token.
            new_window = Toplevel(self.master)
            new_window.title('Enter Access Token')
            new_window.iconbitmap('ico/junkie-audio-player-icon.ico')
            nw_frame = Frame(new_window)
            text = StringVar()
            Label(
                nw_frame,
                text="""You need a token from Genius API website.
            Enter it below:""",
            ).grid(row=0, column=0, pady=10)
            entry = ttk.Entry(
                nw_frame, textvariable=text, width=72
            )
            entry.grid(row=1, column=0, padx=10)
            ttk.Button(
                nw_frame, text='Confirm', command=partial(set_token, text)
            ).grid(row=2, column=0, pady=10)
            nw_frame.pack()
            entry.bind('<Return>', set_token)
        else:
            messagebox.showerror(
                'File info not found',
                self.file_info_not_found,
            )

    def video_search(self):
        """Search Youtube API for the playing song in the browser."""
        youtube_url = 'https://www.youtube.com/results?search_query={}'
        if (
            'Artist' in self.file_tags_dict
            and 'Title' in self.file_tags_dict
        ):
            fileartist = self.file_tags_dict['Artist']
            filetitle = self.file_tags_dict['Title']
            query_term = '{} {} official video'.format(fileartist,
                                                       filetitle)
            search_url = youtube_url.format(query_term)
            webbrowser.open(search_url)
        else:
            messagebox.showerror(
                'File not found',
                self.file_not_found,
            )

    def show_tip(self, widget, text):
        """
        Create a top level window and show text inside it
        as tool tip.
        """
        if self.tip_window or not text:
            return
        x, y, cx, cy = widget.bbox('insert')
        del cx
        # Calculate the appropriate coordinates for buttons.
        if type(widget) == ttk.Button:
            x_move_length = (2*len(text)) - 1
            x = (x+widget.winfo_rootx()) - x_move_length
            y = (y+cy) + (widget.winfo_rooty()+34)
        # Calculate the appropriate coordinates for check buttons.
        elif type(widget) == ttk.Checkbutton:
            x_move_length = (2*len(text)) - (len(text)/2.95)
            x = (x+widget.winfo_rootx()) - x_move_length
            y = (y+cy) + (widget.winfo_rooty()+34)
        self.tip_window = tipwindow = Toplevel(widget)
        tipwindow.wm_overrideredirect(1)
        tipwindow.wm_geometry('+%d+%d' % (x, y))
        label = ttk.Label(
            tipwindow, text=text,
            justify='left', foreground='#ffffff',
            borderwidth=3, background='#999',
            font=('tahoma', '10', 'normal'),
        )
        label.pack(padx=1)

    def hide_tip(self):
        """Destroy the tool tip top level window."""
        tipwindow = self.tip_window
        self.tip_window = None
        if tipwindow:
            tipwindow.destroy()

    def create_tooltip(self, widget, text):
        """
        Create a tool tip for 'widget' parameter widget with
        text 'text' parameter with binding.
        """
        def enter(event):
            self.show_tip(widget, text)
        def leave(event):
            self.hide_tip()

        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def about(self):
        """
        Create a top level window and display an image including
        some text about the app and creator of it.
        """
        def callback(url):
            webbrowser.open_new(url)

        def on_closing():
            new_window.grab_release()
            new_window.destroy()

        new_window = Toplevel(self.master, takefocus=True)
        new_window.title('About')
        new_window.iconbitmap('ico/junkie-audio-player-icon.ico')
        new_window.resizable(False, False)
        new_window.focus_force()
        new_window.grab_set()
        about_photoimage = PhotoImage(file='png/about-540.png')
        label = Label(new_window, image=about_photoimage, cursor='hand2')
        label.bind(
            '<Button-1>', lambda e: callback('http://www.google.com')
        )
        label.image = about_photoimage
        label.pack()

        new_window.protocol('WM_DELETE_WINDOW', on_closing)

    def stop_music(self):
        """Stop music, if something is playing."""
        mixer.music.stop()
        self.timeline_changed = True

    def closing(self, *args):
        """
        Delete cache files that were created while using the app.
        This function is called on closing the root window.
        """
        to_delete_files = [
            'png/artwork.png',
            'png/artwork-blur.png',
            'png/default-music-artwork-324-blur.png',
        ]
        for i in to_delete_files:
            try:
                os.remove(i)
            except FileNotFoundError:
                continue
        self.conn.close()
        root.destroy()


# Initialize and set the settings of the Tk interface
root = thk.ThemedTk()
root.get_themes()
root.set_theme('adapta')
root.title('Junkie Audio Player')
root.iconbitmap('ico/junkie-audio-player-icon.ico')
root.geometry('850x590')
root.resizable(True, False)
root.update()
root.minsize(root.winfo_width(), root.winfo_height())

if __name__ == '__main__':
    mixer.init()  # Initialize pygame.mixer module for audio playback.
    music_player = MusicPlayer(root)
    root.mainloop()
