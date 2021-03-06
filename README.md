# QuantiFish

  QuantiFish is a quantification program intended for measuring fluorescence in images of zebrafish, although use with images of other specimens is possible. To perform an analysis, specify the folder containing your images of interest, select which analysis settings you want, then choose a file to save the data to. When these parameters are set the “Run” button in the bottom right will become available to allow you to start the analysis.
  
  ![Main Window](https://i.imgur.com/AXlTMdT.png "Main Window")


## [Available for Download Here](https://github.com/DavidStirling/QuantiFish/releases/)


##  What's New in 2.1?
  QuantiFish 2.1 introduces new measurements to analyse distribution of staining:
  - Fluor50 - Number of foci responsible for 50% of total staining. Provides insight into the distribution of staining between individual foci.
  - Grid Analysis - Images are divided into zones of a defined size. Zones containing foci are counted as positive. Measures spatial distribution while minimising the influence of groups of foci in close proximity.
  - Polygon Area - Area of the smallest possible polygon which contains all foci. Informs on 2D spatial distribution.
  - IFDmax - Maximum inter-focus distance, being the distance between the two furthest objects.
  
  **See below for more information!**
  
  See the [full changelog](https://github.com/DavidStirling/QuantiFish/blob/master/ChangeLog.txt) for more!
  
##  Referencing
 Citations can be made by referencing [this manuscript](https://www.nature.com/articles/s41598-020-59932-1):
 
> Stirling, D.R., Suleyman, O., Gil, E. et al. Analysis tools to quantify dissemination of pathology in zebrafish larvae. *Sci Rep* **10**, 3149 (2020).

[![DOILink](https://img.shields.io/badge/DOI-10.1038%2Fs41598--020--59932--1-blue)](https://doi.org/10.1038/s41598-020-59932-1)
 

##  Compatibility
  This program is supported on **Windows 7** or newer and **Mac OS X 10.12 “Sierra”** or newer. For other operating systems you can run the script from the source code (freely available on GitHub). This software was written in Python 3. Key dependencies are the NumPy, SciPy, Scikit-Image and PIL libraries. Standalone Windows and Mac releases are bundled with all dependencies to simplify installation.


## Accepted Images
  The program reads **.tif** files which can be exported from most microscopes. Due to the way that image colour data is stored the program can only separate **R**ed, **G**reen and **B**lue in multi-channel images, so please don’t overlay in other colours (typically brightfield in grey) as this will interfere with the analysis.
  
  This version of the software currently assumes **one fish per image**.

  
  
## Output Data
  Results will be recorded in **.csv** files chosen by the user, which can be opened in most spreadsheet programs (e.g. Microsoft Excel). In the default output each row represents one image, but when saving focus data is enabled a second output file is created in which each row represents a single region of staining within an image.
  
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

### Dissemination Analysis

**Analyse Foci** - When enabled, the software will search for continuous areas of staining and perform additional analysis on these areas.

**Minimum Size** - Specifies the minimum area that a region of staining must be to be considered as a focus.

**Calculate Fluor50** - When enabled, data for foci will be sorted by size (largest to smallest). From this the number of foci responsible for 50% of staining will be calculated. Cumulative results are also included in the focus output if saving is enabled below.

**Spatial Analysis** - Turning this on will analyse for spatial distribution, performing grid analysis, polygon area and IFDmax measurments.

**Box Size** - Grid analysis divides the image up into boxes of the size specified here. At the default 50, each image will be split into 50x50 squares and squares containing the midpoint of a focus will be counted as positive.

N.B. When using excessively large box sizes, this algorithm will try to keep the boxes as evenly sized as possible. For example, trying to divide a 1000 pixel-wide image into boxes of 700 would create 2x 500 pixel-wide boxes rather than using 700 + 300.

**Save Foci Data** - When enabled, the intensity and size data for each individual focus within an image will be recorded in a second output file, specified under this option.

###  Spatial Measures

**Stain Polygon Area** - Draws a polygon around all staining using the minimum possible vertices, like a rubber band. Good for evaluating how far staining has disseminated.

  ![Stain Polygon Area](https://i.imgur.com/OHOklDk.jpg "Stain Polygon Area")

**Focus Polygon Area** - Similar to the stain polygon, but using the midpoints of foci. Only foci larger than the minimum size will be used. Useful when areas of staining are irregularly shaped or when the area of an individual object would be very large by itself.

  ![Focus Polygon Area](https://i.imgur.com/wsKFX60.jpg "Focus Polygon Area")

**IFDmax** - Distance between the midpoints of the two furthest foci.

  ![IFDmax](https://i.imgur.com/W0rv23Y.jpg "IFDmax")

**Grid Analysis** - Image is divided into boxes (of the specified size) and boxes containing midpoints of foci are considered positive. Useful for examining dissemination when objects may be packed closely together. 

  ![Grid Analysis](https://i.imgur.com/A6dIWRA.jpg "Grid Analysis")

###  File Output

**Set Output Directory** - Choose a directory where output files will be saved.
  

### Previewing

  ![Previewer Window](https://i.imgur.com/Mgxe6lO.png "Previewer Window" )

**Preview** – The preview function will load an example image and generate an overlay of which pixels would be detected by the script using the current settings. Positive pixels are coloured light blue for visibility and ideally should only be present in the areas you’d consider as stained. The preview will update as you change the threshold. The overlay can be toggled on and off to aid thresholding. Large images will automatically be scaled down to fit the window.

The **Auto Threshold** button will try to pick a threshold based on the highest value in the current preview image (ideally a negative control). This is useful for getting an estimate to start from, although there will be some variance between different images. This function will also not work properly if your microscope has damaged pixels which always read positive, which can happen as camera sensors age.

If you’ve selected an input directory, the program will automatically open images from there for previewing. You can cycle between images in the target folder using the **Next/Previous File** buttons, or you can manually select a preview image with the **Select File** button – this can be from anywhere on your computer. You can also **save** a copy of the preview image overlay to aid presentation.

The **Find Foci** option will preview which foci will be counted as positive if foci analysis is enabled. Positive foci will be shown in dark blue. This can be adjusted using the *Minimum Size* option.

*N.B.* Foci analysis is resource intensive and so the preview does not update automatically. In excessively large images the software may preview foci in a lower resolution, which could contain slight inaccuracies.
  
The **Pixel Value** box displays the intensity of the pixel which is currently underneath the mouse cursor. Use this to assist with determining your threshold.
  
###  Run Analysis
 
 The *Run* button will activate when input and output directories are set. Upon running the *Progress Bar* will display progress through analysing the file list. Additional information and errors appear in the *Log* box.
 
 
###  Exported Data

Some columns may or may not be present in the output file depending on the analysis settings used.

#### Output File Contents

Data contained in output.csv (default name).

Column Name | Description \[Option]
------------ | -------------
File | The full path and name of the file analysed
Integrated Intensity | The sum of the positive pixels in the image, also equal to the average brightness of the stain multiplied by the stained area. This is your overall measure of fluorescence.
Positive Pixels | The total number of pixels which were considered positive (above the threshold). This represents the stained area.
Maximum | The highest pixel value in the image.
Minimum | The lowest pixel value in the image.
Stain Polygon | The area of a polygon containing all staining within the image using a minimum number of vertices. Similar to stretching a rubber band around the stained areas. Also known as a Convex Hull.
Total Foci | Areas of continuous fluorescence above the detection threshold. \[Analyse Foci]
Peaks | Individual points of high fluorescence, usually indicating the midpoint of a fluorescent object. A single focus can be made up of multiple peaks when objects are in close proximity. \[Analyse Foci]
Large Foci | Number of foci bigger than the size threshold set by the user. Termed "large foci". \[Analyse Foci]
Peaks in Large Foci | Number of peaks in foci larger than the minimum size. \[Analyse Foci]
Integrated Intensity in Large Foci | Sum of all staining within large foci. \[Analyse Foci]
Positive Pixels in Large Foci | Number of positive pixels within large foci. \[Analyse Foci]
Fluor50 | Minimum number of foci responsible for 50% of all staining in large foci. \[Calculate Fluor50]
Total Grid Boxes | Number of boxes an image was divided into during grid analysis. \[Spatial Analysis]
Positive Grid Boxes | Number of grid boxes which contained the midpoint of a focus of staining. \[Spatial Analysis]
Focus Polygon Area | The area of a polygon containing all focus midpoints within the image using a minimum number of vertices. \[Spatial Analysis]
IFDmax | Maximum Inter-Focus Distance. The distance between the two foci which are furthest apart. \[Spatial Analysis]
Displayed Threshold | The threshold specified on the scale by the user.
Computed Threshold | The final value of the threshold after being adjusted for image bit depth. Pixels below this number were ignored. This is used to remove background.
Channel | The colour of the image being analysed.

  The results file should be locked for editing while the program is open, so please don’t try to modify it while the analysis is running. Multiple runs during the same session will be logged to the same file, although if you close the program and re-open it the program will clear pre-existing data should you try to select the same file.


#### Foci File Contents

When using **Save Foci Data** mode, the following data per focus can be saved in foci.csv (default name). If using a size threshold only data for foci larger than or equal to that size will be recorded:

Column Name | Description \[Option]
------------ | -------------
File | The full path and name of the file containing the focus.
Focus ID | The number of the focus in the image.
Focus Location | Co-ordinates of the focus's position in the image. In the format (Y, X)
Focus Area | The number of pixels in the focus.
Maximum Intensity | The highest value within the focus.
Minimum Intensity | The lowest value within the focus.
Average Intensity | The mean value within the focus.
Integrated Intensity | The total intensity within the focus.
Percent Intensity | The percent of all staining in the image contributed by the focus. \[Calculate Fluor50]
Cumulative Intensity | Cumulative intensity of foci in the image. \[Calculate Fluor50]
Cumulative Percent Intensity | Cumulative percentage of all staining in the image. \[Calculate Fluor50]

 - - - -


If you have any questions, problems or suggestions, contact the developer either here or on Twitter - [@DavidRStirling](https://www.twitter.com/DavidRStirling)
