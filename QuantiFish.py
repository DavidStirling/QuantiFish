# QuantiFish - A tool for quantification of fluorescence in Zebrafish embryos.
# Copyright(C) 2017-2018 David Stirling

"""This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>."""

import sys
import os
import threading
import time
import tkinter as tk
import tkinter.filedialog as tkfiledialog
from tkinter import ttk
from csv import writer
from xml.dom import minidom

import cv2
import numpy as np
from PIL import Image, ImageTk
from scipy import ndimage as ndi
from skimage.feature import peak_local_max

# Global Variables
version = "2.0 beta"
directory = "Select a directory to process"
savedir = "Select a location to save the output"
colour = "Unknown"  # By default we don't know which channel we're looking at.
firstrun = True  # Do we need to write headers to the output file?
# Parameters for different display modes.
depthmap = {0: ("8-bit", 1, 256, 16), 1: ("10-bit", 4, 1024, 64), 2: ("12-bit", 16, 4096, 256),
            3: ("16-bit", 256, 65536, 4096)}  # (ID, multiplier, maxrange, absmin)
currentdepthname, scalemultiplier, maxrange, absmin = depthmap[0]
manualbitdepth = False
currentdepth = 0


# Get path for unpacked Pyinstaller exe (MEIPASS), else default to current directory.
def resource_path(relative_path):
    if relative_path == 'resources/QFIcon':
        extension = ".ico"
    elif os.name == 'nt':
        extension = ".png"
    else:
        extension = ".gif"
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path + extension)


