# paper-backup
The purpose of this script is to save data (and even data structures) to paper and restore them.
There exist other projects similar to this, however i could not find one tailored to my needs - hence this repository.

I created this script with the following goals in mind:
- It should be cross-platform
- It should support binary data and be able to restore entire folder structures
- It should use a "common" way of storing data to paper, as this enables usage of other means to decode the data
- Manual fixing of corrupted data should be possible
- It should write to pdf, such that printing is not (so much) dependent on the image viewer

Thus I decided to encode the data as QR-Codes.
## How to use
I use Python 3.8.6 to execute the script (and haven't tested any other versions). It is used as a command line tool with the following most common use cases:
```
py paper-backup.py --backup -i <INPUTFOLDER> -o <OUTPUTPDF>
```
makes a backup of all **contents and structure** of the ```<INPUTFOLDER>``` as QR-Codes and writes them to the pdf-file ```<OUTPUTPDF>``` (the suffix .pdf is appended automatically if not supplied). 

In addition to this, one can set the size in ```mm``` of the images in the pdf-file via ```-q```. The default is ```-q 80```.

For debugging purposes, the flag ```-b``` saves all generated QR-Codes in bitmap format to the current working directory and the flag ```-p``` saves all chunks in .chunk files into the current working directory. The flag ```-b``` is not affected by ```-q```.
```
py paper-backup.py --restore -i <INPUTFOLDER> -o <OUTPUTFOLDER>
```
recursively scans all images within ```<INPUTFOLDER>``` (this means that all subfolders are also scanned!) for QR-Codes and restores the data into ```<OUTPUTFOLDER>```. Furthermore, it supports reading data from *.chunk files, which one can use to insert chunks that had to be restored manually. To do this, just copy the restored data into a .txt file with arbitrary name and change the suffix from .txt to .chunk, then put this file somewhere into ```<INPUTFOLDER>```. Be careful not to add anything to the data (e.g. newlines).

## How does it work
### Backup
1. Add all files/folders within ```<INPUTFOLDER>``` to a tarball in memory
2. Compress the bytes with gzip
3. Encode bytes with base85 (we do this because QR-Code readers have very poor compatibility with binary data) and save in UTF-8
4. Next we split this string among QR-Codes in the following fashion: Say from the last step we obtained abcdefghIJKLMNOPQRStuVwXYZ and lets assume we can always save exactly 10 characters in one QR-Code. Then the data in the QR-Codes would be
  - 0>abcdefgh
  - 1>IJKLMNOP
  - 2>QRStuVwX
  - 3<YZ

   Thus, for any chunk that is not the last one we have ```chunkIndex>asMuchPayloadAsPossible``` and for the last one ```chunkIndex<asMuchPayloadAsPossible```.

5. Lastly, put all the QR-Codes on the pdf-File.
### Restore
1. Read chunk data from images with QR-Codes and .chunk files
2. Order the chunk data using the chunk indicies
2. Perform sanity checks on the chunk data, e.g. check for duplicate or missing chunks 
3. Append the chunk data
4. Decode into bytes from base85
5. Decompress bytes with gzip
6. Extract the resulting tarball into ```<OUTPUTFOLDER>```
