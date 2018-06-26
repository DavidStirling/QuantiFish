# QuantiFish

  QuantiFish is a quantification program intended for measuring fluorescence in images of zebrafish, although use with images of other specimens is possible. To perform an analysis, specify the folder containing your images of interest, select which analysis settings you want, then choose a file to save the data to. When these parameters are set the “Run” button in the bottom right will become available to allow you to start the analysis.
  
  ![Main Window](https://i.imgur.com/IY0PXlO.png "Main Window")


## [Available for Download Here](https://github.com/DavidStirling/QuantiFish/releases/)


##  What's New in 2.0?
  QuantiFish 2.0 brings various enhancements:
  - Redesigned interface
  - Improved file handling 
  - Simplified setup and configuration
  - Support for very large images
  - Ability to export data for each region of staining within an image
  
  See the [full changelog](https://github.com/DavidStirling/QuantiFish/blob/master/ChangeLog.txt) for more!
  
##  Referencing
 Citations can be made using the following DOI:
 
 [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1298429.svg)](https://doi.org/10.5281/zenodo.1298429)
 
 Full manuscript coming soon!


##  Compatibility
  This program is supported on **Windows 7** or newer and **Mac OS X 10.12 “Sierra”** or newer. For other operating systems you can run the script from the source code (freely available on GitHub). This software was written in Python 3. Key dependencies are the NumPy, SciPy, Scikit-Image and PIL libraries. Standalone Windows and Mac releases are bundled all dependencies to simplify installation.


## Accepted Images
  The program reads **.tif** files which can be exported from most microscopes. Due to the way that image colour data is stored the program can only separate **R**ed, **G**reen and **B**lue in multi-channel images, so please don’t overlay in other colours (typically brightfield in grey) as this will interfere with the analysis.
  
  This version of the software currently assumes **one fish per image**.

  
  
## Output Data
  Results will be recorded in **.csv** files chosen by the user, which can be opened in most spreadsheet programs (e.g. Microsoft Excel). In the default output each row represents one image, but when saving cluster data is enabled a second output file is created in which each row represents a single region of staining within an image.
  
## Workflow and Settings
  This section details what each of the settings represents and how to operate the software.
  
###  File Input

**Set Input Directory** - Choose a directory from which images will be loaded.

**Include Subdirectories** - When checked the program will also scan folders inside the specified input directory.

**Generate File List** - Initiates a scan of the currently selected directory. A preview of the resulting list of files which will be analysed is displayed in a second window. This scan runs automatically when starting a run.
  
**Bit Depth** - (Advanced Users) - Different microscopes save data with various dynamic ranges which a single pixel's value can be (e.g. An 8-bit image has a range from 0-255 brightness levels). By default the software will automatically try to work out what type of image has been loaded, but you can use this box to override this if you encounter problems. Please do not mix images with different bit depths in the same run.

**File List Filter** - These options allow you to refine the file list to just the images you want to analyse. *Greyscale Only* mode will only load images with one channel, while *RGB Only* mode will only load images with multiple channels (you need to specify which channel to analyse). With no filter images will be scanned to see if only one channel has data.

**Keyword Filter** - Many microscopes assign a specific word to identify image channels (e.g "green" or "ch01"). Use this feature to selectively analyse images.

  ![File List Window](https://i.imgur.com/l1UZ0Tp.png "File List Window")

### Thresholding

When enabled, only pixels above the specified threshold will be counted as positive. Use this to remove autofluorescence. See the *Preview* function for more information.

### Cluster Analysis

**Analyse Clustering** - When enabled, the software will search for large areas of staining and perform additional analysis on these areas.

**Minimum Size** - Specifies the minimum size that an area of staining must be to be considered as a cluster.

**Save Cluster Data** - When enabled, the intensity and size data for each individual cluster within an image will be recorded in a second output file, specified under this option.


###  File Output

**Set Output Directory** - Choose a directory where output files will be saved.
  

### Previewing

  ![Previewer Window](https://i.imgur.com/Mgxe6lO.png "Previewer Window" )

**Preview** – The preview function will load an example image and generate an overlay of which pixels would be detected by the script using the current settings. Positive pixels are coloured light blue for visibility and ideally should only be present in the areas you’d consider as stained. The preview will update as you change the threshold. The overlay can be toggled on and off to aid thresholding. Large images will automatically be scaled down to fit the window.

The **Auto Threshold** button will try to pick a threshold based on the highest value in the current preview image (ideally a negative control). This is useful for getting an estimate to start from, although there will be some variance between different images. This function will also not work properly if your microscope has damaged pixels which always read positive, which can happen as camera sensors age.

If you’ve selected an input directory, the program will automatically open images from there for previewing. You can cycle between images in the target folder using the **Next/Previous File** buttons, or you can manually select a preview image with the **Select File** button – this can be from anywhere on your computer. You can also **save** a copy of the preview image overlay to aid presentation.

The **Find Clusters** option will preview which "clusters" will be counted as positive if cluster analysis is enabled. Positive clusters will be shown in dark blue. This can be adjusted using the *Minimum Size* option.

*N.B.* Clustering analysis is resource intensive and so the preview does not update automatically. In excessively large images the software may preview clustering in a lower resolution, which could contain slight inaccuracies.
  
The **Pixel Value** box displays the intensity of the pixel which is currently underneath the mouse cursor. Use this to assist with determining your threshold.
  
###  Run Analysis
 
 The *Run* button will activate when input and output directories are set. Upon running the *Progress Bar* will display progress through analysing the file list. Additional information and errors appear in the *Log* box.
 
 
###  Exported Data
 
Data per image contains the following statistics:
1.	File – the name and directory of the image being analysed
2.	Integrated Intensity – The sum of the positive pixels in the image, also equal to the average brightness of the stain multiplied by the stained area. This is your overall measure of fluorescence.
3.	Positive Pixels – The total number of pixels which were considered positive (above the threshold). This represents the stained area.
4.	Minimum – The lowest pixel value in the image.
5.	Maximum – The highest pixel value in the image.
6.	Displayed Threshold – The threshold specified on the scale by the user.
7.  Computed Threshold - The final value of the threshold after being adjusted for image bit depth. Pixels below this number were ignored. This is used to remove background.
8.	Channel – The colour of the image being analysed.

Additional data types when using cluster detection mode:

8.  Clusters – Areas of continuous fluorescence above the detection threshold. 
9.  Peaks – Individual points of high fluorescence. For the detection of multiple fluorescent objects in close proximity. A single cluster can be made up of multiple peaks.

  The results file should be locked for editing while the program is open, so please don’t try to modify it while the analysis is running. Multiple runs during the same session will be logged to the same file, although if you close the program and re-open it the program will clear pre-existing data should you try to select the same file.

When using **Save Cluster Data** mode, the following data per cluster is saved:

1.  File - The file path which the cluster belongs to.
2.  Cluster ID - The number of the cluster in the image.
3.  Cluster Location - Co-ordinates of the cluster's position in the image.
4.	Cluster Area - The number of pixels in the cluster.
5.	Maximum Intensity - The highest value within the cluster.
6.  Minimum Intensity - The lowest value within the cluster.
7.  Average Intensity - The mean value within the cluster.
8.  Integrated Intensity - The total intensity within the cluster.

 - - - -


If you have any questions, problems or suggestions, contact the developer either here or on Twitter - [@DavidRStirling](https://www.twitter.com/DavidRStirling)