# Core UI
class CoreWindow:
    def __init__(self, master):
        self.imagetypefail = None
        self.master = master
        self.savestatus = False
        self.dirstatus = False
        self.about_window = None
        self.previewwindow = None
        self.previewer_contents = None
        self.locked = False
        self.file_list_window_active = False
        self.master.wm_title("QuantiFish")
        self.master.iconbitmap(resource_path('resources/QFIcon'))
        # self.master.resizable(width=False, height=False)
        self.master.grid_columnconfigure(1, minsize=100)
        self.master.grid_columnconfigure(2, weight=1, minsize=250)
        self.master.grid_columnconfigure(3, minsize=100)

        # Core UI Containers
        self.header = ttk.Frame(self.master)
        self.corewrapper = ttk.Frame(self.master)
        self.logwrapper = ttk.Frame(self.master)
        self.header.pack(fill=tk.X, expand=False)
        self.corewrapper.pack(fill=tk.X, expand=False)
        self.logwrapper.pack(fill=tk.BOTH, expand=True)

        # Threading Controllers
        self.list_stopper = threading.Event()

        # Header Bar
        self.img = ImageTk.PhotoImage(Image.open(resource_path("resources/QFLogo")))
        self.logo = ttk.Label(self.header, image=self.img)
        self.title = ttk.Label(self.header, text="QuantiFish ", font=("Arial", 25),
                               justify=tk.CENTER).grid(column=2, columnspan=1, row=1, sticky=tk.E + tk.W)
        self.subtitle = ttk.Label(self.header, text="Zebrafish Image Analyser", font=("Arial", 10),
                                  justify=tk.CENTER).grid(column=2, columnspan=1, row=2, sticky=tk.E + tk.W)
        self.about = ttk.Button(self.header, text="About", command=self.about)
        self.logo.grid(column=1, row=1, rowspan=2, sticky=tk.W)
        self.about.grid(column=4, row=1, rowspan=1, sticky=tk.E, padx=10, pady=5)
        self.header.grid_columnconfigure(3, weight=1)

        # Log Box
        self.scrollbar = ttk.Scrollbar(self.logwrapper, orient=tk.VERTICAL)
        self.logbox = tk.Listbox(self.logwrapper, yscrollcommand=self.scrollbar.set, activestyle="none")
        self.logbox.insert(tk.END, "Log:")
        self.scrollbar.configure(command=self.logbox.yview)
        self.logbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Directory Select/File List Preview Buttons
        self.dirbuttons = ttk.Frame(self.corewrapper)
        self.dirselect = ttk.Button(self.dirbuttons, text="Set Directory", command=self.directselect)
        self.filelistbutton = ttk.Button(self.dirbuttons, text="Generate File List", command=self.filelist_thread)
        self.dirselect.pack(fill=tk.X)
        self.filelistbutton.pack(fill=tk.X)
        self.dirbuttons.grid(column=1, row=1, padx=5, sticky=tk.NSEW)

        # Directory Options Container
        self.dirframe = ttk.Frame(self.corewrapper)
        self.currdir = ttk.Entry(self.dirframe, textvariable=directory)
        self.currdir.insert(tk.END, directory)
        self.currdir.config(state=tk.DISABLED)
        self.bitlabel = ttk.Label(self.dirframe, text="Bit Depth:")
        self.bitcheck = ttk.Combobox(self.dirframe, state="readonly")
        self.bitcheck['values'] = ('Auto Detect', '8-bit', '10-bit', '12-bit', '16-bit')
        self.bitcheck.current(0)
        self.subdiron = tk.BooleanVar()
        self.subdiron.set(True)
        self.subdircheck = ttk.Checkbutton(self.dirframe, text="Include Subdirectories", variable=self.subdiron,
                                           onvalue=True, offvalue=False, command=self.subtoggle)
        self.currdir.grid(column=1, row=1, columnspan=5, sticky=tk.E + tk.W)
        self.bitlabel.grid(column=1, row=2)
        self.bitcheck.grid(column=2, row=2)
        self.subdircheck.grid(column=5, row=2, sticky=tk.E)
        self.dirframe.grid(column=2, row=1, sticky=tk.NSEW, padx=5)
        self.dirframe.grid_columnconfigure(4, weight=1)

        # File List Filter
        self.filterkwd = tk.BooleanVar()
        self.filterkwd.set(False)
        self.filtermode = tk.IntVar()
        self.filtermode.set(0)
        self.filterbox = ttk.LabelFrame(self.corewrapper, text="File List Filter")
        self.nofilter = ttk.Radiobutton(self.filterbox, text="None (Process all)", variable=self.filtermode, value="0",
                                        command=self.switch_file_filter)
        self.greyonly = ttk.Radiobutton(self.filterbox, text="Greyscale Only", variable=self.filtermode, value="1",
                                        command=self.switch_file_filter)
        self.detect = ttk.Radiobutton(self.filterbox, text="RGB Only:", variable=self.filtermode, value="2",
                                      command=self.switch_file_filter)
        self.channelselect = ttk.Combobox(self.filterbox, values=["Detect", "Blue", "Green", "Red"], width=10,
                                          state='readonly')
        self.channelselect.current(0)
        self.channelselect.state(['disabled'])
        self.textfilter = ttk.Checkbutton(self.filterbox, text="Keyword:", variable=self.filterkwd,
                                          command=self.toggle_keyword)
        self.textentry = ttk.Entry(self.filterbox, width=8)
        self.textentry.state(['disabled'])
        self.filterbox.grid(column=1, row=2, rowspan=2, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.nofilter.grid(column=1, row=1, columnspan=2, sticky=tk.W, pady=2)
        self.greyonly.grid(column=1, row=2, columnspan=2, sticky=tk.W, pady=2)
        self.detect.grid(column=1, row=3, sticky=tk.W, pady=2)
        self.channelselect.grid(column=2, row=3, sticky=tk.NSEW, pady=2)
        self.textfilter.grid(column=1, row=4, sticky=tk.W, pady=2)
        self.textentry.grid(column=2, row=4, sticky=tk.NSEW, pady=2)

        """# Mode Selector
        global mode
        mode = tk.StringVar()
        mode.set("RGB")
        global chandet
        chandet = tk.BooleanVar()
        chandet.set(True)
        self.modebox = ttk.LabelFrame(relief=tk.GROOVE, text="Image Type:")
        self.modebox.grid(column=1, row=4, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.RGB = ttk.Radiobutton(self.modebox, text="Colour", variable=mode, value="RGB",
                                  command=lambda: self.checkmode())
        self.RGB.grid(column=1, row=2, sticky=tk.W)
        self.RAW = ttk.Radiobutton(self.modebox, text="Greyscale", variable=mode, value="RAW",
                                  command=lambda: self.checkmode())
        self.RAW.grid(column=1, row=3, sticky=tk.W)
        self.detecttoggle = ttk.Checkbutton(self.modebox, text="Detect Channels", variable=chandet, onvalue=True,
                                           offvalue=False, command=self.detchan)
        self.detecttoggle.grid(column=1, row=4, sticky=tk.W)
        """
        # Threshold Selector
        self.thrframe = ttk.LabelFrame(self.corewrapper, text="Threshold (minimum intensity to count):")
        self.threshold = tk.IntVar()
        self.threshold.set(60)
        self.thron = tk.BooleanVar()
        self.thron.set(True)

        self.threslide = tk.Scale(self.thrframe, from_=0, to=256, tickinterval=64, variable=self.threshold,
                                  orient=tk.HORIZONTAL,
                                  command=lambda x: self.previewer_contents.regenpreview("nochange"))
        self.setthr = ttk.Entry(self.thrframe, textvariable=self.threshold, width=5, justify=tk.CENTER, )
        self.setthr.bind("<Return>", lambda x: self.previewer_contents.regenpreview("nochange"))
        self.thrcheck = ttk.Checkbutton(self.thrframe, text="Use Threshold", variable=self.thron, onvalue=True,
                                        offvalue=False, command=self.thrstatus)
        self.threslide.grid(column=2, row=4, rowspan=2, ipadx=150)
        self.setthr.grid(column=3, row=4, sticky=tk.S)
        self.thrcheck.grid(column=3, row=5, sticky=tk.E)
        self.thrframe.grid(column=2, row=2, sticky=tk.NSEW, pady=5, padx=5)

        # Cluster Analysis Setup
        self.clusteron = tk.BooleanVar()
        self.clusteron.set(False)
        self.minarea = tk.IntVar()
        self.minarea.set(0)
        self.clusterbox = ttk.LabelFrame(self.corewrapper, relief=tk.GROOVE, text="Cluster Analysis")
        self.cluscheck = ttk.Checkbutton(self.clusterbox, text="Search for large areas of staining",
                                         variable=self.clusteron,
                                         onvalue=True, offvalue=False, command=self.cluststatus)
        self.setsizelabel = ttk.Label(self.clusterbox, text="Minimum Cluster Size:")
        self.setarea = ttk.Entry(self.clusterbox, textvariable=self.minarea, width=5, justify=tk.CENTER)
        self.setarea.bind("<Return>", lambda x: self.previewer_contents.regenpreview("nochange"))
        self.cluscheck.grid(column=1, row=1, padx=10)
        self.setsizelabel.grid(column=3, row=1)
        self.setarea.grid(column=4, row=1, padx=(0, 10))
        self.clusterbox.grid(column=2, row=3, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.clusterbox.grid_columnconfigure(2, weight=1)

        """
        # Colour Selector
        global desiredcolour
        desiredcolour = tk.IntVar()
        desiredcolour.set(1)
        self.colbox = ttk.LabelFrame(relief=tk.GROOVE, text="Quantifying:")
        self.colbox.grid(column=3, row=4, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.opt1 = ttk.Radiobutton(self.colbox, text="Blue", variable=desiredcolour, value=2, )
        self.opt1.grid(column=1, row=2, sticky=tk.W)
        self.opt2 = ttk.Radiobutton(self.colbox, text="Green", variable=desiredcolour, value=1, )
        self.opt2.grid(column=1, row=3, sticky=tk.W)
        self.opt3 = ttk.Radiobutton(self.colbox, text="Red", variable=desiredcolour, value=0, )
        self.opt3.grid(column=1, row=4, sticky=tk.W)

        # Cluster Explain Text
        self.clusterbox = ttk.LabelFrame(text="Clustering Analysis:", relief=tk.GROOVE)
        self.clusterbox.grid(column=1, row=5, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.clusstatement = ttk.Label(self.clusterbox, text="Search for large\nareas of staining")
        self.clusstatement.grid(column=1, row=2, sticky=tk.W + tk.E + tk.N + tk.S)

        # Cluster Selector
        #global minarea
        #global clusteron
        self.clusframe = ttk.LabelFrame(text="Minimum cluster size (pixels):",)
        #minarea = tk.IntVar()
        #minarea.set(0)
        self.areaslide = tk.Scale(self.clusframe, from_=0, to=1000, tickinterval=250, variable=minarea,
                                  orient=tk.HORIZONTAL,
                                  command=lambda x: self.previewer_contents.regenpreview("nochange"))
        self.areaslide.grid(column=2, row=4, rowspan=2, ipadx=150)
        self.setarea = ttk.Entry(self.clusframe, textvariable=minarea, width=5, justify=tk.CENTER, )
        self.setarea.bind("<Return>", lambda x: self.previewer_contents.regenpreview("nochange"))
        self.setarea.grid(column=3, row=4, sticky=tk.S)
        clusteron = tk.BooleanVar()
        clusteron.set(False)
        self.cluscheck = ttk.Checkbutton(self.clusframe, text="Analyse\nClustering", variable=clusteron, onvalue=True,
                                        offvalue=False, command=self.cluststatus)
        self.areaslide.config(state=tk.DISABLED)
        self.setarea.config(state=tk.DISABLED)
        self.cluscheck.grid(column=3, row=5, sticky=tk.E)
        self.clusframe.grid(column=2, row=5, sticky=tk.W + tk.E + tk.N + tk.S, pady=5)"""

        # Save Selector
        self.saveselect = ttk.Button(self.corewrapper, text="Set Output File", command=self.savesel)
        self.savefile = ttk.Entry(self.corewrapper, textvariable=savedir)
        self.savefile.insert(tk.END, savedir)
        self.savefile.config(state=tk.DISABLED)
        self.saveselect.grid(column=1, row=4, sticky=tk.NSEW, padx=5)
        self.savefile.grid(column=2, row=4, sticky=tk.E + tk.W, padx=5)

        # Preview/Run Buttons
        self.previewbutton = ttk.Button(self.corewrapper, text="Preview", command=self.openpreview)
        self.refreshpreviewbutton = ttk.Button(self.corewrapper, text="Refresh",
                                               command=lambda: self.previewer_contents.regenpreview("refresh"))
        self.runbutton = ttk.Button(self.corewrapper, text="Run", command=self.runscript,
                                    state=tk.DISABLED)
        self.previewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)
        self.runbutton.grid(column=1, row=6, sticky=tk.NSEW, padx=5)
        self.corewrapper.grid_rowconfigure(6, weight=1)

        # Progress Bar
        self.progressframe = ttk.LabelFrame(self.corewrapper, text="Progress")
        self.progresstext = ttk.Label(self.progressframe, text="Not Ready")
        self.progressbar = ttk.Progressbar(self.progressframe, mode='indeterminate')
        self.progressbar.start()
        self.progresstext.grid(column=1, row=1, columnspan=2)
        self.progressbar.grid(column=1, row=2, columnspan=2, sticky=tk.NSEW, padx=5, pady=(0, 5))
        self.progressframe.grid_columnconfigure(2, weight=1)
        self.progressframe.grid(column=2, row=5, rowspan=2, sticky=tk.NSEW, padx=5)

    # TODO: Preview window as class

    def preview_update(self):
        # trigger update if preview window exists.
        return

    def preview_window(self):
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.previewwindow = tk.Toplevel(self.master)
        self.previewer_contents = PreviewWindow(self.previewwindow)
        self.previewwindow.title("Previewer")
        self.previewwindow.iconbitmap(resource_path('resources/QFIcon'))
        self.previewwindow.update_idletasks()
        self.previewwindow.geometry('%dx%d+%d+%d' % (self.previewwindow.winfo_width(),
                                                     self.previewwindow.winfo_height(), x, y))
        self.previewwindow.protocol("WM_DELETE_WINDOW", app.closepreview)

    # Closes Preview Window    
    def closepreview(self):
        if self.previewwindow:
            self.refreshpreviewbutton.grid_forget()
            self.previewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)
            self.previewwindow.destroy()

    def about(self):
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.about_window = tk.Toplevel(self.master)
        self.app = AboutWindow(self.about_window)
        self.about_window.title("About")
        self.about_window.focus_set()
        self.about_window.grab_set()
        self.about_window.iconbitmap(resource_path('resources/QFIcon'))
        self.about_window.geometry('%dx%d+%d+%d' % (150, 225, x, y))

    def file_list_viewer(self):
        if self.file_list_window_active:
            self.flapp.filelistbox.delete(0, tk.END)
        else:
            x = self.master.winfo_rootx()
            y = self.master.winfo_rooty()
            x += self.master.winfo_width()
            self.file_list_window = tk.Toplevel(self.master)
            self.flapp = FileListWindow(self.file_list_window)
            self.file_list_window.title("File List")
            self.file_list_window.focus_set()
            self.file_list_window.iconbitmap(resource_path('resources/QFIcon'))
            self.file_list_window.geometry('%dx%d+%d+%d' % (150, 225, x, y))
            self.file_list_window.protocol("WM_DELETE_WINDOW", app.closefilelist)
            self.file_list_window_active = True
            self.file_list_window.geometry("700x500")

    def closefilelist(self):
        self.file_list_window.destroy()
        self.file_list_window_active = False

    def preview_filelist(self):
        global directory
        if self.dirstatus:
            self.file_list_viewer()
            self.flapp.filelistlabel.config(text="Scanning, please wait...")
            filelist = genfilelist(directory, self.list_stopper)
            for item in filelist:
                self.flapp.filelistbox.insert(tk.END, str(item))
            self.flapp.filelistlabel.config(text=(str(len(filelist)) + " files to be analysed"))

        else:
            self.logevent("No image directory set, unable to generate file list.")
            self.flapp.filelistlabel.config(text="0 files to be analysed")

    def filelist_thread(self):
        if self.list_stopper.is_set():
            self.list_stopper.clear()
            time.sleep(0.5)
        self.list_stopper.set()
        filegenthread = threading.Thread(target=self.preview_filelist, args=())
        filegenthread.setDaemon(True)
        filegenthread.start()

    # On changing file list filter type, update UI.
    def switch_file_filter(self):
        # Modes: None, Greyscale, Keyword, Detect
        # Descriptor Parts:
        # textentrystate, channelselectstate, logdescription
        newmode = self.filtermode.get()
        descriptors = {
            0: ('disabled', ('File filter disabled, all files in target directory will be processed.',
                             'Multi-colour overlays are not supported. Single colour images will still be analysed.')),
            1: ('disabled', ('Only greyscale files will be analysed.',
                             'Use a keyword to filter to a specific channel.')),
            2: ('!disabled', ('Only colour images will be analysed.',
                              'Will try to detect if only one channel has data, ' +
                              'for multi-colour images please specify the desired channel.')),
        }
        self.channelselect.state([descriptors[newmode][0]])
        for line in descriptors[newmode][1]:
            self.logevent(line)

    def toggle_keyword(self):
        if self.filterkwd.get():
            self.textentry.state(['!disabled'])
            self.logevent("Will filter file list for selected keyword")
        else:
            self.textentry.state(['disabled'])

    # Checks mode and closes preview windows to avoid conflict on mode change.
    # TODO: Rewire to trigger on bit depth change
    def checkmode(self):
        if mode.get() == "RGB":
            self.threslide.config(to=256, tickinterval=64)
            try:
                self.previewwindow.destroy()
                self.refreshpreviewbutton.grid_forget()
                self.previewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)
            except:
                pass
            self.logevent("Will run in RGB mode, use this if your images show in colour(s)")
        elif mode.get() == "RAW":
            self.threslide.config(to=65536, tickinterval=16384)
            try:
                self.previewwindow.destroy()
                self.refreshpreviewbutton.grid_forget()
                self.previewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)
            except:
                pass
            self.logevent("Will run in RAW mode, use this if your images show in greyscale")

    # Pushes message to log box.
    def logevent(self, text):
        self.logbox.insert(tk.END, str(text))
        self.logbox.see(tk.END)

    # Detect threshold status and disable widgets if it's off.
    def thrstatus(self):
        if self.thron.get():
            self.logevent("Threshold Enabled")
            self.threslide.config(state=tk.NORMAL)
            self.setthr.config(state=tk.NORMAL)
        else:
            self.logevent("Threshold Disabled")
            self.threslide.config(state=tk.DISABLED)
            self.setthr.config(state=tk.DISABLED)
            threshold.set(0)

    # Detect clustering status and disable widgets if it's off.
    def cluststatus(self):
        global firstrun
        if clusteron.get():
            self.logevent("Cluster Analysis Enabled")
            self.logevent("WARNING: Logging format changed. Any data already in the output file will be lost.")
            self.areaslide.config(state=tk.NORMAL)
            self.setarea.config(state=tk.NORMAL)
            minarea.set(10)
            firstrun = True
        else:
            self.logevent("Cluster Analysis Disabled")
            self.logevent("WARNING: Logging format changed. Any data already in the output file will be lost.")
            self.areaslide.config(state=tk.DISABLED)
            self.setarea.config(state=tk.DISABLED)
            minarea.set(0)
            firstrun = True

    # Prompt user to select directory.
    def directselect(self):
        global directory
        self.closepreview()
        try:
            directory = tkfiledialog.askdirectory(title='Choose directory')
            if directory == "":
                self.logevent("Directory not selected")
                return
            self.currdir.config(state=tk.NORMAL)
            self.currdir.delete(0, tk.END)
            self.currdir.insert(tk.END, directory)
            self.currdir.config(state=tk.DISABLED)
            self.logevent("Images will be read from: " + str(directory))
            self.dirstatus = True
            if self.dirstatus and self.savestatus:
                self.runbutton.config(state=tk.NORMAL, text="Run", bg="#99e699")
            if self.file_list_window_active:
                self.filelist_thread()
        except:
            self.logevent("Directory not set")

    # Prompt user for output file.
    def savesel(self):
        global savedir
        global firstrun
        try:
            savedir = tkfiledialog.asksaveasfile(mode='w', defaultextension='.csv', initialfile='output.csv',
                                                 title='Save output file')
            self.savefile.config(state=tk.NORMAL)
            self.savefile.delete(0, tk.END)  # TODO: Update this for read only fields rather than disabling them.
            self.savefile.insert(tk.END, savedir.name)
            self.savefile.config(state=tk.DISABLED)
            self.logevent("Data will save in: " + str(savedir.name))
            self.savestatus = True
            firstrun = True
            if self.dirstatus and self.savestatus:
                self.runbutton.config(state=tk.NORMAL, text="Run", bg="#99e699")
            else:
                return
        except:
            self.logevent("Save file selection unsuccessful.")

    # Toggle inclusion of subdirectories
    def subtoggle(self):
        if self.subdiron.get():
            self.logevent("Will process images in subdirectories")
        else:
            self.logevent("Will skip images in subdirectories")

    # Explain to user whether they're going to detect channels.
    def detchan(self):
        if chandet.get():
            self.logevent(
                "Will search for Leica metadata to identify colours and then only process images from the selected channel")
        else:
            self.logevent(
                "Will analyse all files, you'll need to determine which images in the output are your desired channel")

    def lock_ui(self):
        if self.locked:
            newstate = '!disabled'
            self.locked = False
        else:
            newstate = 'disabled'
            self.locked = True
        for widget in self.master.winfo_children():
            print(widget.children.values())
            widget.state([newstate])
        # TODO: Convert all to ttk frames.
        # self.widgetslist = [self.logselect, self.currlog, self.prevsaveselect, self.prevdir, self.prevsavecheck, self.singlespotcheck, self.singleplanecheck, self.singleplaneentry]
        return

    # Open preview window
    def openpreview(self):
        global pospixels
        pospixels = tk.IntVar()
        app.list_stopper.set()
        self.fileslist = genfilelist(directory, app.list_stopper)
        self.currentpreviewfile = 0
        try:
            if self.dirstatus:
                self.previewfile = self.fileslist[self.currentpreviewfile]
            else:
                self.previewfile = tkfiledialog.askopenfilename(filetypes=[('Tiff file', '*.tif')])

        except:
            self.logevent("Unable to open file, did you select a .tif image?")
            return
        self.logevent("Opening preview")
        self.genpreview(self.previewfile, False, True)
        #        try:
        self.preview_window()
        self.previewbutton.grid_forget()

        self.refreshpreviewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)

        if self.imagetypefail:
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)
            self.previewframe.grid_columnconfigure(1, weight=1)
            self.previewpane = tk.Label(self.previewframe, text="[Preview Not Available]", height=30)
            self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)

    #   except Exception as e:
    #       self.logevent("Failed to generate preview, sorry!")

    # Thresholded Preview Generator

    def genpreview(self, tgt, wantclusters, newimage):
        global maxvalue, scalemultiplier
        self.imagetypefail = False
        if newimage:
            imfile, imagetype = open_file(tgt)
            if imagetype == "Invalid":
                self.imagetypefail = True
                return
            maxvalue = np.amax(imfile[:, :])
            bit_depth_detect(imfile)
            # Reduce preview spawner to 8-bit range
            self.im = (imfile / scalemultiplier).astype('uint8')
            # Resize preview spawner if it's too large for the window
            if self.im.shape[1] > 1500:
                self.resizefactor = 1500 / self.im.shape[1]
                from skimage.transform import rescale
                self.im = rescale(self.im, self.resizefactor)
                self.im = (self.im * 255).astype('uint8')
            # Display as a grey background in an RGB image (duplicate channels)
            self.im = np.repeat(self.im[:, :, np.newaxis], 3, axis=2)
        self.im2 = self.im.copy()  # Clone the core image to work with it.
        thold = self.threshold.get()
        nooverlay = Image.fromarray(self.im2, 'RGB')
        mask = (self.im2[:, :, 1] > thold)
        pospixels.set(np.count_nonzero(mask))
        if wantclusters:
            threshtemp = self.im2.copy()
            tmask2 = (self.im2[:, :] < thold)
            threshtemp[tmask2] = 0
            simpleclusters, numclusters = ndi.measurements.label(threshtemp)
            areacounts = np.unique(simpleclusters, return_counts=True)
            positivegroups = areacounts[0][1:][areacounts[1][1:] > self.minarea.get()]
            clustermask = np.isin(simpleclusters[:, :], positivegroups)
        self.im2[mask] = (0, 191, 255)
        if wantclusters:
            self.im2[clustermask] = (0, 75, 255)
        self.preview2 = Image.fromarray(self.im2, 'RGB')
        self.preview = self.preview2.resize((self.preview2.size[0] // 2, self.preview2.size[1] // 2))
        self.nooverlay = nooverlay.resize((nooverlay.size[0] // 2, nooverlay.size[1] // 2))
        self.nooverlay = ImageTk.PhotoImage(self.nooverlay)
        self.preview = ImageTk.PhotoImage(self.preview)
        self.displayed = "overlay"


    # TODO: Replace CV2 with skimage file handling
    # TODO: Convert RGB imports into greyscale.
    # TODO: Bit depth detection

    # Writes headers in output file
    def headers(self):
        if clusteron.get():
            headings = (
                'File', 'Integrated Intensity', 'Positive Pixels', 'Maximum', 'Minimum', 'Total Clusters',
                'Total Peaks',
                'Large Clusters', 'Peaks in Large Clusters', 'Integrated Intensity in Large Clusters',
                'Positive Pixels in Large Clusters', 'Threshold', 'Channel')
        else:
            headings = (
                'File', 'Integrated Intensity', 'Positive Pixels', 'Maximum', 'Minimum', 'Threshold', 'Channel')
        try:
            with open(savedir.name, 'w', newline="\n", encoding="utf-8") as f:
                self.writer = writer(f)
                self.writer.writerow(headings)
                self.logevent("Save file created successfully")
        except:
            self.logevent("Unable to create save file")
        savedir.close()

    # Exports data to csv file
    def datawriter(self, exportpath, exportdata):
        writeme = tuple([exportpath]) + exportdata + tuple([self.threshold.get()] + [colour])
        try:
            with open(savedir.name, 'a', newline="\n", encoding="utf-8") as f:
                datawriter = writer(f)
                datawriter.writerow(writeme)
        except Exception as e:
            print(e)
            self.logevent("Unable to write to save file, please make sure it isn't open in another program!")

    # TODO: Better UI toggling.

    # Script Starter
    def runscript(self):
        global mpro
        global firstrun
        # Disable everything
        self.dirselect.config(state=tk.DISABLED)
        self.subdircheck.config(state=tk.DISABLED)
        self.RGB.config(state=tk.DISABLED)
        self.RAW.config(state=tk.DISABLED)
        self.detecttoggle.config(state=tk.DISABLED)
        self.opt1.config(state=tk.DISABLED)
        self.opt2.config(state=tk.DISABLED)
        self.opt3.config(state=tk.DISABLED)
        self.saveselect.config(state=tk.DISABLED)
        self.thrcheck.config(state=tk.DISABLED)
        self.setthr.config(state=tk.DISABLED)
        self.threslide.config(state=tk.DISABLED)
        self.cluscheck.config(state=tk.DISABLED)
        self.areaslide.config(state=tk.DISABLED)
        self.setarea.config(state=tk.DISABLED)
        self.runbutton.config(text="Stop", bg="#ff4d4d", command=self.abort)
        if firstrun:
            try:
                self.headers()
                firstrun = False
            except:
                self.logevent("Unable to write to output file")
        try:  # Setup thread for analysis to run in
            global mprokilla
            mprokilla = threading.Event()
            mprokilla.set()
            mpro = threading.Thread(target=cyclefiles, args=(
                mprokilla, directory, mode.get(), self.threshold.get(), desiredcolour.get()))
            mpro.setDaemon(True)
            mpro.start()
        except:
            app.logevent("Unable to acquire data, something went wrong!")
            app.dirselect.config(state=tk.NORMAL)
            app.subdircheck.config(state=tk.NORMAL)
            app.RGB.config(state=tk.NORMAL)
            app.RAW.config(state=tk.NORMAL)
            app.detecttoggle.config(state=tk.NORMAL)
            app.opt1.config(state=tk.NORMAL)
            app.opt2.config(state=tk.NORMAL)
            app.opt3.config(state=tk.NORMAL)
            app.saveselect.config(state=tk.NORMAL)
            app.thrcheck.config(state=tk.NORMAL)
            app.cluscheck.config(state=tk.NORMAL)
            if clusteron.get():
                app.areaslide.config(state=tk.NORMAL)
                app.setarea.config(state=tk.NORMAL)
            if app.thron.get():
                app.setthr.config(state=tk.NORMAL)
                app.threslide.config(state=tk.NORMAL)
            return
        return

    # Stops a running script
    def abort(self):
        try:
            mprokilla.clear()
            self.logevent("Aborted run")
            app.runbutton.config(text="Run", bg="#99e699", command=app.runscript)
            app.dirselect.config(state=tk.NORMAL)
            app.subdircheck.config(state=tk.NORMAL)
            app.RGB.config(state=tk.NORMAL)
            app.RAW.config(state=tk.NORMAL)
            app.detecttoggle.config(state=tk.NORMAL)
            app.opt1.config(state=tk.NORMAL)
            app.opt2.config(state=tk.NORMAL)
            app.opt3.config(state=tk.NORMAL)
            app.saveselect.config(state=tk.NORMAL)
            app.thrcheck.config(state=tk.NORMAL)
            app.cluscheck.config(state=tk.NORMAL)
            if clusteron.get():
                app.areaslide.config(state=tk.NORMAL)
                app.setarea.config(state=tk.NORMAL)
            if app.thron.get():
                app.setthr.config(state=tk.NORMAL)
                app.threslide.config(state=tk.NORMAL)
        except:
            self.logevent("Failed to stop script, eep! Try restarting the program.")


# Microscope Settings Detector, searches for metadata and determines channel identities
def findmeta():
    global colour, colourid, chandet, directory
    global colourid
    global chandet
    greenid = "Unknown"
    blueid = "Unknown"
    redid = "Unknown"
    if not chandet.get():
        colour = "Unknown"
        return False
    for scanroot, scandirs, scanfiles in os.walk(directory):
        for folder in scandirs:
            if "MetaData" in folder:
                app.logevent("Found MetaData folder, trying to pull image parameters...")
                metadir = os.path.join(scanroot, folder)
                for root, dirs, files in os.walk(metadir):
                    for file in files:
                        if file.endswith(".xml"):
                            metafile = os.path.join(root, file)
                            xmldoc = minidom.parse(metafile)
                            itemlist = xmldoc.getElementsByTagName('WideFieldChannelInfo')
                            for item in itemlist:
                                if item.attributes["LUT"].value == "Green":
                                    greenid = item.attributes["Channel"].value[-2:]
                                elif item.attributes["LUT"].value == "Red":
                                    redid = item.attributes["Channel"].value[-2:]
                                elif item.attributes["LUT"].value == "Blue":
                                    blueid = item.attributes["Channel"].value[-2:]
                                elif item.attributes["LUT"].value == "Gray":
                                    BFid = item.attributes["Channel"].value[-2:]
                            if desiredcolour.get() == 1 and greenid is not "Unknown":
                                colourid = greenid
                                colour = "Green"
                                app.logevent("Identified green channel")
                                return True
                            elif desiredcolour.get() == 0 and redid is not "Unknown":
                                colourid = redid
                                colour = "Red"
                                app.logevent("Identified red channel")
                                return True
                            elif desiredcolour.get() == 2 and blueid is not "Unknown":
                                colourid = blueid
                                colour = "Blue"
                                app.logevent("Identified blue channel")
                                return True
                            else:
                                app.logevent("Failed to identify desired channel, will process all images")
                                colour = "Unknown"
                                return False
    app.logevent("Cannot find metafile, will process all images")
    colour = "Unknown"
    return False


# File List Generator
def genfilelist(tgtdirectory, aborter):
    subdirectories = app.subdiron.get()
    searchmode = app.filtermode.get()
    if app.filterkwd.get():
        kwd = app.textentry.get()
        filelist = [os.path.normpath(os.path.join(root, f)) for root, dirs, files in os.walk(tgtdirectory) for f in
                    files if f.lower().endswith((".tif", ".tiff")) and not f.startswith(".") and kwd in f and (
                            root == tgtdirectory or subdirectories)]
    else:  # No keyword filter
        filelist = [os.path.normpath(os.path.join(root, f)) for root, dirs, files in os.walk(tgtdirectory) for f in
                    files if f.lower().endswith((".tif", ".tiff")) and not f.startswith(".") and (
                            root == tgtdirectory or subdirectories)]
    if searchmode == 1:  # Greyscale Only
        allowed_formats = ("I", "F", "L")
    elif searchmode == 2:  # RGB Only
        allowed_formats = ("RGB", "RGBA")
    else:  # No type filter, return.
        app.list_stopper.clear()
        return filelist
    filteredfilelist = []
    for file in filelist:  # Remove files in incorrect format.
        if aborter.is_set():
            try:
                imgtest = Image.open(file)
                if imgtest.mode.startswith(allowed_formats):
                    filteredfilelist.append(file)
                imgtest.close()
            except OSError as e:
                app.logevent("ERROR: Unable to read " + file)
                app.logevent("File may be corrupted. Will skip during analysis.")
                print(e)
            except Exception as e:
                app.logevent("Unhandled Error, skipping file")
    app.list_stopper.clear()
    return filteredfilelist


# Master File Cycler
def cyclefiles(stopper, tgtdirectory, activemode, thresh, desiredcolourid):
    app.list_stopper.set()
    filelist = genfilelist(tgtdirectory, app.list_stopper)
    # TODO: ADD A PROGRESSBAR FUNCTION
    # TODO: Handle inappropriate filetypes better.
    for file in filelist:
        if stopper.wait():
            app.logevent("Analysing: " + file)
            data, filetype = open_file(file)
            if filetype == "Invalid":
                app.logevent("Invalid file type, analysis skipped")
            else:
                try:
                    results = genstats(data, desiredcolourid, activemode, thresh, clusteron.get())
                    app.datawriter(file, results)
                except:
                    app.logevent("Analysis failed, image may be corrupted")

    # TODO: Progress bar updater here.
    app.logevent("Script Complete!")
    app.dirselect.config(state=tk.NORMAL)
    app.subdircheck.config(state=tk.NORMAL)
    app.RGB.config(state=tk.NORMAL)
    app.RAW.config(state=tk.NORMAL)
    app.detecttoggle.config(state=tk.NORMAL)
    app.opt1.config(state=tk.NORMAL)
    app.opt2.config(state=tk.NORMAL)
    app.opt3.config(state=tk.NORMAL)
    app.saveselect.config(state=tk.NORMAL)
    app.thrcheck.config(state=tk.NORMAL)
    app.cluscheck.config(state=tk.NORMAL)
    if clusteron.get():
        app.areaslide.config(state=tk.NORMAL)
        app.setarea.config(state=tk.NORMAL)
    if app.thron.get():
        app.setthr.config(state=tk.NORMAL)
        app.threslide.config(state=tk.NORMAL)
    app.runbutton.config(text="Run", bg="#99e699", command=app.runscript)
    savedir.close()


def open_file(filepath):
    from skimage.io import imread
    currentmode = app.filtermode.get()
    chandef = {"Detect": 0,
               "Blue": 1,
               "Green": 2,
               "Red": 3
               }
    desiredcolour = chandef[app.channelselect.get()]
    inputarray = imread(filepath, as_grey=False, plugin="pil")
    if inputarray.ndim == 2:
        imagetype = "greyscale"
    elif inputarray.ndim == 3:
        dimensions = inputarray.shape[2]
        if dimensions == 3:
            imagetype = "RGB"
        elif dimensions == 4:
            imagetype = "RGBA"
        else:
            imagetype = "Invalid"
            app.logevent("Invalid image format, skipping...")

        if currentmode == 2 and desiredcolour != "Detect":
            inputarray = inputarray[:, :, desiredcolour - 1]
        else:  # Check if only one channel has data.
            populated_channels = []
            for i in range(0, 3):  # Scan RGB channels, not A. List channels containing data.
                if np.max(inputarray[:, :, i]) > 0:
                    populated_channels.append(i)
            if len(populated_channels) == 1:  # Single colour RGB image, work on just the channel of interest
                inputarray = inputarray[:, :, populated_channels[0]]
            elif len(populated_channels) == 0:  # All channels blank
                app.logevent("Image appears to be blank, skipping")
                imagetype = "Invalid"
            else:  # Multi colour overlay
                app.logevent("Image has multiple channels with data but no channel is specified for analysis, skipping")
                imagetype = "Invalid"
    else:
        imagetype = "Invalid"
    if imagetype != "Invalid":
        bit_depth_detect(inputarray)
    return inputarray, imagetype


def bit_depth_detect(imgarray):  # TODO: Update this for QuantiFish
    global depthmap, currentdepth, scalemultiplier, maxrange, absmin, depthname, manualbitdepth
    max_value = imgarray.max()
    if manualbitdepth:
        return
    if max_value < 256:
        depth = 0  # 8-bit
    elif 256 <= max_value < 1024:
        depth = 1  # 10-bit
    elif 1024 <= max_value < 4096:
        depth = 2  # 12-bit
    else:
        depth = 3  # 16-bit
    if currentdepth < depth:
        name, scalemultiplier, maxrange, absmin = depthmap[depth]
        currentdepth = depth
        app.logevent("Detected bit depth: " + name)
        # TODO: Config thresholds
        # depthname.set(name)
    # Check if run is ongoing and alert if depth changes.
    return


# Data generators
def genstats(inputimage, x, mode2, th, wantclusters):
    if mode2 == "RGB":
        inputimage = cv2.cvtColor(inputimage, cv2.COLOR_BGR2RGB)
        max_value = np.amax(inputimage[:, :, x])
        min_value = np.amin(inputimage[:, :, x])
        mask = (inputimage[:, :, x] < th)
        try:
            inputimage[mask] = (0, 0, 0)
        except:
            inputimage[mask] = (0, 0, 0, 255)
        intint = np.sum(inputimage[:, :, x])
        count = np.count_nonzero(inputimage[:, :, x])
    else:  # mode2 == "RAW"
        max_value = np.amax(inputimage)
        min_value = np.amin(inputimage)
        mask = (inputimage < th)
        inputimage[mask] = 0
        intint = np.sum(inputimage)
        count = np.count_nonzero(inputimage)
    results_pack = (intint, count, max_value, min_value)
    if wantclusters:
        numclusters, targetclusters, numpeaks, numtargetpeaks, intintfil, countfil = getclusters(inputimage, th, mode2,
                                                                                                 x, minarea.get())
        results_pack += (numclusters, numpeaks, targetclusters, numtargetpeaks, intintfil, countfil)
    return results_pack


# Cluster Analysis
def getclusters(trgtimg, thresh, mode2, x, minimumarea):
    # Find and count peaks above threshold, assign labels to clusters of stainng.
    if mode2 == "RGB":
        localmax = peak_local_max(trgtimg[:, :, x], indices=False, threshold_abs=thresh)
        peaks, numpeaks = ndi.measurements.label(localmax)
        simpleclusters, numclusters = ndi.measurements.label(trgtimg[:, :, x])
        # Create table of cluster ids vs size of each, then list clusters bigger than minsize
        areacounts = np.unique(simpleclusters, return_counts=True)
        positivegroups = areacounts[0][1:][areacounts[1][1:] > minimumarea]
        # Mask for only positive clusters, find clusters which are in the list of clusters, count them.
        clustermask = np.isin(simpleclusters, positivegroups)
        targetclusters = np.sum(areacounts[1][1:] > minimumarea)
        # Clone the image then remove any staining in negative clusters. Quantifies staining in positive clusters.
        filthresholded = trgtimg.copy()
        try:
            filthresholded[np.invert(clustermask)] = (0, 0, 0)
        except:
            filthresholded[np.invert(clustermask)] = (0, 0, 0, 255)
        intintfil = np.sum(filthresholded[:, :, x])
        countfil = np.count_nonzero(filthresholded[:, :, x])
        localmax2 = peak_local_max(filthresholded[:, :, x], indices=False, threshold_abs=thresh)
    else:
        localmax = peak_local_max(trgtimg, indices=False, threshold_abs=thresh)
        peaks, numpeaks = ndi.measurements.label(localmax)
        simpleclusters, numclusters = ndi.measurements.label(trgtimg)
        # Create table of cluster ids vs size of each, then list clusters bigger than minsize
        areacounts = np.unique(simpleclusters, return_counts=True)
        positivegroups = areacounts[0][1:][areacounts[1][1:] > minimumarea]
        # Mask for only positive clusters, find clusters which are in the list of clusters, count them.
        clustermask = np.isin(simpleclusters, positivegroups)
        targetclusters = np.sum(areacounts[1][1:] > minimumarea)
        # Clone the image then remove any staining in negative clusters. Quantifies staining in positive clusters.
        filthresholded = trgtimg.copy()
        filthresholded[np.invert(clustermask)] = 0
        intintfil = np.sum(filthresholded)
        countfil = np.count_nonzero(filthresholded)
        localmax2 = peak_local_max(filthresholded[:, :], indices=False, threshold_abs=thresh)
    targetpeaks, numtargetpeaks = ndi.measurements.label(localmax2)
    return numclusters, targetclusters, numpeaks, numtargetpeaks, intintfil, countfil


def savepreview():
    try:
        previewsavename = tkfiledialog.asksaveasfile(mode="w", defaultextension=".tif",
                                                     title="Choose save location")
        app.preview2.save(previewsavename.name)
        app.logevent("Saving preview")
        previewsavename.close()
    except:
        app.logevent("Unable to save file, is this location valid?")
        return


class PreviewWindow:
    def __init__(self, master):
        self.master = master
        style = ttk.Style()
        style.configure('preview.TButton', background='green', sticky='nswe', justify='center', width=6)
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.previewwindow = ttk.Frame(self.master)
        self.previewtitle = ttk.Label(self.previewwindow, text=("..." + app.previewfile[-100:]))
        self.previewtitle.grid(row=1, column=1, columnspan=5)

        self.previewframe = ttk.Frame(self.previewwindow)  # Frame to aid holding and deleting preview images.
        self.previewframe.grid_columnconfigure(1, weight=1)
        if not app.imagetypefail:
            self.previewpane = ttk.Label(self.previewframe, image=app.preview)
            self.previewpane.image = app.preview
        else:
            self.previewpane = ttk.Label(self.previewframe, text="[Preview Not Available]", height=30)
        self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
        self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)

        self.previewcontrols = ttk.Frame(self.previewwindow, borderwidth=2,
                                         relief=tk.GROOVE)  # Frame for preview controls.
        self.previewcontrols.grid(column=1, columnspan=5, row=3, sticky=tk.E + tk.W + tk.N + tk.S)
        self.prevpreviewbutton = ttk.Button(self.previewcontrols, width=5, text="Previous\nFile",
                                           command=lambda: self.regenpreview("previous"))
        self.prevpreviewbutton.grid(column=1, row=1, rowspan=2, sticky=tk.E, padx=(3, 0), pady=5, ipadx=10)
        self.prevpreviewbutton.config(state=tk.DISABLED)
        self.nextpreviewbutton = ttk.Button(self.previewcontrols, width=5, text="Next\nFile",
                                           command=lambda: self.regenpreview("next"))
        self.nextpreviewbutton.grid(column=2, row=1, rowspan=2, sticky=tk.E, padx=(0, 3), pady=5, ipadx=10)
        if not app.dirstatus:
            self.nextpreviewbutton.config(state=tk.DISABLED)
        self.changepreviewbutton = ttk.Button(self.previewcontrols, width=5, text="Select\nFile",
                                             command=lambda: self.regenpreview("change"))
        self.changepreviewbutton.grid(column=3, row=1, rowspan=2, sticky=tk.E + tk.W, padx=3, ipadx=10)
        self.refresh = ttk.Button(self.previewcontrols, text="Refresh",
                                 command=lambda: self.regenpreview("refresh")).grid(column=4, row=1, rowspan=2,
                                                                                    sticky=tk.E, padx=3, pady=5,
                                                                                    ipadx=10)
        self.overlaytoggle = ttk.Button(self.previewcontrols, text="Show\nOverlay",
                                        command=lambda: self.switchpreview(False))
        self.overlaytoggle.grid(column=5, row=1, rowspan=2, padx=3, pady=5, ipadx=10)
        self.clustertoggle = ttk.Button(self.previewcontrols, text="Find\nClusters",
                                       command=lambda: self.switchpreview(True))
        self.clustertoggle.grid(column=6, row=1, rowspan=2, padx=3, pady=5, ipadx=10)

        self.overlaysave = ttk.Button(self.previewcontrols, text="Save\nOverlay",
                                     command=lambda: savepreview())
        self.overlaysave.grid(column=7, row=1, rowspan=2, sticky=tk.W, padx=3, pady=5, ipadx=10)
        self.autothresh = ttk.Button(self.previewcontrols, width=5, text="Auto\nThreshold",
                                    command=lambda: self.autothreshold()).grid(column=8, row=1, rowspan=2, sticky=tk.E,
                                                                               padx=5, pady=5, ipadx=15)
        self.pospixelbox = ttk.LabelFrame(self.previewcontrols, text="Positive Pixels")
        self.poscount = ttk.Label(self.pospixelbox, textvariable=pospixels)
        self.poscount.grid(column=1, row=2, sticky=tk.W + tk.E, )
        self.pospixelbox.grid(column=9, row=1, rowspan=2, sticky=tk.W, padx=(5, 0))
        self.previewexplain = ttk.Label(self.previewwindow,
                                       text="Light blue pixels represent areas which will be counted as positive.\n Clicking \"Find Clusters\" will mark detected areas in a darker blue. \n Use AutoThreshold on a negative control or set threshold manually to remove autofluorescence.").grid(
            column=1, row=4, columnspan=5)
        self.previewwindow.pack()

    # Regenerate preview, reset window if the source image is changing.
    def regenpreview(self, mode):
        newfile = False
        try:
            if self.previewwindow.winfo_exists() == 0:
                return
        except:
            return
        if mode == "refresh":
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)
        elif mode == "cluster":
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)
            try:
                app.genpreview(app.previewfile, True, newfile)
                self.previewpane = tk.Label(self.previewframe, image=app.preview)
                self.previewpane.image = app.preview
                self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
            except Exception as e:
                app.logevent("Error generating preview file")
                print(e)
            self.overlaytoggle.config(relief=tk.SUNKEN)
            self.displayed = "clusters"
            return
        elif mode == "change":
            newfile = True
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow, height=500)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)
            try:
                app.previewfile = os.path.normpath(tkfiledialog.askopenfilename(filetypes=[('Tiff file', '*.tif')]))
                self.previewtitle.destroy()
                self.previewtitle = tk.Label(self.previewwindow, text=("..." + app.previewfile[-100:]))
                self.previewtitle.grid(row=1, column=1, columnspan=5)
                if app.previewfile in app.fileslist:
                    app.currentpreviewfile = app.fileslist.index(app.previewfile)
                    if app.currentpreviewfile > 0:
                        self.prevpreviewbutton.config(state=tk.NORMAL)
                    elif app.currentpreviewfile == 0:
                        self.prevpreviewbutton.config(state=tk.DISABLED)
                    if app.currentpreviewfile < len(app.fileslist) - 1:
                        self.nextpreviewbutton.config(state=tk.NORMAL)
                    else:
                        self.nextpreviewbutton.config(state=tk.DISABLED)
                else:
                    self.nextpreviewbutton.config(state=tk.DISABLED)
                    self.prevpreviewbutton.config(state=tk.DISABLED)
            except Exception as e:
                print(e)
                app.logevent("Unable to open file, did you select a .tif image?")
                self.previewframe.grid_columnconfigure(1, weight=1)
                self.previewpane = tk.Label(self.previewframe, text="[Preview Not Available]", height=30)
                self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
                return
        elif mode == "next":
            newfile = True
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)
            app.currentpreviewfile += 1
            self.prevpreviewbutton.config(state=tk.NORMAL)
            if app.currentpreviewfile == (len(app.fileslist) - 1):
                self.nextpreviewbutton.config(state=tk.DISABLED)
            else:
                self.nextpreviewbutton.config(state=tk.NORMAL)
            app.previewfile = app.fileslist[app.currentpreviewfile]
            self.previewtitle.destroy()
            self.previewtitle = tk.Label(self.previewwindow, text=("..." + app.previewfile[-100:]))
            self.previewtitle.grid(row=1, column=1, columnspan=5)
        elif mode == "previous":
            newfile = True
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)
            app.currentpreviewfile -= 1
            self.nextpreviewbutton.config(state=tk.NORMAL)
            if app.currentpreviewfile == 0:
                self.prevpreviewbutton.config(state=tk.DISABLED)
            else:
                self.prevpreviewbutton.config(state=tk.NORMAL)
            app.previewfile = app.fileslist[app.currentpreviewfile]
            self.previewtitle.destroy()
            self.previewtitle = tk.Label(self.previewwindow, text=("..." + app.previewfile[-100:]))
            self.previewtitle.grid(row=1, column=1, columnspan=5)

        # try:
        app.genpreview(app.previewfile, False, newfile)
        # TODO: Re-enable preview failcheck
        # except Exception as e:
        #    app.logevent("Error generating preview file")
        #    print(e)
        #    return
        if not app.imagetypefail:  # Only show preview if the image is the right type.
            self.previewpane = tk.Label(self.previewframe, image=app.preview)
            self.previewpane.image = app.preview
            self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
        else:
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)
            self.previewframe.grid_columnconfigure(1, weight=1)
            self.previewpane = tk.Label(self.previewframe, text="[Preview Not Available]", height=30)
            self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
        self.overlaytoggle.config(relief=tk.SUNKEN)
        self.displayed = "overlay"

    # TODO: Proper exception handling

    # Automatically generate a threshold value.
    def autothreshold(self):
        try:
            threshold.set(maxvalue + 1)
            self.regenpreview("nochange")
        except:
            pass

    # Switch between overlay and original image in preview
    def switchpreview(self, cluster):
        if app.imagetypefail:
            return
        if not cluster:
            if app.displayed == "overlay":
                self.previewpane.grid_forget()
                self.previewpane2 = tk.Label(self.previewframe, image=app.nooverlay)
                self.previewpane2.image = app.nooverlay
                self.previewpane2.grid(row=1, column=1, sticky=tk.E + tk.W)
                self.overlaytoggle.config(relief=tk.RAISED)
                app.displayed = "original"
            elif app.displayed == "original":
                self.previewpane2.grid_forget()
                self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
                self.overlaytoggle.config(relief=tk.SUNKEN)
                app.displayed = "overlay"
            elif app.displayed == "clusters":
                self.previewpane.grid_forget()
                self.previewpane2 = tk.Label(self.previewframe, image=app.nooverlay)
                self.previewpane2.image = app.nooverlay
                self.previewpane2.grid(row=1, column=1, sticky=tk.E + tk.W)
                self.overlaytoggle.config(relief=tk.RAISED)
                app.displayed = "original"
        else:
            if app.displayed == "clusters":
                self.previewpane.grid_forget()
                self.previewpane2 = tk.Label(self.previewframe, image=app.nooverlay)
                self.previewpane2.image = app.nooverlay
                self.previewpane2.grid(row=1, column=1, sticky=tk.E + tk.W)
                self.overlaytoggle.config(relief=tk.RAISED)
                app.displayed = "original"
            else:
                self.regenpreview("cluster")
                self.overlaytoggle.config(relief=tk.SUNKEN)

    # TODO: Fix self assignments which aren't needed.


