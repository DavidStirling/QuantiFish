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

import os
import sys
import threading
import time
import tkinter as tk
import tkinter.filedialog as tkfiledialog
from csv import writer
from tkinter import ttk

import numpy as np
from PIL import Image, ImageTk
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.transform import rescale

# Global Variables
version = "2.0 beta"
colour = "Unknown"  # By default we don't know which channel we're looking at.

# Parameters for different display modes.
depthmap = {"8-bit": (1, 256), "10-bit": (4, 1024), "12-bit": (16, 4096), "16-bit": (256, 65536)}
# (ID, multiplier, maxrange)
scalemultiplier, maxrange = depthmap["8-bit"]
manualbitdepth = False
currentdepth = 8


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
        self.depthlocked = False
        self.savestatus = False
        self.dirstatus = False
        self.about_window = None
        self.previewwindow = None
        self.file_list_window = None
        self.previewer_contents = None
        self.locked = False
        self.file_list_window_active = False
        self.firstrun = True  # Do we need to write headers to the output file?
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
        self.directory = tk.StringVar()
        self.directory.set("Select a directory to process")
        self.dirframe = ttk.Frame(self.corewrapper)
        self.currdir = ttk.Entry(self.dirframe, textvariable=self.directory)
        self.currdir.state(['readonly'])
        self.bitlabel = ttk.Label(self.dirframe, text="Bit Depth:")
        self.bitcheck = ttk.Combobox(self.dirframe, state="readonly")
        self.bitcheck['values'] = ('Auto Detect', '8-bit', '10-bit', '12-bit', '16-bit')
        self.bitcheck.current(0)
        self.bitcheck.bind("<<ComboboxSelected>>", self.bitmode_select)
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

        # Threshold Selector
        self.thrframe = ttk.LabelFrame(self.corewrapper, text="Threshold (minimum intensity to count)")
        self.threshold = tk.IntVar()
        self.threshold.set(60)
        self.thron = tk.BooleanVar()
        self.thron.set(True)
        self.threslide = tk.Scale(self.thrframe, from_=0, to=256, tickinterval=64, variable=self.threshold,
                                  orient=tk.HORIZONTAL, command=self.preview_update)
        self.setthr = ttk.Entry(self.thrframe, textvariable=self.threshold, width=5, justify=tk.CENTER, )
        self.setthr.bind("<Return>", self.preview_update)
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
        self.minarea.set(10)
        self.clusterbox = ttk.LabelFrame(self.corewrapper, relief=tk.GROOVE, text="Cluster Analysis")
        self.cluscheck = ttk.Checkbutton(self.clusterbox, text="Search for large areas of staining",
                                         variable=self.clusteron,
                                         onvalue=True, offvalue=False, command=self.cluststatus)
        self.setsizelabel = ttk.Label(self.clusterbox, text="Minimum Cluster Size:")
        self.areavalidate = (self.clusterbox.register(self.validate_number), '%P')
        self.setarea = ttk.Entry(self.clusterbox, textvariable=self.minarea, validate='focusout',
                                 validatecommand=self.areavalidate, width=5, justify=tk.CENTER)
        self.setarea.state(['disabled'])
        self.cluscheck.grid(column=1, row=1, padx=10)
        self.setsizelabel.grid(column=3, row=1)
        self.setarea.grid(column=4, row=1, padx=(0, 10))
        self.clusterbox.grid(column=2, row=3, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.clusterbox.grid_columnconfigure(2, weight=1)


        # Save Selector
        self.savedir = tk.StringVar()
        self.savedir.set("Select a file in which to save the output")
        self.saveselect = ttk.Button(self.corewrapper, text="Set Output File", command=self.savesel)
        self.savefile = ttk.Entry(self.corewrapper, textvariable=self.savedir)
        self.savefile.state(['readonly'])
        self.saveselect.grid(column=1, row=4, sticky=tk.NSEW, padx=5)
        self.savefile.grid(column=2, row=4, sticky=tk.E + tk.W, padx=5)

        # Preview/Run Buttons
        self.previewbutton = ttk.Button(self.corewrapper, text="Preview", command=self.openpreview)
        self.refreshpreviewbutton = ttk.Button(self.corewrapper, text="Refresh",
                                               command=self.preview_update)
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

    def bitmode_select(self, *args):
        global depthmap, scalemultiplier, maxrange
        if self.bitcheck.current() == 0:
            self.depthlocked = False
            scalemultiplier, maxrange = depthmap['8-bit']
        else:
            self.depthlocked = True
            depthnames = {1: '8-bit', 2: '10-bit', 3: '12-bit', 4: '16-bit'}
            id = depthnames[self.bitcheck.current()]
            scalemultiplier, maxrange = depthmap[id]

    def validate_number(self, newvalue):
        if newvalue in ("", "0"):
            self.minarea.set(1)
            return False
        try:
            if 0 < int(newvalue) < 100000:
                return True
            else:
                self.minarea.set(99999)
                return False
        except ValueError:
            self.logevent("Invalid entry")
            self.minarea.set(1)
            return False

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
        self.about_window.geometry('%dx%d+%d+%d' % (150, 230, x, y))

    def open_filelist_window(self):
        if self.file_list_window:
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
            self.file_list_window.protocol("WM_DELETE_WINDOW", app.close_filelist)
            self.file_list_window.geometry("700x500")

    def close_filelist(self):
        self.file_list_window.destroy()
        self.file_list_window = None

    def preview_filelist(self):
        if self.dirstatus:
            self.open_filelist_window()
            self.flapp.filelistlabel.config(text="Scanning, please wait...")
            filelist = genfilelist(self.directory.get(), self.list_stopper)
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
        # Modes: None, Greyscale, RGBDetect
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
                self.previewwindow = None
                self.refreshpreviewbutton.grid_forget()
                self.previewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)
            except:
                pass
            self.logevent("Will run in RGB mode, use this if your images show in colour(s)")
        elif mode.get() == "RAW":
            self.threslide.config(to=65536, tickinterval=16384)
            try:
                self.previewwindow.destroy()
                self.previewwindow = None
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
            self.threslide.config(state=tk.NORMAL)
            self.setthr.state(['!disabled'])
        else:
            self.threslide.config(state=tk.DISABLED)
            self.setthr.state(['disabled'])
            self.threshold.set(0)

    # Detect clustering status and disable widgets if it's off.
    def cluststatus(self):
        if self.clusteron.get():
            self.logevent("Cluster Analysis Enabled")
            self.logevent("WARNING: Logging format changed. Any data already in the output file will be lost.")
            self.setarea.state(['!disabled'])
            self.minarea.set(10)
        else:
            self.logevent("Cluster Analysis Disabled")
            self.logevent("WARNING: Logging format changed. Any data already in the output file will be lost.")
            self.setarea.state(['disabled'])
        self.firstrun = True

    # Prompt user to select directory.
    def directselect(self):
        self.close_previewer()
        try:
            newdirectory = tkfiledialog.askdirectory(title='Choose directory')
            if newdirectory == "":
                self.logevent("Directory not changed")
                return
            self.directory.set(newdirectory)
            self.logevent("Images will be read from: " + str(newdirectory))
            self.dirstatus = True
            if self.dirstatus and self.savestatus:
                self.runbutton.state(['!disabled'])
                self.runbutton.config(text="Run", bg="#99e699")
            if self.file_list_window_active:
                self.filelist_thread()
        except OSError:
            self.logevent("Directory not set")

    # Prompt user for output file.
    def savesel(self):
        try:
            newsavedir = tkfiledialog.asksaveasfile(mode='w', defaultextension='.csv', initialfile='output.csv',
                                                    title='Save output file')
            if not newsavedir:
                self.logevent("Save file not set")
                return
            self.savedir.set(newsavedir.name)
            self.logevent("Data will save in: " + str(newsavedir.name))
            self.savestatus = True
            self.firstrun = True
            if self.dirstatus and self.savestatus:
                self.runbutton.state(['!disabled'])
                self.runbutton.config(text="Run", bg="#99e699")
        except:
            self.logevent("Save file selection unsuccessful.")

    # Toggle inclusion of subdirectories
    def subtoggle(self):
        if self.subdiron.get():
            self.logevent("Will process images in subdirectories")
        else:
            self.logevent("Will skip images in subdirectories")

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
        # self.widgetslist = [self.logselect, self.currlog, self.prevsaveselect, self.prevdir, self.prevsavecheck, self.singlespotcheck, self.singleplanecheck, self.singleplaneentry]
        return

    # Open preview window
    def openpreview(self):
        global pospixels
        pospixels = tk.IntVar()
        app.list_stopper.set()
        self.fileslist = genfilelist(self.directory.get(), app.list_stopper)
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
        self.open_preview_window()
        self.previewbutton.grid_forget()

        self.refreshpreviewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)

        if self.imagetypefail:
            self.previewer_contents.previewpane.config(image='', text="[Preview Not Available]")
            self.previewer_contents.previewpane.image = None

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
            imfile = (imfile / scalemultiplier).astype('uint8')
            im = imfile.copy()  # Clone file for work
            # Reduce preview spawner to 8-bit range
            if imfile.shape[1] > 750:
                self.resizefactor = 750 / im.shape[1]
                self.imsml = rescale(im, self.resizefactor)
                self.imsml = (self.imsml * 255).astype('uint8')
            self.imlrg = np.repeat(imfile[:, :, np.newaxis], 3, axis=2)
            self.imsml = np.repeat(self.imsml[:, :, np.newaxis], 3, axis=2)
            nooverlay = Image.fromarray(self.imsml, 'RGB')
            self.nooverlay = ImageTk.PhotoImage(nooverlay)

        # self.imsml = resized 256 array
        # self.imlrg = full size 256 arrauy

        thold = self.threshold.get()

        if not wantclusters:
            im2 = self.imsml.copy()  # Clone the core image to work with it.
            mask = (im2[:, :, 1] > thold)
            im2[mask] = (0, 191, 255)
        else:  # Clustering needed
            im2 = self.imlrg.copy()
            threshtemp = self.imlrg.copy()
            mask = (im2[:, :, 1] > thold)
            tmask2 = (self.imlrg[:, :, 1] < thold)
            threshtemp[tmask2] = 0
            simpleclusters, numclusters = ndi.measurements.label(threshtemp)
            areacounts = np.unique(simpleclusters, return_counts=True)
            positivegroups = areacounts[0][1:][areacounts[1][1:] > self.minarea.get()]
            clustermask = np.isin(simpleclusters[:, :, 1], positivegroups)
            im2[mask] = (0, 191, 255)
            im2[clustermask] = (0, 75, 255)
            # Resize preview spawner if it's too large for the window
            if im2.shape[1] > 750:
                im2 = rescale(im2, self.resizefactor)
                im2 = (im2 * 255).astype('uint8')

        preview = Image.fromarray(im2, 'RGB')
        self.preview = ImageTk.PhotoImage(preview)
        self.displayed = "overlay"

    """    def genpreview(self, tgt, wantclusters, newimage):
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
        # TODO: Apply rescaler after previewgeneration
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
        """

    def preview_update(self, *args):
        if self.previewwindow and not self.imagetypefail:
            self.previewer_contents.regenpreview("nochange")

    def open_preview_window(self):
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.previewwindow = tk.Toplevel(self.master)
        self.previewer_contents = PreviewWindow(self.previewwindow)
        self.previewwindow.title("Previewer")
        self.previewwindow.iconbitmap(resource_path('resources/QFIcon'))
        self.previewwindow.update_idletasks()
        if app.previewwindow.winfo_reqheight() + 10 < 610:
            reqh = 610
        else:
            reqh = app.previewwindow.winfo_reqheight() + 10
        self.previewwindow.geometry('%dx%d+%d+%d' % (app.previewwindow.winfo_reqwidth() + 10, reqh, x, y))
        self.previewwindow.protocol("WM_DELETE_WINDOW", app.close_previewer)

    # Closes Preview Window
    def close_previewer(self):
        if self.previewwindow:
            self.refreshpreviewbutton.grid_forget()
            self.previewbutton.grid(column=1, row=5, sticky=tk.NSEW, padx=5)
            self.previewwindow.destroy()
            self.previewwindow = None

    # TODO: Replace CV2 with skimage file handling
    # TODO: Bit depth detection

    # Writes headers in output file
    def headers(self):
        if self.clusteron.get():
            headings = (
                'File', 'Integrated Intensity', 'Positive Pixels', 'Maximum', 'Minimum', 'Total Clusters',
                'Total Peaks',
                'Large Clusters', 'Peaks in Large Clusters', 'Integrated Intensity in Large Clusters',
                'Positive Pixels in Large Clusters', 'Threshold', 'Channel')
        else:
            headings = (
                'File', 'Integrated Intensity', 'Positive Pixels', 'Maximum', 'Minimum', 'Threshold', 'Channel')
        try:
            with open(self.savedir.get(), 'w', newline="\n", encoding="utf-8") as f:
                self.writer = writer(f)
                self.writer.writerow(headings)
                self.logevent("Save file created successfully")
        except:
            self.logevent("Unable to create save file")

    # Exports data to csv file
    def datawriter(self, exportpath, exportdata):
        writeme = tuple([exportpath]) + exportdata + tuple([self.threshold.get()] + [colour])
        try:
            with open(self.savedir.get(), 'a', newline="\n", encoding="utf-8") as f:
                datawriter = writer(f)
                datawriter.writerow(writeme)
        except Exception as e:
            print(e)
            self.logevent("Unable to write to save file, please make sure it isn't open in another program!")

    # TODO: Better UI toggling.

    # Script Starter
    def runscript(self):
        global mpro
        # Disable everything
        self.dirselect.state(['disabled'])
        self.subdircheck.state(['disabled'])
        self.RGB.state(['disabled'])
        self.RAW.state(['disabled'])
        self.detecttoggle.state(['disabled'])
        self.opt1.state(['disabled'])
        self.opt2.state(['disabled'])
        self.opt3.state(['disabled'])
        self.saveselect.state(['disabled'])
        self.thrcheck.state(['disabled'])
        self.setthr.state(['disabled'])
        self.threslide.state(['disabled'])
        self.cluscheck.state(['disabled'])
        self.areaslide.state(['disabled'])
        self.setarea.state(['disabled'])
        self.runbutton.config(text="Stop", bg="#ff4d4d", command=self.abort)
        if self.firstrun:
            try:
                self.headers()
                self.firstrun = False
            except:
                self.logevent("Unable to write to output file")
        try:  # Setup thread for analysis to run in
            global mprokilla
            mprokilla = threading.Event()
            mprokilla.set()
            mpro = threading.Thread(target=cyclefiles, args=(
                mprokilla, self.directory.get(), mode.get(), self.threshold.get(), desiredcolour.get()))
            mpro.setDaemon(True)
            mpro.start()
        except:
            app.logevent("Unable to acquire data, something went wrong!")
            app.dirselect.state(['!disabled'])
            app.subdircheck.state(['!disabled'])
            app.RGB.state(['!disabled'])
            app.RAW.state(['!disabled'])
            app.detecttoggle.state(['!disabled'])
            app.opt1.state(['!disabled'])
            app.opt2.state(['!disabled'])
            app.opt3.state(['!disabled'])
            app.saveselect.state(['!disabled'])
            app.thrcheck.state(['!disabled'])
            app.cluscheck.state(['!disabled'])
            if app.clusteron.get():
                app.areaslide.state(['!disabled'])
                app.setarea.state(['!disabled'])
            if app.thron.get():
                app.setthr.state(['!disabled'])
                app.threslide.state(['!disabled'])
            return
        return

    # Stops a running script
    def abort(self):
        try:
            mprokilla.clear()
            self.logevent("Aborted run")
            app.runbutton.config(text="Run", bg="#99e699", command=app.runscript)
            app.dirselect.state(['!disabled'])
            app.subdircheck.state(['!disabled'])
            app.RGB.state(['!disabled'])
            app.RAW.state(['!disabled'])
            app.detecttoggle.state(['!disabled'])
            app.opt1.state(['!disabled'])
            app.opt2.state(['!disabled'])
            app.opt3.state(['!disabled'])
            app.saveselect.state(['!disabled'])
            app.thrcheck.state(['!disabled'])
            app.cluscheck.state(['!disabled'])
            if app.clusteron.get():
                app.areaslide.state(['!disabled'])
                app.setarea.state(['!disabled'])
            if app.thron.get():
                app.setthr.state(['!disabled'])
                app.threslide.state(['!disabled'])
        except:
            self.logevent("Failed to stop script, eep! Try restarting the program.")


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
def cyclefiles(stopper, tgtdirectory):
    global scalemultiplier
    app.list_stopper.set()
    thresh = app.threshold.get() * scalemultiplier
    filelist = genfilelist(tgtdirectory, app.list_stopper)
    # TODO: ADD A PROGRESSBAR FUNCTION
    # TODO: Handle inappropriate filetypes better.
    for file in filelist:

        if stopper.wait():
            app.logevent("Analysing: " + file)
            imagedata, filetype = open_file(file)
            if not app.depthlocked:
                app.depthlocked = True
            if filetype == "Invalid":
                app.logevent("Invalid file type, analysis skipped")
            else:
                try:
                    results = genstats(imagedata, thresh, app.clusteron.get())
                    app.datawriter(file, results)
                except:
                    app.logevent("Analysis failed, image may be corrupted")

    # TODO: Progress bar updater here.
    # TODO: Unlock UI
    app.logevent("Script Complete!")
    app.dirselect.state(['!disabled'])
    app.subdircheck.state(['!disabled'])
    app.RGB.state(['!disabled'])
    app.RAW.state(['!disabled'])
    app.detecttoggle.state(['!disabled'])
    app.opt1.state(['!disabled'])
    app.opt2.state(['!disabled'])
    app.opt3.state(['!disabled'])
    app.saveselect.state(['!disabled'])
    app.thrcheck.state(['!disabled'])
    app.cluscheck.state(['!disabled'])
    if app.clusteron.get():
        app.areaslide.state(['!disabled'])
        app.setarea.state(['!disabled'])
    if app.thron.get():
        app.setthr.state(['!disabled'])
        app.threslide.state(['!disabled'])
    app.runbutton.config(text="Run", bg="#99e699", command=app.runscript)


