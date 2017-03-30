# QuantiFish

  QuantiFish is a quantification program intended for measuring fluorescence in images of zebrafish, although use with images of other specimens is possible. To perform an analysis, specify the folder containing your images of interest, select which analysis settings you want, then choose a file to save the data to. When these parameters are set the “Run” button in the bottom right will become available to allow you to start the analysis.
  
  ![Main Window](http://i.imgur.com/AUTJ2Ag.png "Main Window")
  

## Input
  The program reads **.tif** files which can be exported from most microscopes. Images can either be in greyscale (**RAW mode**, one image per channel) or overlays (**RGB mode**, multiple channels in different colours or one image per channel). Due to the way that image colour data is stored the program can only separate **R**ed, **G**reen and **B**lue, so please don’t overlay in other colours as this will interfere with the analysis. This also means that overlaying a brightfield image in grey would prevent accurate analysis.
  
  This version of the software currently supports **one fish per image**.

  Use the “Select directory” button to choose the folder containing your images. QuantiFish will scan that folder, along with any subfolders if you have the “Include Subdirectories” option selected.

  The analyser will ignore files which aren’t images, so there’s no need to organise the input folders. If your microscope supplies metadata this can also be used to selectively analyse the right images for your channel of interest (Leica hardware only for now).

## Output
  Results will be recorded in a **.csv** file chosen by the user, which can be opened in most spreadsheet programs (e.g. Microsoft Excel). Results are exported with each row representing one image, with the following recorded for each:
  
1.	File – the name and directory of the image being analysed
2.	Integrated Intensity – The average brightness of your staining multiplied by the stained area. This is your overall measure of fluorescence.
3.	Positive Pixels – The total number of pixels which were considered positive (above the threshold). This represents the stained area.
4.	Minimum – The lowest value among the positive pixels.
5.	Maximum – The highest value among the positive pixels.
6.	Threshold – The threshold used for the analysis. Pixels below this number are ignored. This is used to remove background.
7.	Channel – The colour of the image being analysed, if using the “Detect channels” feature.

  The results file should be locked for editing while the program is open, so please don’t try to modify it while the analysis is running. Multiple runs during the same session will be logged to the same file, although if you close the program and re-open it the program will clear pre-existing data should you try to select the same file.

## Settings
  **Image Type** – This determines the type of input images you’d like the program to analyse.  When viewing your images in other software they’ll either appear as greyscale or colour images depending on the settings you used to export them. Colour images may be a single channel or an overlay of multiple channel.

  The **“Detect Channels”** option can be used when your images were exported as separate files for each channel (colour). This will tell the program to search the images folder for metadata files which are typically exported by Leica microscopes. If found, these are then used to determine which images represent which channels and the script will try to only analyse the images from the correct channel. This avoids analysing images of the wrong colour, but if detection fails the program will fall back and analyse all the images in the directory. 

In the current version, this is limited to metadata from Leica systems. When exporting your images there’s no need to do anything extra, just don’t delete the metadata folder from the directory you’re looking to analyse. Channel detection is based on the colour you’ve set your system to display a channel as, so if you’ve told it to show GFP in red, GFP will be the “Red” channel. The software also assumes that you used the same microscope/channel settings for all your images, so you may want to turn channel detection off if you changed filters midway through the experiment.

**Thresholding** – This feature allows you to set a minimum brightness required for a pixel to be classed as positive. The scale represents the possible range of brightness values across your images. Ideally you should set this so that your negative controls are entirely below the threshold. This feature effectively removes background noise and autofluorescence, but can be disabled if the need arises. Use the **Preview** feature to test what the current settings will detect.

**Quantifying** – This allows you to select which colour you’re looking to analyse. When multiple channels are present the software will pull out the correct colour and quantify signal on that channel. If “Detect Channels” mode is off while using Greyscale mode, this setting becomes irrelevant as the script will analyse all images regardless of channel.

## Previewing

  ![Previewer Window](http://i.imgur.com/02or9R3.png "Previewer Window")

**Preview** – The preview function will ask you to choose an example image and will generate an overlay of which pixels would be detected by the script using the current settings. Positive pixels are coloured light blue for visibility and ideally should only be present in the areas you’d consider as stained. The preview will update as you change the threshold, but if you want to switch channels hit the “**Refresh**” button to update the analysis. The overlay can be toggled on and off to aid thresholding.

The **Auto Threshold** button will try to pick a threshold based on the highest value in the current preview image (ideally a negative control). This is useful for getting an estimate to start from, although there will be some variance between different images. This function will also not work properly if your microscope has damaged pixels which always read positive, which can happen as sensors age. A small number of stuck pixels should be consistent across all images and wouldn’t significantly impact results beyond a minor increase in background.

If you’ve selected a working directory, the program will automatically open images from there for previewing. You can cycle between images in the target folder using the **Next/Previous** buttons, or you can manually select a preview image with the **Change** button – this can be from anywhere on your computer. You can also **save** a copy of the preview image overlay to aid presentation.

### Colour or Greyscale?
It is better to import “RAW” data if possible, which will give you greyscale files. This provides a bigger range of possible brightness values for your image which will improve the resolution of your analysis. Readings from RAW data will generally be higher than from RGB images due to this different scale, so they’re not directly comparable. Some microscopes will only export RAW data in proprietary formats, and so this program has been designed to accommodate both RAW and RGB exports to ensure compatibility.

You may notice that switching between colour and greyscale mode also changes the “threshold” scale. This is because the different image types do not have the same **bit depth**. RGB images typically have 8 bits per channel, making a total of 256 possible brightness values in each colour. Greyscale images can be up to 16-bit if using RAW export settings, with 65,536 possible values. To make matters more complicated most microscope sensors capture in 12-bit (4,096 values) which is then either stretched or compressed onto an 8- or 16-bit scale. Therefore, saving in 8-bit results in some loss of precision.

If you have any questions, problems or suggestions, contact the developer either here or on Twitter - [@DavidRStirling](https://www.twitter.com/DavidRStirling)