# About Window
class AboutWindow:
    # Simple about window frame
    def __init__(self, master):
        self.master = master
        self.aboutwindow = tk.Frame(self.master)
        self.logo = Image.open(resource_path("resources/QFLogoImg"))
        self.logoimg = ImageTk.PhotoImage(self.logo)
        self.logoimage = tk.Label(self.aboutwindow, image=self.logoimg)
        self.logoimage.pack(pady=(15, 0))
        self.heading = tk.Label(self.aboutwindow, text="QuantiFish", font=("Arial", 18), justify=tk.CENTER)
        self.heading.pack()
        self.line2 = tk.Label(self.aboutwindow, text="Version " + version, font=("Consolas", 10), justify=tk.CENTER)
        self.line2.pack(pady=(0, 5))
        self.line3 = tk.Label(self.aboutwindow, text="David Stirling, 2018", font=("Arial", 10), justify=tk.CENTER)
        self.line3.pack()
        self.line4 = tk.Label(self.aboutwindow, text="@DavidRStirling", font=("Arial", 10), justify=tk.CENTER)
        self.line4.pack(pady=(0, 15))
        self.aboutwindow.pack()


class FileListWindow:
    # Simple file list window frame
    def __init__(self, master):
        self.master = master
        self.filelistframe = tk.Frame(self.master)
        self.filelistscrollbar = ttk.Scrollbar(self.filelistframe)
        self.filelistlabel = ttk.Label(self.master, text="0 files to be analysed")
        self.filelistbox = tk.Listbox(self.filelistframe, yscrollcommand=self.filelistscrollbar.set)
        self.filelistbox.pack(expand=True, fill=tk.BOTH, side=tk.LEFT)
        self.filelistscrollbar.configure(command=self.filelistbox.yview)
        self.filelistscrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.filelistlabel.pack()
        self.filelistframe.pack(expand=True, fill=tk.BOTH)


# UI Initialiser
def main():
    global app
    root = tk.Tk()
    app = CoreWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()

# TODO: Add progress bar
# TODO: Update to ttk