# Open a file and convert it into a single channel image.
def open_file(filepath):
    from skimage.io import imread
    currentmode = app.filtermode.get()
    chandef = {"Detect": 0, "Blue": 1, "Green": 2, "Red": 3}
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

        if currentmode == 2 and desiredcolour != 0:  # Not in detect mode
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
    global depthmap, currentdepth, scalemultiplier, maxrange, depthname, manualbitdepth
    max_value = imgarray.max()
    if manualbitdepth or app.depthlocked:
        return
    if max_value < 256:
        depth = 8
        depthname = '8-bit'
    elif 256 <= max_value < 1024:
        depth = 10
        depthname = '10-bit'
    elif 1024 <= max_value < 4096:
        depth = 12
        depthname = '12-bit'
    else:
        depth = 16
        depthname = '16-bit'
    if currentdepth < depth:
        scalemultiplier, maxrange, = depthmap[depthname]
        currentdepth = depth
        app.logevent("Detected bit depth: " + depthname)
        # TODO: Config thresholds
        # depthname.set(name)
    # Check if run is ongoing and alert if depth changes.
    return


# Data generators
def genstats(inputimage, threshold, wantclusters):  # TODO: Remove mode determination
    max_value = np.amax(inputimage)
    min_value = np.amin(inputimage)
    mask = (inputimage < threshold)
    inputimage[mask] = 0
    intint = np.sum(inputimage)
    count = np.count_nonzero(inputimage)
    results_pack = (intint, count, max_value, min_value)
    if wantclusters:
        cluster_results = getclusters(inputimage, threshold, app.minarea.get())
        results_pack += cluster_results
    return results_pack


