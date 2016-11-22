# ffslicer.py

FFMPEG wrapper for slicing videos.
Requires python 3.4 or above.

For help in terminal type:

>pyton3 ./ffslicer.py -h

Example:

>python3 ./ffslicer.py -i input.mp4 @args.txt ~/destdir/output.mkv

Takes arguments for args.txt file.  
Will create a contaner folder named "ffslices_input.mp4" at "~/destdir/"(must already exist).  
Input filename appended to the ffslices container folder name.  
~/destdir/ffslices\_input.mp4 will contain a video file for each slice in arguments.

Each option in the arguments file (named args.txt in this case) must on a separate line:

*-i  
../test.mp4  
--slices  
00:00:03.325 8.305  
8.317 15.34 28 35.8  
-preset  
superfast  
-qp  
4  
-pix_fmt  
yuv420p*  

Only **--slices** option can have arguments spread on several lines.
All options can reside in an arguments file, so a call could look like:
>python3 ./ffslicer.py @args.txt

To parallelize slicing there's **--multiprocess** option.
