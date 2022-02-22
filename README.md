# Junkie-Audio-Player
An audio player application written in Python using tkinter.

Except tkinter for GUI, the app uses pygame.mixer for audio playback, sqlite3 for saving, loading and modifying playlists from database,
lyricsgenius to connect to and use Genius API for song lyrics and some other modules for more specific functionalities.

## How to use the app

### Add files to playing list

After running the program you can see a Tk interface with some widgets inside it. click on 'Add folder' or 'Add file' to respectively
add files inside a folder or add a single file to currently playing list. Notice that only files of MP3 and WAV type are supported
for adding to list and playing.

### Play files

after adding some file(s) to the playing list you can either click on play button to start from the beginning of playing list or
double-click on a specific file in your list to play it.

### Other playing functionalities

After playing some file, you can pause the song with pause button. You can also click on next or previous button to play respectively
the next or previous song in the list. You can enable shuffle or repeat to change the playing order. You can also see a volume button
besides other buttons; by clicking on that you can either mute or unmute the playing song. There is also a slider besides the volume
button; you can adjust playing volume using that.

### Saving, loading or modifying playlists

To save the playing list, you can simply click on 'Save list', enter a name for your playlist and click on the button below your entry
to confirm your actions. After saving a playlist, you can see a list of your playlist(s) by clicking on 'My playlists' in a window. In
there you can see two button: 'Delete playlist' and 'Load playlist', by clicking on each one you can respectively delete or load the
chosen playlist; Or load the selected playlist by double-clicking on it. You can also add a song from playing list to a playlist by
right-clicking on that song and choosing 'Add to playlist' from the menu that pops up.

### Other functionalities

Besides shuffle and repeat check button you can see another check button with a sign of 'i'; When playing a song by checking that check
button you can see information of that song on its artwork if there are any info available in its file. You can also see two buttons besides
check buttons; By clicking on the left one, you can see a new window with an entry. In that entry you need to enter a client access token
from Genius API website to get lyrics for playing song and see them. By clicking on the right button a tab gets opened in your browser that
searches for the playing song in YouTube.

### Top menubar

On top of the main window you can see a menu bar with some menus. Each menu contains some options that each one has a keyboard shortcut for
easy access.


### Other features for next versions

I might add some new and fix some problems in the feauture. You can report problems that you find or also suggest a way to solve them
or give me new ideas for other features; All of these will be so appreciated. Some of features that you might want to help me with are
as follows:
1. Supporting more types of audio files
2. Making the interface look more beautiful and easy-to-use
3. Suggest one :)



Thanks for reading