# Cluster Analysis
def getclusters(trgtimg, threshold, minimumarea):
    # Find and count peaks above threshold, assign labels to clusters of stainng.

    localmax = peak_local_max(trgtimg, indices=False, threshold_abs=threshold)
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
    localmax2 = peak_local_max(filthresholded[:, :], indices=False, threshold_abs=threshold)
    targetpeaks, numtargetpeaks = ndi.measurements.label(localmax2)
    return numclusters, numpeaks, targetclusters, numtargetpeaks, intintfil, countfil


def savepreview():
    try:
        previewsavename = tkfiledialog.asksaveasfile(mode="w", defaultextension=".tif",
                                                     title="Choose save location")
        app.previewer_contents.preview.save(previewsavename.name)
        app.logevent("Saving preview")
        previewsavename.close()
    except:
        app.logevent("Unable to save file, is this location valid?")
        return


class PreviewWindow:
    def __init__(self, master):
        self.master = master
        style = ttk.Style()
        style.configure('preview.TButton', sticky='nswe', justify='center', width=6, height=2, state='!disabled')
        style.configure('imgwindow.TLabel', anchor='center')
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.previewwindow = ttk.Frame(self.master)
        self.previewtitle = ttk.Label(self.previewwindow, text=("..." + app.previewfile[-100:]))

        if not app.imagetypefail:
            self.previewpane = ttk.Label(self.previewwindow, style='imgwindow.TLabel', image=app.preview)
            self.previewpane.image = app.preview
        else:
            self.previewpane = ttk.Label(self.previewwindow, style='imgwindow.TLabel', text="[Preview Not Available]")
        self.previewpane.bind("<Motion>", self.hover_pixel)
        self.previewcontrols = ttk.Frame(self.previewwindow, borderwidth=2,
                                         relief=tk.GROOVE)  # Frame for preview controls.
        self.prevpreviewbutton = ttk.Button(self.previewcontrols, style='preview.TButton', text="Previous\nFile",
                                            command=lambda: self.regenpreview("previous"))
        self.prevpreviewbutton.state(['disabled'])
        self.nextpreviewbutton = ttk.Button(self.previewcontrols, style='preview.TButton', text="Next\nFile",
                                            command=lambda: self.regenpreview("next"))
        if not app.dirstatus:
            self.nextpreviewbutton.state(['disabled'])
        self.changepreviewbutton = ttk.Button(self.previewcontrols, style='preview.TButton', text="Select\nFile",
                                              command=lambda: self.regenpreview("change"))
        self.refresh = ttk.Button(self.previewcontrols, style='preview.TButton', text="Refresh",
                                  command=app.preview_update)
        self.overlaytoggle = ttk.Button(self.previewcontrols, style='preview.TButton', text="Show\nOverlay",
                                        command=lambda: self.switchpreview(False))
        self.overlaytoggle.state(['pressed'])
        self.clustertoggle = ttk.Button(self.previewcontrols, style='preview.TButton', text="Find\nClusters",
                                        command=lambda: self.switchpreview(True))
        self.overlaysave = ttk.Button(self.previewcontrols, style='preview.TButton', text="Save\nOverlay",
                                      command=lambda: savepreview())
        self.autothresh = ttk.Button(self.previewcontrols, style='preview.TButton', text="Auto\nThreshold",
                                     command=lambda: self.autothreshold())

        # TODO: Replace with current pixel value
        self.currpixel = tk.IntVar()
        self.currpixel.set(0)
        self.pixelbox = ttk.LabelFrame(self.previewcontrols, text="Pixel Value")
        self.pixelvalue = ttk.Label(self.pixelbox, textvariable=self.currpixel)

        self.prevpreviewbutton.grid(column=1, row=1, sticky=tk.E, padx=(3, 0), pady=5, ipadx=10)
        self.nextpreviewbutton.grid(column=2, row=1, sticky=tk.E, padx=(0, 3), pady=5, ipadx=10)
        self.changepreviewbutton.grid(column=3, row=1, sticky=tk.E + tk.W, padx=3, ipadx=10)
        self.refresh.grid(column=4, row=1, sticky=tk.NSEW, padx=3, pady=5, ipadx=10)
        self.overlaytoggle.grid(column=5, row=1, padx=3, pady=5, ipadx=10)
        self.clustertoggle.grid(column=6, row=1, padx=3, pady=5, ipadx=10)
        self.overlaysave.grid(column=7, row=1, sticky=tk.W, padx=3, pady=5, ipadx=10)
        self.autothresh.grid(column=8, row=1, sticky=tk.E, padx=5, pady=5, ipadx=15)
        self.pixelbox.grid(column=9, row=1, sticky=tk.W, padx=5)
        self.pixelvalue.pack()

        self.previewtitle.pack()
        self.previewcontrols.pack()
        self.previewpane.pack()
        self.previewwindow.pack(fill='both', expand=True)

    # Regenerate preview, reset window if the source image is changing.
    def regenpreview(self, mode):
        newfile = False
        if not self.previewwindow:
            return
        if mode == "cluster":
            # try:
            app.genpreview(app.previewfile, True, newfile)
            self.previewpane.config(image=app.preview)
            self.previewpane.image = app.preview
            # except Exception as e:
            #    app.logevent("Error generating preview file")
            #    print(e)
            self.overlaytoggle.state(['active'])
            self.displayed = "clusters"
            return
        elif mode == "change":
            newfile = True
            try:
                app.previewfile = os.path.normpath(tkfiledialog.askopenfilename(filetypes=[('Tiff file', '*.tif')]))
                self.previewtitle.config(text=("..." + app.previewfile[-100:]))
                if app.previewfile in app.fileslist:
                    app.currentpreviewfile = app.fileslist.index(app.previewfile)
                    if app.currentpreviewfile > 0:
                        self.prevpreviewbutton.state(['!disabled'])
                    elif app.currentpreviewfile == 0:
                        self.prevpreviewbutton.state(['disabled'])
                    if app.currentpreviewfile < len(app.fileslist) - 1:
                        self.nextpreviewbutton.state(['!disabled'])
                    else:
                        self.nextpreviewbutton.state(['disabled'])
                else:
                    self.nextpreviewbutton.state(['disabled'])
                    self.prevpreviewbutton.state(['disabled'])
            except Exception as e:
                print(e)
                app.logevent("Unable to open file, did you select a .tif image?")
                self.previewpane.config(text="[Preview Not Available]", image='')
                self.previewpane.image = None
                return
        elif mode == "next":
            newfile = True
            app.currentpreviewfile += 1
            self.prevpreviewbutton.state(['!disabled'])
            if app.currentpreviewfile == (len(app.fileslist) - 1):
                self.nextpreviewbutton.state(['disabled'])
            else:
                self.nextpreviewbutton.state(['!disabled'])
            app.previewfile = app.fileslist[app.currentpreviewfile]
            self.previewtitle.config(text=("..." + app.previewfile[-100:]))
        elif mode == "previous":
            newfile = True
            app.currentpreviewfile -= 1
            self.nextpreviewbutton.state(['!disabled'])
            if app.currentpreviewfile == 0:
                self.prevpreviewbutton.state(['disabled'])
            else:
                self.prevpreviewbutton.state(['!disabled'])
            app.previewfile = app.fileslist[app.currentpreviewfile]
            self.previewtitle.config(text=("..." + app.previewfile[-100:]))

        # try:
        app.genpreview(app.previewfile, False, newfile)
        # TODO: Re-enable preview failcheck
        # except Exception as e:
        #    app.logevent("Error generating preview file")
        #    print(e)
        #    return
        if not app.imagetypefail:  # Only show preview if the image is the right type.
            self.previewpane.config(image=app.preview)
            self.previewpane.image = app.preview
        else:
            self.previewpane.config(image='', text="[Preview Not Available]")
            self.previewpane.image = None
        if app.previewwindow.winfo_reqheight() + 10 < 610:
            reqh = 610
        else:
            reqh = app.previewwindow.winfo_reqheight() + 10
        app.previewwindow.geometry('%dx%d' % (app.previewwindow.winfo_reqwidth() + 10, reqh))
        self.displayed = "overlay"

        # Get pixel intensity under the mouse pointer.

    def hover_pixel(self, event):
        if not app.imagetypefail:
            ymax, xmax, axes = app.imsml.shape
            if event.y < ymax and event.x < xmax:
                pixel = app.imsml[event.y][event.x][0]
                self.currpixel.set(pixel)
        else:
            self.currpixel.set(0)

    # TODO: Proper exception handling

    # Automatically generate a threshold value.
    def autothreshold(self):
        try:
            app.threshold.set(maxvalue + 1)
            self.regenpreview("nochange")
        except:
            pass

    # Switch between overlay and original image in preview
    def switchpreview(self, cluster):
        if app.imagetypefail:
            return
        if not cluster or app.displayed == "clusters":
            if app.displayed == "original":
                self.previewpane.config(image=app.preview)
                self.previewpane.image = app.preview
                self.overlaytoggle.state(['pressed'])
                app.displayed = "overlay"
            else:
                self.previewpane.config(image=app.nooverlay)
                self.previewpane.image = app.nooverlay
                self.overlaytoggle.state(['!pressed'])
                app.displayed = "original"
        else:
            self.regenpreview("cluster")
            self.overlaytoggle.state(['pressed'])

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
        self.logoimage.pack(pady=(5, 0))
        self.heading = tk.Label(self.aboutwindow, text="QuantiFish", font=("Arial", 18), justify=tk.CENTER)
        self.heading.pack()
        self.line2 = tk.Label(self.aboutwindow, text="Version " + version, font=("Consolas", 10), justify=tk.CENTER)
        self.line2.pack(pady=(0, 5))
        self.line3 = tk.Label(self.aboutwindow, text="David Stirling, 2018", font=("Arial", 10), justify=tk.CENTER)
        self.line3.pack()
        self.line4 = tk.Label(self.aboutwindow, text="@DavidRStirling", font=("Arial", 10), justify=tk.CENTER)
        self.line4.pack(pady=(0, 5))
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
