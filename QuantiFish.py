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
import tkinter as tk
import tkinter.filedialog as tkfiledialog
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
        self.master.wm_title("QuantiFish")
        self.master.iconbitmap(resource_path('resources/QFIcon'))
        self.master.resizable(width=False, height=False)
        self.master.grid_columnconfigure(1, minsize=100)
        self.master.grid_columnconfigure(2, weight=1, minsize=250)
        self.master.grid_columnconfigure(3, minsize=100)
        self.logframe = tk.Frame()
        self.scrollbar = tk.Scrollbar(self.logframe, orient=tk.VERTICAL)
        self.logbox = tk.Listbox(self.logframe, yscrollcommand=self.scrollbar.set, activestyle="none")
        self.logbox.grid(column=1, row=1, sticky=tk.W + tk.E + tk.N + tk.S)
        self.scrollbar.grid(column=2, row=1, sticky=tk.W + tk.E + tk.N + tk.S)
        self.logbox.insert(tk.END, "Log:")
        self.logframe.grid(column=1, columnspan=3, row=9, pady=(10, 0), sticky=tk.W + tk.E + tk.N + tk.S)
        self.logframe.grid_columnconfigure(1, weight=1, minsize=250)

        # Top Bar
        self.header = tk.Frame()
        self.img = ImageTk.PhotoImage(Image.open(resource_path("resources/QFLogo")))
        self.logo = tk.Label(self.header, image=self.img)
        self.logo.grid(column=1, row=1, rowspan=2, sticky=tk.W)
        self.title = tk.Label(self.header, text="QuantiFish", font=("Arial", 25),
                              justify=tk.CENTER).grid(column=2, columnspan=1, row=1, sticky=tk.E + tk.W)
        self.subtitle = tk.Label(self.header, text="Zebrafish Image Analyser", font=("Arial", 10),
                                 justify=tk.CENTER).grid(column=2, columnspan=1, row=2, sticky=tk.E + tk.W)
        self.header.grid(column=1, row=1, columnspan=2, sticky=tk.W + tk.E + tk.N + tk.S)
        self.about = tk.Button(master, height=1, text="About", command=self.about).grid(column=3, row=1,
                                                                                        rowspan=1,
                                                                                        sticky=tk.E + tk.W,
                                                                                        padx=5)

        # Directory Selector
        self.dirselect = tk.Button(master, height=2, text="Select Directory", command=self.directselect)
        self.dirselect.grid(column=1, row=2, rowspan=2, padx=5, sticky=tk.E + tk.W)
        self.currdir = tk.Entry(master, textvariable=directory)
        self.currdir.insert(tk.END, directory)
        self.currdir.config(state=tk.DISABLED)
        self.currdir.grid(column=2, row=2, sticky=tk.E + tk.W)
        global subdiron
        subdiron = tk.BooleanVar()
        subdiron.set(True)
        self.subdircheck = tk.Checkbutton(master, text="Include Subdirectories", variable=subdiron, onvalue=True,
                                          offvalue=False, command=self.subtoggle)
        self.subdircheck.grid(column=2, row=3, sticky=tk.E)

        # Preview Button
        self.previewbutton = tk.Button(master, height=2, text="Preview", command=self.openpreview)
        self.previewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W, padx=5)
        self.refreshpreviewbutton = tk.Button(self.master, height=2, text="Refresh",
                                              command=lambda: self.previewer_contents.regenpreview("refresh"))

        # Mode Selector
        global mode
        mode = tk.StringVar()
        mode.set("RGB")
        global chandet
        chandet = tk.BooleanVar()
        chandet.set(True)
        self.modebox = tk.Frame(bd=2, relief=tk.GROOVE)
        self.modebox.grid(column=1, row=4, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.modelabel = tk.Label(self.modebox, text="Image Type:").grid(column=1, row=1, sticky=tk.W)
        self.RGB = tk.Radiobutton(self.modebox, text="Colour", variable=mode, value="RGB",
                                  command=lambda: self.checkmode())
        self.RGB.grid(column=1, row=2, sticky=tk.W)
        self.RAW = tk.Radiobutton(self.modebox, text="Greyscale", variable=mode, value="RAW",
                                  command=lambda: self.checkmode())
        self.RAW.grid(column=1, row=3, sticky=tk.W)
        self.detecttoggle = tk.Checkbutton(self.modebox, text="Detect Channels", variable=chandet, onvalue=True,
                                           offvalue=False, command=self.detchan)
        self.detecttoggle.grid(column=1, row=4, sticky=tk.W)

        # Threshold Selector
        global threshold
        self.thrframe = tk.Frame(bd=2, relief=tk.GROOVE)
        threshold = tk.IntVar()
        threshold.set(60)
        self.threslide = tk.Scale(self.thrframe, from_=0, to=256, tickinterval=64, variable=threshold,
                                  orient=tk.HORIZONTAL, label="Threshold (minimum intensity to count):",
                                  command=lambda x: self.previewer_contents.regenpreview("nochange"))
        self.threslide.grid(column=2, row=4, rowspan=2, ipadx=150)
        self.setthr = tk.Entry(self.thrframe, textvariable=threshold, width=5, justify=tk.CENTER, )
        self.setthr.bind("<Return>", lambda x: self.previewer_contents.regenpreview("nochange"))
        self.setthr.grid(column=3, row=4, sticky=tk.S)
        self.thron = tk.BooleanVar()
        self.thron.set(True)
        self.thrcheck = tk.Checkbutton(self.thrframe, text="Apply\nThreshold", variable=self.thron, onvalue=True,
                                       offvalue=False, command=self.thrstatus)
        self.thrcheck.grid(column=3, row=5, sticky=tk.E)
        self.thrframe.grid(column=2, row=4, sticky=tk.W + tk.E + tk.N + tk.S, pady=5)

        # Colour Selector
        global desiredcolour
        desiredcolour = tk.IntVar()
        desiredcolour.set(1)
        self.colbox = tk.Frame(bd=2, relief=tk.GROOVE)
        self.colbox.grid(column=3, row=4, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.colabel = tk.Label(self.colbox, text="Quantifying:").grid(column=1, row=1, sticky=tk.W)
        self.opt1 = tk.Radiobutton(self.colbox, text="Blue", variable=desiredcolour, value=2, )
        self.opt1.grid(column=1, row=2, sticky=tk.W)
        self.opt2 = tk.Radiobutton(self.colbox, text="Green", variable=desiredcolour, value=1, )
        self.opt2.grid(column=1, row=3, sticky=tk.W)
        self.opt3 = tk.Radiobutton(self.colbox, text="Red", variable=desiredcolour, value=0, )
        self.opt3.grid(column=1, row=4, sticky=tk.W)

        # Cluster Explain Text
        self.clusterbox = tk.Frame(bd=2, relief=tk.GROOVE)
        self.clusterbox.grid(column=1, row=5, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.cluslabel = tk.Label(self.clusterbox, text="Clustering Analysis:").grid(column=1, row=1, sticky=tk.W)
        self.clusstatement = tk.Label(self.clusterbox, text="Search for large\nareas of staining")
        self.clusstatement.grid(column=1, row=2, sticky=tk.W + tk.E + tk.N + tk.S)

        # Cluster Selector
        global minarea
        global clusteron
        self.clusframe = tk.Frame(bd=2, relief=tk.GROOVE)
        minarea = tk.IntVar()
        minarea.set(0)
        self.areaslide = tk.Scale(self.clusframe, from_=0, to=1000, tickinterval=250, variable=minarea,
                                  orient=tk.HORIZONTAL, label="Minimum cluster size (pixels):",
                                  command=lambda x: self.previewer_contents.regenpreview("nochange"))
        self.areaslide.grid(column=2, row=4, rowspan=2, ipadx=150)
        self.setarea = tk.Entry(self.clusframe, textvariable=minarea, width=5, justify=tk.CENTER, )
        self.setarea.bind("<Return>", lambda x: self.previewer_contents.regenpreview("nochange"))
        self.setarea.grid(column=3, row=4, sticky=tk.S)
        clusteron = tk.BooleanVar()
        clusteron.set(False)
        self.cluscheck = tk.Checkbutton(self.clusframe, text="Analyse\nClustering", variable=clusteron, onvalue=True,
                                        offvalue=False, command=self.cluststatus)
        self.areaslide.config(state=tk.DISABLED)
        self.setarea.config(state=tk.DISABLED)
        self.cluscheck.grid(column=3, row=5, sticky=tk.E)
        self.clusframe.grid(column=2, row=5, sticky=tk.W + tk.E + tk.N + tk.S, pady=5)

        # Save Selector
        self.saveselect = tk.Button(master, height=2, text="Select Output", command=self.savesel)
        self.saveselect.grid(column=1, row=7, rowspan=2, sticky=tk.E + tk.W, padx=5)
        self.savefile = tk.Entry(master, textvariable=savedir)
        self.savefile.insert(tk.END, savedir)
        self.savefile.config(state=tk.DISABLED)
        self.savefile.grid(column=2, row=7, sticky=tk.E + tk.W)
        self.runbutton = tk.Button(master, height=2, text="Not Ready", bg="#cccccc", command=self.runscript,
                                   state=tk.DISABLED)
        self.runbutton.grid(column=3, row=7, rowspan=2, sticky=tk.E + tk.W, padx=5)

    # TODO: Preview window as class

    def preview_update(self):
        # trigger update if preview window exists.
        return

    def preview_window(self, outgoingimage):
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.previewwindow = tk.Toplevel(self.master)
        self.previewer_contents = PreviewWindow(self.previewwindow, outgoingimage)
        self.previewwindow.title("Previewer")
        self.previewwindow.iconbitmap(resource_path('resources/QFIcon'))
        self.previewwindow.update_idletasks()
        self.previewwindow.geometry('%dx%d+%d+%d' % (self.previewwindow.winfo_width(),
                                                     self.previewwindow.winfo_height(), x, y))
        self.previewwindow.protocol("WM_DELETE_WINDOW", app.closepreview)

    # Closes Preview Window    
    def closepreview(self):
        self.refreshpreviewbutton.grid_forget()
        self.previewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W, padx=5)
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

    # Checks mode and closes preview windows to avoid conflict on mode change.
    def checkmode(self):
        if mode.get() == "RGB":
            self.threslide.config(to=256, tickinterval=64)
            try:
                self.previewwindow.destroy()
                self.refreshpreviewbutton.grid_forget()
                self.previewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W, padx=5)
            except:
                pass
            self.logevent("Will run in RGB mode, use this if your images show in colour(s)")
        elif mode.get() == "RAW":
            self.threslide.config(to=65536, tickinterval=16384)
            try:
                self.previewwindow.destroy()
                self.refreshpreviewbutton.grid_forget()
                self.previewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W, padx=5)
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
        except:
            self.logevent("Directory not set")

    # Prompt user for output file.
    def savesel(self):
        global savedir
        global firstrun
        try:
            savedir = tkfiledialog.asksaveasfile(mode='w', defaultextension='.csv', initialfile='output.csv',
                                                 title='Save output file')
            self.friendlysavename = savedir.name
            self.savefile.config(state=tk.NORMAL)
            self.savefile.delete(0, tk.END)
            self.savefile.insert(tk.END, self.friendlysavename)
            self.savefile.config(state=tk.DISABLED)
            self.logevent("Data will save in: " + str(self.friendlysavename))
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
        if subdiron.get():
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

    # Open preview window
    def openpreview(self):
        global pospixels
        pospixels = tk.IntVar()

        self.fileslist = genfilelist(directory, subdiron.get())
        self.currentpreviewfile = 0
        try:
            if not self.dirstatus:
                self.previewfile = tkfiledialog.askopenfilename(filetypes=[('Tiff file', '*.tif')])
            else:
                self.previewfile = self.fileslist[self.currentpreviewfile]
        except:
            self.logevent("Unable to open file, did you select a .tif image?")
            return
        self.logevent("Opening preview")
        self.genpreview(self.previewfile, desiredcolour.get(), False)
        #        try:
        self.preview_window(self.preview)
        self.previewbutton.grid_forget()

        self.refreshpreviewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W + tk.N, padx=5)
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

    def genpreview(self, tgt, value, wantclusters):
        global maxvalue
        activemode = mode.get()
        thold = threshold.get()
        imfile = cv2.imread(tgt, -1)
        self.imagetypefail = False
        if activemode == "RGB" and imfile.dtype != "uint8":
            self.logevent("Error: This is not an RGB file")
            self.imagetypefail = True
            return
        elif activemode == "RAW" and imfile.dtype != "uint16":
            self.logevent("Error: This doesn't look like a RAW file")
            self.imagetypefail = True
            return
        if activemode == "RGB":
            imfile = cv2.cvtColor(imfile, cv2.COLOR_BGR2RGB)
            maxvalue = np.amax(imfile[:, :, value])
            nooverlay = Image.fromarray(imfile, 'RGB')
            mask = (imfile[:, :, value] > thold)
            pospixels.set(np.count_nonzero(mask))
            if wantclusters:
                threshtemp = imfile.copy()
                tmask2 = (imfile[:, :, value] < thold)
                threshtemp[tmask2] = (0, 0, 0)
                simpleclusters, numclusters = ndi.measurements.label(threshtemp)
                areacounts = np.unique(simpleclusters, return_counts=True)
                positivegroups = areacounts[0][1:][areacounts[1][1:] > minarea.get()]
                clustermask = np.isin(simpleclusters[:, :, 1], positivegroups)
            imfile[mask] = (0, 191, 255)
            if wantclusters:
                imfile[clustermask] = (0, 75, 255)
            self.preview2 = Image.fromarray(imfile, 'RGB')
            self.preview = self.preview2.resize((self.preview2.size[0] // 2, self.preview2.size[1] // 2))
            self.nooverlay = nooverlay.resize((nooverlay.size[0] // 2, nooverlay.size[1] // 2))
        elif activemode == "RAW":
            im = cv2.imread(tgt)
            maxvalue = np.amax(imfile[:, :])
            nooverlay = Image.fromarray(im, 'RGB')
            mask = (im[:, :, 1] > thold // 256)
            pospixels.set(np.count_nonzero(mask))
            if wantclusters:
                threshtemp = imfile.copy()
                tmask2 = (imfile[:, :] < thold)
                threshtemp[tmask2] = 0
                simpleclusters, numclusters = ndi.measurements.label(threshtemp)
                areacounts = np.unique(simpleclusters, return_counts=True)
                positivegroups = areacounts[0][1:][areacounts[1][1:] > minarea.get()]
                clustermask = np.isin(simpleclusters[:, :], positivegroups)
            im[mask] = (0, 191, 255)
            if wantclusters:
                im[clustermask] = (0, 75, 255)
            self.preview2 = Image.fromarray(im, 'RGB')
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
        writeme = tuple([exportpath]) + exportdata + tuple([threshold.get()] + [colour])
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
                mprokilla, directory, mode.get(), threshold.get(), subdiron.get(), desiredcolour.get(), findmeta()))
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
    for root, dirs, files in os.walk(directory):
        for folder in dirs:
            if "MetaData" in folder:
                app.logevent("Found MetaData folder, trying to pull image parameters...")
                metadir = os.path.join(root, folder)
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
def genfilelist(tgtdirectory, subdirectories):
    return [os.path.normpath(os.path.join(root, f)) for root, dirs, files in os.walk(tgtdirectory) for f in files if
            f.lower().endswith((".tif", ".tiff")) and not f.startswith(".") and (
                    root == tgtdirectory or subdirectories)]


# Master File Cycler
def cyclefiles(stopper, tgtdirectory, activemode, thresh, subdirectories, desiredcolourid, metastatus):
    filelist = genfilelist(tgtdirectory, subdirectories)
    # TODO: ADD A PROGRESSBAR FUNCTION
    # TODO: Handle inappropriate filetypes better.
    if not metastatus:
        for file in filelist:
            if stopper.wait():
                app.logevent("Analysing: " + file)
                data = cv2.imread(file, -1)
                if activemode == "RGB" and data.dtype != "uint8":
                    app.logevent("Not an RGB image, analysis skipped")
                elif activemode == "RAW" and data.dtype == "uint8":
                    app.logevent("Not a RAW image, analysis skipped")
                else:
                    try:

                        results = genstats(data, desiredcolourid, activemode, thresh, clusteron.get())
                        app.datawriter(file, results)
                    except:
                        app.logevent("Analysis failed, image may be corrupted")
    else:
        extention = colourid + ".tif"
        for file in filelist:
            if stopper.wait():
                if file.endswith(extention):
                    app.logevent("Analysing: " + file)
                    data = cv2.imread(file, -1)
                    if activemode == "RGB" and data.dtype != "uint8":
                        app.logevent("Not an RGB image, analysis skipped")
                    elif activemode == "RAW" and data.dtype == "uint8":
                        app.logevent("Not a RAW image, analysis skipped")
                    else:
                        # try:
                        results = genstats(data, desiredcolourid, activemode, thresh, clusteron.get())
                        app.datawriter(file, results)
                        # except:
                        #    app.logevent("Analysis failed, image may be corrupted")
                else:
                    pass
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
    if wantclusters:
        numclusters, targetclusters, numpeaks, numtargetpeaks, intintfil, countfil = getclusters(inputimage, th, mode2,
                                                                                                 x, minarea.get())
        return intint, count, max_value, min_value, numclusters, numpeaks, targetclusters, numtargetpeaks, intintfil, countfil
    return intint, count, max_value, min_value


## Cluster Analysis
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

    # Preview Window


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
    def __init__(self, master, firstimage):
        self.master = master
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.previewwindow = tk.Frame(self.master)
        self.previewtitle = tk.Label(self.previewwindow, text=("..." + app.previewfile[-100:]))
        self.previewtitle.grid(row=1, column=1, columnspan=5)

        self.previewframe = tk.Frame(self.previewwindow)  # Frame to aid holding and deleting preview images.
        self.previewpane = tk.Label(self.previewframe, image=firstimage)
        self.previewpane.image = firstimage
        self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
        self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N + tk.S + tk.E + tk.W)

        self.previewcontrols = tk.Frame(self.previewwindow, bd=2, relief=tk.GROOVE)  # Frame for preview controls.
        self.previewcontrols.grid(column=1, columnspan=5, row=3, sticky=tk.E + tk.W + tk.N + tk.S)
        self.prevpreviewbutton = tk.Button(self.previewcontrols, width=5, height=2, text="Previous\nFile",
                                           command=lambda: self.regenpreview("previous"))
        self.prevpreviewbutton.grid(column=1, row=1, rowspan=2, sticky=tk.E, padx=(3, 0), pady=5, ipadx=10)
        self.prevpreviewbutton.config(state=tk.DISABLED)
        self.nextpreviewbutton = tk.Button(self.previewcontrols, width=5, height=2, text="Next\nFile",
                                           command=lambda: self.regenpreview("next"))
        self.nextpreviewbutton.grid(column=2, row=1, rowspan=2, sticky=tk.E, padx=(0, 3), pady=5, ipadx=10)
        if not app.dirstatus:
            self.nextpreviewbutton.config(state=tk.DISABLED)
        self.changepreviewbutton = tk.Button(self.previewcontrols, width=5, height=2, text="Select\nFile",
                                             command=lambda: self.regenpreview("change"))
        self.changepreviewbutton.grid(column=3, row=1, rowspan=2, sticky=tk.E + tk.W, padx=3, ipadx=10)
        self.refresh = tk.Button(self.previewcontrols, height=2, text="Refresh",
                                 command=lambda: self.regenpreview("refresh")).grid(column=4, row=1, rowspan=2,
                                                                                    sticky=tk.E, padx=3, pady=5,
                                                                                    ipadx=10)
        self.overlaytoggle = tk.Button(self.previewcontrols, height=2, text="Show\nOverlay",
                                       command=lambda: self.switchpreview(False), relief=tk.SUNKEN)
        self.overlaytoggle.grid(column=5, row=1, rowspan=2, padx=3, pady=5, ipadx=10)
        self.clustertoggle = tk.Button(self.previewcontrols, height=2, text="Find\nClusters",
                                       command=lambda: self.switchpreview(True))
        self.clustertoggle.grid(column=6, row=1, rowspan=2, padx=3, pady=5, ipadx=10)

        self.overlaysave = tk.Button(self.previewcontrols, height=2, text="Save\nOverlay",
                                     command=lambda: savepreview())
        self.overlaysave.grid(column=7, row=1, rowspan=2, sticky=tk.W, padx=3, pady=5, ipadx=10)
        self.autothresh = tk.Button(self.previewcontrols, height=2, width=5, text="Auto\nThreshold",
                                    command=lambda: self.autothreshold()).grid(column=8, row=1, rowspan=2, sticky=tk.E,
                                                                               padx=5, pady=5, ipadx=15)
        self.pospixelbox = tk.Frame(self.previewcontrols, height=5, bd=2, relief=tk.RIDGE)
        self.poscountlabel = tk.Label(self.pospixelbox, text="Positive Pixels:").grid(column=1, row=1,
                                                                                      sticky=tk.W + tk.E, padx=(3, 0))
        self.poscount = tk.Label(self.pospixelbox, textvariable=pospixels)
        self.poscount.grid(column=1, row=2, sticky=tk.W + tk.E, )
        self.pospixelbox.grid(column=9, row=1, rowspan=2, sticky=tk.W, padx=(5, 0))
        self.previewexplain = tk.Label(self.previewwindow,
                                       text="Light blue pixels represent areas which will be counted as positive.\n Clicking \"Find Clusters\" will mark detected areas in a darker blue. \n Use AutoThreshold on a negative control or set threshold manually to remove autofluorescence.").grid(
            column=1, row=4, columnspan=5)
        self.previewwindow.pack()

    # Regenerate preview, reset window if the source image is changing.
    def regenpreview(self, mode):
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
                app.genpreview(app.previewfile, desiredcolour.get(), True)
                self.previewpane = tk.Label(self.previewframe, image=app.preview)
                self.previewpane.image = app.preview
                self.previewpane.grid(row=1, column=1, sticky=tk.E + tk.W)
            except:
                app.logevent("Error generating preview file")
            self.overlaytoggle.config(relief=tk.SUNKEN)
            self.displayed = "clusters"
            return
        elif mode == "change":
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

        try:
            app.genpreview(app.previewfile, desiredcolour.get(), False)
        except:
            app.logevent("Error generating preview file")
            return
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
