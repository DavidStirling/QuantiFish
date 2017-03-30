import tkinter as tk
import tkinter.filedialog as tkfiledialog
from PIL import Image
from PIL import ImageTk
import os
import csv
from xml.dom import minidom
import cv2
import numpy as np
import threading


# Global Variables
version = "1.0"
directory = "Select a directory to process"
savedir = "Select a location to save the output"
colour = "Unknown" #By default we don't know which channel we're looking at.
#__spec__ = None #Fix for a bug in Thonny


# Get path for unpacked Pyinstaller exe (MEIPASS), else default to current directory. 
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Core UI
class CoreWindow:
    def __init__(self, master):
        self.master = master
        self.savestatus = False
        self.dirstatus = False
        self.master.wm_title("QuantiFish")
        self.master.iconbitmap(resource_path('/resources/QFIconSml.ico'))
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
        self.img = ImageTk.PhotoImage(Image.open(resource_path("/resources/QFLogo.png")))
        self.logo = tk.Label(self.header, image=self.img)
        self.logo.grid(column=1, row=1, rowspan=2, sticky=tk.W)
        self.title = tk.Label(self.header, text="QuantiFish",font=("Arial", 25), justify=tk.CENTER).grid(column=2, columnspan=1, row=1, sticky=tk.E+tk.W)
        self.subtitle = tk.Label(self.header, text="Zebrafish Image Analyser",font=("Arial", 10), justify=tk.CENTER).grid(column=2, columnspan=1, row=2, sticky=tk.E+tk.W)
        self.header.grid(column=1, row=1, columnspan=2, sticky=tk.W + tk.E + tk.N + tk.S)
        self.about = tk.Button(master, height=1, text="About",command=self.about).grid(column=3, row=1, rowspan=1, sticky=tk.E + tk.W, padx=5)

        # Directory Selector
        self.dirselect = tk.Button(master, height=2, text="Select Directory", command=self.directselect)
        self.dirselect.grid(column=1, row=2, rowspan=2, padx=5, sticky=tk.E + tk.W)
        self.currdir = tk.Entry(master, textvariable=directory)
        self.currdir.insert(tk.END, directory)
        self.currdir.config(state=tk.DISABLED)
        self.currdir.grid(column=2, row=2, sticky=tk.E + tk.W)
        global subdiron
        subdiron = tk.StringVar()
        subdiron.set("True")
        self.subdircheck = tk.Checkbutton(master, text="Include Subdirectories", variable=subdiron, onvalue="True", offvalue="False", command=self.subtoggle)
        self.subdircheck.grid(column=2, row=3, sticky=tk.E)

        # Preview Button
        self.previewbutton = tk.Button(master, height=2, text="Preview", command=self.openpreview)
        self.previewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W, padx=5)

        # Mode Selector
        global mode
        mode = tk.StringVar()
        mode.set("RGB")
        global chandet
        chandet = tk.StringVar()
        chandet.set("True")
        self.modebox = tk.Frame(bd=2, relief=tk.GROOVE)
        self.modebox.grid(column=1, row=4, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.modelabel = tk.Label(self.modebox, text="Image Type:").grid(column=1, row=1, sticky=tk.W)
        self.RGB = tk.Radiobutton(self.modebox, text="Colour", variable=mode, value="RGB", command=lambda: self.checkmode())
        self.RGB.grid(column=1, row=2, sticky=tk.W)
        self.RAW = tk.Radiobutton(self.modebox, text="Greyscale", variable=mode, value="RAW", command=lambda: self.checkmode())
        self.RAW.grid(column=1, row=3, sticky=tk.W)
        self.detecttoggle = tk.Checkbutton(self.modebox, text="Detect Channels", variable=chandet, onvalue="True", offvalue="False", command=self.detchan)
        self.detecttoggle.grid(column=1, row=4, sticky=tk.W)

        # Threshold Selector
        global threshold
        self.thrframe = tk.Frame(bd=2, relief=tk.GROOVE)
        threshold = tk.IntVar()
        threshold.set(60)
        self.threslide = tk.Scale(self.thrframe, from_=0, to=256, tickinterval=64, variable=threshold, orient=tk.HORIZONTAL, label="Threshold (minimum intensity to count):", command=lambda x: self.regenpreview("nochange"))
        self.threslide.grid(column=2, row=4, rowspan=2, ipadx=150)
        self.setthr = tk.Entry(self.thrframe, textvariable=threshold, width=5, justify=tk.CENTER,)
        self.setthr.bind("<Return>", lambda x: self.regenpreview("nochange"))
        self.setthr.grid(column=3, row=4, sticky=tk.S)
        self.thron = tk.StringVar()
        self.thron.set("True")
        self.thrcheck = tk.Checkbutton(self.thrframe, text="Use Threshold", variable=self.thron, onvalue="True", offvalue="False", command=self.thrstatus)
        self.thrcheck.grid(column=3, row=5, sticky=tk.E)
        self.thrframe.grid(column=2, row=4, sticky=tk.W + tk.E + tk.N + tk.S, pady=5)

        # Colour Selector
        global desiredcolour
        desiredcolour = tk.IntVar()
        desiredcolour.set(1)
        self.colbox = tk.Frame(bd=2, relief=tk.GROOVE)
        self.colbox.grid(column=3, row=4, sticky=tk.W + tk.E + tk.N + tk.S, padx=5, pady=5)
        self.colabel = tk.Label(self.colbox, text="Quantifying:").grid(column=1, row=1, sticky=tk.W)
        self.opt1 = tk.Radiobutton(self.colbox, text="Blue", variable=desiredcolour, value=2,)
        self.opt1.grid(column=1, row=2, sticky=tk.W)
        self.opt2 = tk.Radiobutton(self.colbox, text="Green", variable=desiredcolour, value=1,)
        self.opt2.grid(column=1, row=3, sticky=tk.W)
        self.opt3 = tk.Radiobutton(self.colbox, text="Red", variable=desiredcolour, value=0,)
        self.opt3.grid(column=1, row=4, sticky=tk.W)

        # Save Selector
        self.saveselect = tk.Button(master, height=2, text="Select Output", command=self.savesel)
        self.saveselect.grid(column=1, row=7, rowspan=2, sticky=tk.E + tk.W, padx=5)
        self.savefile = tk.Entry(master, textvariable=savedir)
        self.savefile.insert(tk.END, savedir)
        self.savefile.config(state=tk.DISABLED)
        self.savefile.grid(column=2, row=7, sticky=tk.E + tk.W)
        self.runbutton = tk.Button(master, height=2, text="Not Ready", bg="#cccccc", command=self.runscript, state=tk.DISABLED)
        self.runbutton.grid(column=3, row=7, rowspan=2, sticky=tk.E + tk.W, padx=5)

    # Preview Window
    def preview_window(self, outgoingimage):
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.previewwindow = tk.Toplevel()
        self.previewwindow.title("Previewer")
        self.previewwindow.wm_attributes('-toolwindow', 1)
        self.previewtitle = tk.Label(self.previewwindow, text=("..." + self.previewfile[-100:]))
        self.previewtitle.grid(row=1, column=1, columnspan=5)

        self.previewframe = tk.Frame(self.previewwindow) #Frame to aid holding and deleting preview images.
        self.previewpane = tk.Label(self.previewframe, image=outgoingimage)
        self.previewpane.image = outgoingimage
        self.previewpane.grid(row=1, column=1,)
        self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N+tk.S+tk.E+tk.W)
        self.previewbutton.grid_forget()
        self.refreshpreviewbutton = tk.Button(self.master, height=2, text="Refresh", command=lambda: self.regenpreview("refresh"))
        self.refreshpreviewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W + tk.N, padx=5)
  
        self.previewcontrols = tk.Frame(self.previewwindow, bd=2, relief=tk.GROOVE) #Frame for preview controls.
        self.previewcontrols.grid(column=1, columnspan=5, row=3, sticky=tk.E + tk.W + tk.N + tk.S, padx=5)
        self.prevpreviewbutton = tk.Button(self.previewcontrols, width=5, height=2, text="Previous\nFile", command=lambda: self.regenpreview("previous"))
        self.prevpreviewbutton.grid(column=1, row=1, rowspan=2, sticky=tk.E, padx=(5,0), pady=5, ipadx=10)
        self.prevpreviewbutton.config(state=tk.DISABLED)
        self.nextpreviewbutton = tk.Button(self.previewcontrols, width=5, height=2, text="Next\nFile", command=lambda: self.regenpreview("next"))
        self.nextpreviewbutton.grid(column=2, row=1, rowspan=2, sticky=tk.E, padx=(0, 5), pady=5, ipadx=10)
        if self.dirstatus == False:
            self.nextpreviewbutton.config(state=tk.DISABLED)
        self.changepreviewbutton = tk.Button(self.previewcontrols, width=5, height=2, text="Select\nFile", command=lambda: self.regenpreview("change"))
        self.changepreviewbutton.grid(column=3, row=1, rowspan=2, sticky=tk.E + tk.W, padx=5, ipadx=10)
        self.refresh = tk.Button(self.previewcontrols, height=2, text="Refresh", command=lambda: self.regenpreview("refresh")).grid(column=4, row=1, rowspan=2, sticky=tk.E, padx=5, pady=5, ipadx=10)
        self.overlaytoggle = tk.Button(self.previewcontrols, height=2, text="Show\nOverlay", command= lambda:self.switchpreview(), relief=tk.SUNKEN)
        self.overlaytoggle.grid(column=5, row=1, rowspan=2, padx=5, pady=5, ipadx=10)
        self.overlaysave = tk.Button(self.previewcontrols, height=2, text="Save\nOverlay", command= lambda:self.savepreview())
        self.overlaysave.grid(column=6, row=1, rowspan=2, sticky=tk.W, padx=5, pady=5, ipadx=10)
        self.autothresh = tk.Button(self.previewcontrols, height=2, width=5, text="Auto\nThreshold", command=lambda: self.autothreshold()).grid(column=7, row=1, rowspan=2, sticky=tk.E, padx=5, pady=5, ipadx=15)
        self.pospixelbox = tk.Frame(self.previewcontrols, height=5, bd=2, relief=tk.RIDGE)
        self.poscountlabel = tk.Label(self.pospixelbox, text = "Positive Pixels:").grid(column=1, row=1, sticky=tk.W+tk.E, padx=(5,0))
        self.poscount = tk.Label(self.pospixelbox, textvariable = pospixels)
        self.poscount.grid(column=1, row=2, sticky=tk.W+tk.E,)
        self.pospixelbox.grid(column=8, row=1, rowspan=2, sticky=tk.W, padx=(5,0))
        self.previewexplain = tk.Label(self.previewwindow, text="Light blue pixels represent areas which will be counted as positive \n Use AutoThreshold on a negative control or set threshold manually to remove autofluorescence.").grid(column=1, row=4, columnspan=5)
        self.previewwindow.protocol("WM_DELETE_WINDOW", self.closepreview)
        self.previewwindow.focus_set()
        self.previewwindow.update_idletasks()
        self.previewwindow.wm_attributes("-topmost", True)
        self.previewwindow.geometry('%dx%d+%d+%d' % (self.previewwindow.winfo_width(), self.previewwindow.winfo_height(), x, y))

    # Closes Preview Window    
    def closepreview(self):
        self.refreshpreviewbutton.grid_forget()
        self.previewbutton.grid(column=3, row=2, rowspan=2, sticky=tk.E + tk.W, padx=5)
        self.previewwindow.destroy()

    # About Window
    def about(self):
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        x += self.master.winfo_width()
        self.aboutwindow = tk.Toplevel()
        self.aboutwindow.title("About")
        self.aboutwindow.wm_attributes('-toolwindow', 1)
        self.logoimg = ImageTk.PhotoImage(Image.open(resource_path("/resources/QFIconMid.png")))
        self.logoimage = tk.Label(self.aboutwindow, image=self.logoimg)
        self.logoimage.grid(row=1, column=1, pady=(15,0))
        self.heading = tk.Label(self.aboutwindow, text="QuantiFish", font=("Arial", 18), justify=tk.CENTER).grid(column=1, row=2)
        self.line2 = tk.Label(self.aboutwindow, text="Version " + version, font=("Consolas", 10), justify=tk.CENTER).grid(column=1, row=3, pady=(0, 5))
        self.line3 = tk.Label(self.aboutwindow, text="David Stirling, 2017", font=("Arial", 10), justify=tk.CENTER).grid(column=1, row=4)
        self.line4 = tk.Label(self.aboutwindow, text="@DavidRStirling", font=("Arial", 10), justify=tk.CENTER).grid(column=1, row=5, pady=(0, 15))
        self.aboutwindow.grid_columnconfigure(1, minsize=200)
        self.aboutwindow.focus_set()
        self.aboutwindow.grab_set()
        self.aboutwindow.update_idletasks()
        self.aboutwindow.geometry('%dx%d+%d+%d' % (self.aboutwindow.winfo_width(), self.aboutwindow.winfo_height(), x, y))
        self.aboutwindow.resizable(width=False, height=False)

    #Checks mode and closes preview windows to avoid conflict on mode change.
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

    # Detech threshold status and disable widgets if it's off.
    def thrstatus(self):
        if (self.thron.get()) == "True":
            self.logevent("Threshold Enabled")
            self.threslide.config(state=tk.NORMAL)
            self.setthr.config(state=tk.NORMAL)
        elif (self.thron.get()) == "False":
            self.logevent("Threshold Disabled")
            self.threslide.config(state=tk.DISABLED)
            self.setthr.config(state=tk.DISABLED)
            threshold.set(0)

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
            if self.dirstatus and self.savestatus == True:
                self.runbutton.config(state=tk.NORMAL, text="Run", bg="#99e699")
        except:
            self.logevent("Directory not set")

    #Prompt user for output file.  
    def savesel(self):
        global savedir
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
            try:
                self.headers()
            except:
                self.logevent("Unable to write to output file")
            if self.dirstatus and self.savestatus == True:
                self.runbutton.config(state=tk.NORMAL, text="Run", bg="#99e699")
            else:
                return
        except:
            self.logevent("Save file selection unsuccessful.")

    # Toggle inclusion of subdirectories
    def subtoggle(self):
        if subdiron.get() == "True":
            self.logevent("Will process images in subdirectories")
        else:
            self.logevent("Will skip images in subdirectories")

    # Explain to user whether they're going to detect channels.
    def detchan(self):
        if chandet.get() == "True":
            self.logevent("Will search for Leica metadata to identify colours and then only process images from the selected channel")
        else:
            self.logevent("Will analyse all files, you'll need to determine which images in the output are your desired channel")

    # Open preview window
    def openpreview(self):
        global pospixels
        pospixels = tk.IntVar()
        self.fileslist = genfilelist(directory, subdiron.get())
        self.currentpreviewfile = 0
        value = desiredcolour.get()
        try:
            if self.dirstatus == False:
                self.previewfile = tkfiledialog.askopenfilename(filetypes=[('Tiff file','*.tif')])
            else:
                self.previewfile = self.fileslist[self.currentpreviewfile]
        except:
            self.logevent("Unable to open file, did you select a .tif image?")
            return
        self.logevent("Opening preview")
        try:
            self.genpreview(self.previewfile, value)
            self.preview_window(self.preview)
            if self.imagetypefail==True:
                self.previewframe.destroy()
                self.previewframe = tk.Frame(self.previewwindow)
                self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N+tk.S+tk.E+tk.W)
                self.previewframe.grid_columnconfigure(1,weight=1)
                self.previewpane = tk.Label(self.previewframe, text="[Preview Not Available]", height = 30)
                self.previewpane.grid(row=1, column=1, sticky=tk.E+tk.W)
        except:
            self.logevent("Failed to generate preview, sorry!")

    # Thresholded Preview Generator
    def genpreview(self, tgt, value):
        global maxvalue
        activemode = mode.get()
        thold = threshold.get()
        imfile = cv2.imread(tgt, -1)
        self.imagetypefail=False
        if activemode == "RGB" and imfile.dtype != "uint8":
            self.logevent("Error: This is not an RGB file")
            self.imagetypefail=True
            return
        elif activemode == "RAW" and imfile.dtype != "uint16":
            self.logevent("Error: This doesn't look like a RAW file")
            self.imagetypefail=True
            return
        if activemode == "RGB":
            imfile = cv2.cvtColor(imfile, cv2.COLOR_BGR2RGB)
            maxvalue = np.amax(imfile[:,:,value])
            nooverlay = Image.fromarray(imfile, 'RGB')
            mask = (imfile[:,:,value] > thold)
            pospixels.set(np.count_nonzero(mask))
            imfile[mask] = (0, 191, 255)
            self.preview2 = Image.fromarray(imfile, 'RGB')
            self.preview = self.preview2.resize((self.preview2.size[0] // 2, self.preview2.size[1] // 2))
            self.nooverlay = nooverlay.resize((nooverlay.size[0] // 2, nooverlay.size[1] // 2))
        elif activemode == "RAW":
            im = cv2.imread(tgt)
            maxvalue = np.amax(imfile[:,:])
            nooverlay = Image.fromarray(im, 'RGB')
            mask = (im[:,:,1] > thold//256)
            pospixels.set(np.count_nonzero(mask))
            im[mask] = (0, 191, 255)
            self.preview2 = Image.fromarray(im, 'RGB')
            self.preview = self.preview2.resize((self.preview2.size[0] // 2, self.preview2.size[1] // 2))
            self.nooverlay = nooverlay.resize((nooverlay.size[0] // 2, nooverlay.size[1] // 2))
        self.nooverlay = ImageTk.PhotoImage(self.nooverlay)
        self.preview = ImageTk.PhotoImage(self.preview)
        self.displayed = "overlay"

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
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N+tk.S+tk.E+tk.W)
        elif mode == "change":
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow, height=500)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N+tk.S+tk.E+tk.W)
            try:
                self.previewfile = os.path.normpath(tkfiledialog.askopenfilename(filetypes=[('Tiff file','*.tif')]))
                self.previewtitle.destroy()
                self.previewtitle = tk.Label(self.previewwindow, text=("..." + self.previewfile[-100:]))
                self.previewtitle.grid(row=1, column=1, columnspan=5)
                if self.previewfile in self.fileslist:
                    self.currentpreviewfile = self.fileslist.index(self.previewfile)
                    if self.currentpreviewfile > 0:
                        self.prevpreviewbutton.config(state=tk.NORMAL)
                    elif self.currentpreviewfile == 0:
                        self.prevpreviewbutton.config(state=tk.DISABLED)
                    if self.currentpreviewfile < len(self.fileslist)-1:
                        self.nextpreviewbutton.config(state=tk.NORMAL)
                    else:
                        self.nextpreviewbutton.config(state=tk.DISABLED)
                else:
                    self.nextpreviewbutton.config(state=tk.DISABLED)
                    self.prevpreviewbutton.config(state=tk.DISABLED)
            except:
                self.logevent("Unable to open file, did you select a .tif image?")
                self.previewframe.grid_columnconfigure(1,weight=1)
                self.previewpane = tk.Label(self.previewframe, text="[Preview Not Available]", height = 30)
                self.previewpane.grid(row=1, column=1, sticky=tk.E+tk.W)
                return
        elif mode == "next":
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N+tk.S+tk.E+tk.W)
            self.currentpreviewfile += 1
            self.prevpreviewbutton.config(state=tk.NORMAL)
            if self.currentpreviewfile == (len(self.fileslist)-1):
                self.nextpreviewbutton.config(state=tk.DISABLED)
            else:
                self.nextpreviewbutton.config(state=tk.NORMAL)
            self.previewfile = self.fileslist[self.currentpreviewfile]
            self.previewtitle.destroy()
            self.previewtitle = tk.Label(self.previewwindow, text=("..." + self.previewfile[-100:]))
            self.previewtitle.grid(row=1, column=1, columnspan=5)
        elif mode == "previous":
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N+tk.S+tk.E+tk.W)
            self.currentpreviewfile -= 1
            self.nextpreviewbutton.config(state=tk.NORMAL)
            if self.currentpreviewfile == 0:
                self.prevpreviewbutton.config(state=tk.DISABLED)
            else:
                self.prevpreviewbutton.config(state=tk.NORMAL)
            self.previewfile = self.fileslist[self.currentpreviewfile]
            self.previewtitle.destroy()
            self.previewtitle = tk.Label(self.previewwindow, text=("..." + self.previewfile[-100:]))
            self.previewtitle.grid(row=1, column=1, columnspan=5)
        try:
            self.genpreview(self.previewfile, desiredcolour.get())
        except:
            self.logevent("Error generating preview file")
            return
        if self.imagetypefail==False: #Only show preview if the image is the right type.
            self.previewpane = tk.Label(self.previewframe, image=self.preview)
            self.previewpane.image = self.preview
            self.previewpane.grid(row=1, column=1)
        else:
            self.previewframe.destroy()
            self.previewframe = tk.Frame(self.previewwindow)
            self.previewframe.grid(row=2, column=1, columnspan=5, sticky=tk.N+tk.S+tk.E+tk.W)
            self.previewframe.grid_columnconfigure(1,weight=1)
            self.previewpane = tk.Label(self.previewframe, text="[Preview Not Available]", height = 30)
            self.previewpane.grid(row=1, column=1, sticky=tk.E+tk.W)
        self.overlaytoggle.config(relief=tk.SUNKEN)
        self.displayed = "overlay"

    # Automatically generate a threshold value.
    def autothreshold(self):
        try:
            threshold.set(maxvalue+1)
            self.regenpreview("nochange")
        except:
            pass

    # Switch between overlay and original image in preview
    def switchpreview(self):
        if self.imagetypefail==True:
            return
        if self.displayed == "overlay":
            self.previewpane.grid_forget()
            self.previewpane2 = tk.Label(self.previewframe, image=self.nooverlay)
            self.previewpane2.image = self.nooverlay
            self.previewpane2.grid(row=1, column=1)
            self.overlaytoggle.config(relief=tk.RAISED)
            self.displayed = "original"
        elif self.displayed == "original":
            self.previewpane2.grid_forget()
            self.previewpane.grid(row=1, column=1)
            self.overlaytoggle.config(relief=tk.SUNKEN)
            self.displayed = "overlay"

    # Save the preview.
    def savepreview(self):
        try:
            self.previewsavename = tkfiledialog.asksaveasfile(mode="w", defaultextension=".tif", title="Choose save location")
            self.preview2.save(self.previewsavename.name)
            self.logevent("Saving preview")
            self.previewsavename.close()
        except:
           self.logevent("Unable to save file, is this location valid?")
           return

    # Writes headers in output file
    def headers(self):
        self.headings = ('File', 'Integrated Intensity', 'Positive Pixels', 'Maximum', 'Minimum', 'Threshold', 'Channel')
        try:
            with open(savedir.name, 'w', newline="\n", encoding="utf-8") as f:
                self.writer = csv.writer(f)
                self.writer.writerow(self.headings)
                self.logevent("Save file created successfully")
        except:
            self.logevent("Unable to create save file")
        savedir.close()

    # Exports data to csv file
    def datawriter(self, exportpath, exportdata):
        writeme = tuple([exportpath]) + exportdata + tuple([threshold.get()] + [colour])
        try:
            with open(savedir.name, 'a', newline="\n", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(writeme)
        except:
            self.logevent("Unable to write to save file, please make sure it isn't open in another program!")

    # Script Starter
    def runscript(self):
        global mpro
        #Disable everything
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
        self.runbutton.config(text="Stop", bg="#ff4d4d", command=self.abort)
        try: #Setup thread for analysis to run in
            global mprokilla
            mprokilla = threading.Event()
            mprokilla.set()
            mpro = threading.Thread(target=cyclefiles, args=(mprokilla, directory, mode.get(), threshold.get(), subdiron.get(), desiredcolour.get(), findmeta()))
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
            if app.thron.get() == "True":
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
            if app.thron.get() == "True":
                app.setthr.config(state=tk.NORMAL)
                app.threslide.config(state=tk.NORMAL)
        except:
           self.logevent("Failed to stop script, eep! Try restarting the program.")
    
# Microscope Settings Detector, searches for metadata and determines channel identities
def findmeta():
    global colour
    global colourid
    global chandet
    greenid = "Unknown"
    blueid = "Unknown"
    redid = "Unknown"
    if chandet.get() == "False":
        colour="Unknown"
        return False
    for root, dirs, files in os.walk(directory):
        for dir in dirs:
            if "MetaData" in dir:
                app.logevent("Found MetaData folder, trying to pull image parameters...")
                metadir = os.path.join(root, dir)
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

#File List Generator
def genfilelist(tgtdirectory, subdirectories):
    if subdirectories == "False":
        return [os.path.normpath(os.path.join(root,f)) for root,dirs,files in os.walk(tgtdirectory) for f in files if f.endswith(".tif") and root == tgtdirectory]
    elif subdirectories == "True":
        return [os.path.normpath(os.path.join(root,f)) for root,dirs,files in os.walk(tgtdirectory) for f in files if f.endswith(".tif")]

# Master File Cycler
def cyclefiles(stopper, tgtdirectory, activemode, thresh, subdirectories, desiredcolourid, metastatus):
    filelist = genfilelist(tgtdirectory, subdirectories)
    if metastatus == False:
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
                        
                        results = genstats(data, desiredcolourid, activemode, thresh)
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
                        try:
                            results = genstats(data, desiredcolourid, activemode, thresh)
                            app.datawriter(file, results)
                        except:
                            app.logevent("Analysis failed, image may be corrupted")
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
    if app.thron.get() == "True":
        app.setthr.config(state=tk.NORMAL)
        app.threslide.config(state=tk.NORMAL)
    app.runbutton.config(text="Run", bg="#99e699", command=app.runscript)
    savedir.close()

# Data generators
def genstats(input, x, mode2, th):
    if mode2 == "RGB":
        input = cv2.cvtColor(input, cv2.COLOR_BGR2RGB)
        max = np.amax(input[:,:,x])
        min = np.amin(input[:,:,x])
        mask = (input[:,:,x] < th)
        try:
            input[mask] = (0, 0, 0)
        except:
            input[mask] = (0, 0, 0, 255)
        intint = np.sum(input[:,:,x])
        count = np.count_nonzero(input[:,:,x])
        return (intint, count, max, min)
    elif mode2 == "RAW":
        max = np.amax(input[:,:])
        min = np.amin(input[:,:])
        mask = (input[:,:] < th)
        input[mask] = (0)
        intint = np.sum(input[:,:])
        count = np.count_nonzero(input[:,:])
        return (intint, count, max, min)


# UI Initialiser
def main():
    global app
    root = tk.Tk()
    app = CoreWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
