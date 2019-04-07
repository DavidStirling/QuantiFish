# QuantiFish

  QuantiFish is a quantification program intended for measuring fluorescence in images of zebrafish, although use with images of other specimens is possible. To perform an analysis, specify the folder containing your images of interest, select which analysis settings you want, then choose a file to save the data to. When these parameters are set the “Run” button in the bottom right will become available to allow you to start the analysis.
  
  ![Main Window](https://i.imgur.com/BKSDOSM.png "Main Window")


## [Available for Download Here](https://github.com/DavidStirling/QuantiFish/releases/)


##  What's New in 2.1?
  QuantiFish 2.1 introduces new measurements to analyse distribution of staining:
  - Fluor50 - Number of foci responsible for 50% of total staining. Provides insight into the distribution of staining between individual clusters.
  - Grid Analysis - Images are divided into zones of a defined size. Zones containing foci are counted as possible. Measures spatial distribution while minimising the influence of groups of foci in close proximity.
  - Polygon Area - Area of the smallest possible polygon which contains all foci. Informs on 2D spatial distribution.
  - ICDmax - Maximum inter-cluster distance, being the distance between the two furthest objects.
  
  **See below for more information!**
  
  See the [full changelog](https://github.com/DavidStirling/QuantiFish/blob/master/ChangeLog.txt) for more!
  
##  Referencing
 Citations can be made using the following DOI:
 
 [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1298429.svg)](https://doi.org/10.5281/zenodo.1298429)
 
 Full manuscript coming soon!


##  Compatibility
  This program is supported on **Windows 7** or newer and **Mac OS X 10.12 “Sierra”** or newer. For other operating systems you can run the script from the source code (freely available on GitHub). This software was written in Python 3. Key dependencies are the NumPy, SciPy, Scikit-Image and PIL libraries. Standalone Windows and Mac releases are bundled with all dependencies to simplify installation.


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

### Dissemination Analysis

**Analyse Clustering** - When enabled, the software will search for continuous areas of staining and perform additional analysis on these areas.

**Minimum Size** - Specifies the minimum area that a region of staining must be to be considered as a cluster.

**Calculate Fluor50** - When enabled, data for clusters will be sorted by size (largest to smallest). From this the number of clusters responsible for 50% of staining will be calculated. Cumulative results are also included in the cluster output if saving is enabled below.

**Spatial Analysis** - Turning this on will analyse for spatial distribution, performing grid analysis, polygon area and ICDmax measurments.

**Box Size** - Grid analysis divides the image up into boxes of the size specified here. At the default 50, each image will be split into 50x50 squares and squares containing a cluster will be counted as positive.

**Save Cluster Data** - When enabled, the intensity and size data for each individual cluster within an image will be recorded in a second output file, specified under this option.

####  Spatial Measures

**Stain Polygon Area** - Draws a polygon around all staining using the minimum possible vertices, like a rubber band. Good for evaluating how far staining has disseminated.

  ![Stain Polygon Area](https://i.imgur.com/OHOklDk.jpg "Stain Polygon Area")

**Cluster Polygon Area** - Similar to the stain polygon, but using the midpoints of clusters. Only clusters larger than the minimum size will be used. Useful when areas of staining are irregularly shaped or when the area of an individual object would be very large by itself.

  ![Cluster Polygon Area](https://i.imgur.com/wsKFX60.jpg "Cluster Polygon Area")

**ICDmax** - Distance between the two furthest clusters.

  ![ICDmax](https://i.imgur.com/W0rv23Y.jpg "ICDmax")

**Grid Analysis** - Image is divided into boxes (of the specified size) and boxes containing midpoints of clusters are considered positive. Useful for examining dissemination when objects may be packed closely together. 

  ![Grid Analysis](https://i.imgur.com/A6dIWRA.jpg "Grid Analysis")

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
Total Clusters | Areas of continuous fluorescence above the detection threshold. \[Analyse Clustering]
Peaks | Individual points of high fluorescence, usually indicating the midpoint of a fluorescent object. A single cluster can be made up of multiple peaks when objects are in close proximity. \[Analyse Clustering]
Large Clusters | Number of clusters bigger than the size threshold set by the user. Termed "large clusters". \[Analyse Clustering]
Peaks in Large Clusters | Number of peaks in clusters larger than the minimum size. \[Analyse Clustering]
Integrated Intensity in Large Clusters | Sum of all staining within large clusters. \[Analyse Clustering]
Positive Pixels in Large Clusters | Number of positive pixels within large clusters. \[Analyse Clustering]
Fluor50 | Minimum number of clusters responsible for 50% of all staining in large clusters. \[Calculate Fluor50]
Total Grid Boxes | Number of boxes an image was divided into during grid analysis. \[Spatial Analysis]
Positive Grid Boxes | Number of grid boxes which contained the midpoint of a cluster of staining. \[Spatial Analysis]
Cluster Polygon Area | The area of a polygon containing all cluster midpoints within the image using a minimum number of vertices. \[Spatial Analysis]
ICDmax | Maximum Inter-Cluster Distance. The distance between the two clusters which are furthest apart. \[Spatial Analysis]
Displayed Threshold | The threshold specified on the scale by the user.
Computed Threshold | The final value of the threshold after being adjusted for image bit depth. Pixels below this number were ignored. This is used to remove background.
Channel | The colour of the image being analysed.

  The results file should be locked for editing while the program is open, so please don’t try to modify it while the analysis is running. Multiple runs during the same session will be logged to the same file, although if you close the program and re-open it the program will clear pre-existing data should you try to select the same file.


#### Clusters File Contents

When using **Save Cluster Data** mode, the following data per cluster can be saved in clusters.csv (default name). If using a size threshold only data for clusters larger than or equal to that size will be recorded:

Column Name | Description \[Option]
------------ | -------------
File | The full path and name of the file containing the cluster.
Cluster ID | The number of the cluster in the image.
Cluster Location | Co-ordinates of the cluster's position in the image. In the format (Y, X)
Cluster Area | The number of pixels in the cluster.
Maximum Intensity | The highest value within the cluster.
Minimum Intensity | The lowest value within the cluster.
Average Intensity | The mean value within the cluster.
Integrated Intensity | The total intensity within the cluster.
Percent Intensity | The percent of all staining in the image contributed by the cluster. \[Calculate Fluor50]
Cumulative Intensity | Cumulative intensity of clusters in the image. \[Calculate Fluor50]
Cumulative Percent Intensity | Cumulative percentage of all staining in the image. \[Calculate Fluor50]

 - - - -


If you have any questions, problems or suggestions, contact the developer either here or on Twitter - [@DavidRStirling](https://www.twitter.com/DavidRStirling)
