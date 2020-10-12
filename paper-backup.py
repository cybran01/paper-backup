from argparse import ArgumentParser
from io import BytesIO
from logging import error
from pyx.canvas import canvas
from pyx.document import document,page,paperformat
from pyx.bitmap import bitmap

from pyzbar.pyzbar import decode as _QRdecode
from pyzbar.wrapper import ZBarSymbol
from qrcode import make as QRencode
from qrcode import QRCode, exceptions

from base64 import b85encode, b85decode
from PIL import Image,UnidentifiedImageError
from gzip import compress,decompress
from pathlib import Path
import os 
import tarfile

#Determine max. bytes to fit in qrcode
def maxSplit(data: str):
    def dataFits(_data: str):
        qr = QRCode()
        qr.add_data(_data)
        try:
            qr.best_fit()
            return True
        except exceptions.DataOverflowError:
            return False

    if dataFits(data):
        return [data, None]

    iteration = [0,len(data)]
    while iteration[1]-iteration[0] > 1:
        if dataFits(data[: int((iteration[1]+iteration[0])/2)]):
            iteration[0] = int((iteration[1]+iteration[0])/2)
        else:
            iteration[1] = int((iteration[1]+iteration[0])/2)

    return data[:iteration[0]], data[iteration[0]:]

def getChunkData(data: str):
    def findHeaderEnd(_data: str):
        try:
            regularChunkData = _data.index(">")
        except ValueError:
            return True,_data.index("<")
        try:
            endChunkData = _data.index("<")
        except ValueError:
            return False,regularChunkData

        return (endChunkData < regularChunkData), min(regularChunkData,endChunkData)
        
    isEndChunk, headerEndIndex = findHeaderEnd(data)
    chunkIndex = int(data[:headerEndIndex])
    chunkData = data[headerEndIndex+1:]

    return isEndChunk, chunkIndex, chunkData

def pdfImagePlacement(counter: int):
    #All units in centimeters
    qrSize = args.qrSize/10.0
    A4Width = 21.0
    A4Height = 29.7
    horizontalPadding = (A4Width-2*qrSize)/5.0
    horizontalMargin = 2*horizontalPadding
    verticalPadding = (A4Height-3*qrSize)/6.0
    verticalMargin = 2*verticalPadding

    return dict(xpos = horizontalMargin + (counter%2)*(horizontalPadding+qrSize),
        ypos = A4Height-(verticalMargin+qrSize + (int(counter/2)%3)*(verticalPadding+qrSize)),
        width = qrSize)

def QRdecode(file: str):
    decodedChunkBuffer = []

    for Decoded in _QRdecode(Image.open(file), symbols=[ZBarSymbol.QRCODE]):
        decodedChunkBuffer.append(Decoded.data)
    
    return decodedChunkBuffer

def backup():
    inFolder = Path(args.input)

    memTar = BytesIO()
    tar = tarfile.open(fileobj = memTar, mode = "x")
    for itm in inFolder.iterdir():
        tar.add(itm.resolve(), arcname=itm.relative_to(inFolder))

    tar.close()

    content = memTar.getvalue()
    memTar.close()

    content = compress(content)
    b85Content = b85encode(content).decode("UTF-8")

    pdf = document()
    pdfPage = None

    counter = 0
    while b85Content:
        b85Content =  str(counter) + ">" + b85Content
        chunk, b85Content = maxSplit(b85Content)
        if b85Content is None:
            chunk = chunk[:chunk.index(">")] + "<" + chunk[chunk.index(">")+1:] #Signal last chunk

        print("Generating QRCode for chunk " + str(counter))
        qrCode = QRencode(chunk)

        #Used for debugging
        if args.plainChunk:
            f = open("chunk" + str(counter) + ".chunk","w")
            f.write(chunk)
            f.close

        if counter%6 == 0:
            pdfPage = page(canvas(), paperformat = paperformat.A4,centered=0)
            pdf.append(pdfPage)

        pdfPage.canvas.insert(bitmap(**pdfImagePlacement(counter), image = qrCode.convert("LA")))

        if args.makeBmp:
            qrCode.save("chunk" + str(counter) + ".bmp")

        counter += 1

    print("Writing to pdf...")
    outFile = Path(args.output)
    if(outFile.suffix == ".pdf"):
        pdf.writePDFfile(args.output)
    else: 
        pdf.writePDFfile(args.output + ".pdf")

    print("Done")
    
def restore():
    b85ContentRestored = ""
    b85ChunkBuffer = []
    endChunkIndex = -1
    
    allImgs = []
    for root, _, files in os.walk(args.input):
	    for name in files:
                curFile = os.path.join(root, name)
                try:
                    Image.open(curFile)
                    allImgs.append(curFile)
                except UnidentifiedImageError:
                    curFileSuffix = Path(curFile).suffix
                    if curFileSuffix == ".chunk":
                        f = open(curFile, "r")
                        isEndChunk, chunkIndex, b85ChunkData = getChunkData(f.read())
                        f.close()
                        print("Found a chunk file containing chunk " + str(chunkIndex) + ", extracting...")
                        b85ChunkBuffer.append((chunkIndex,b85ChunkData))
                        if isEndChunk:
                            endChunkIndex = chunkIndex

    for nr,file in enumerate(allImgs):
        print("Decoding " + str(nr+1) + " of " + str(len(allImgs)) + " images...")
        for decodedQRChunk in QRdecode(file):
            decodedQRChunk = decodedQRChunk.decode("UTF-8")
            isEndChunk, chunkIndex, b85ChunkData = getChunkData(decodedQRChunk)
            b85ChunkBuffer.append((chunkIndex,b85ChunkData))
            if isEndChunk:
                endChunkIndex = chunkIndex

    #Check if an endchunk was found
    if endChunkIndex == -1:
        error("The end chunk is missing. Shutting down")
        exit()
    else:
        print("Found a total of " + str(endChunkIndex+1) + " chunks")

    b85ChunkBuffer.sort(key = lambda x: x[0])
    
    #Check if b85ChunkBuffer makes sense
    lastIndex = -1
    lastChunkData = None
    for index, b85ChunkData in b85ChunkBuffer:
        if (index > lastIndex + 1):
            error("Chunk " + str(lastIndex + 1) + " is missing. Shutting down")
            exit()
        if (index == lastIndex):
            if(lastChunkData == b85ChunkData):
                print("Chunk " + str(index) + " has a duplicate with identical payload")
                continue
            else:
                print("Chunk " + str(index) + " has a duplicate with different payload. Shutting down")
                exit()
        lastIndex = index
        lastChunkData = b85ChunkData
        b85ContentRestored += b85ChunkData

    restored = b85decode(b85ContentRestored)
    restored = decompress(restored)

    memTar = BytesIO(restored)
    tar = tarfile.open(fileobj = memTar, mode="r")
    tar.extractall(args.output)
    tar.close()
    memTar.close()

    print("Done")

def main():
    if (args.mode == "backup"):
        backup()
    elif (args.mode == "restore"):
        restore()
    

if __name__ == "__main__":
    parser = ArgumentParser()
    modeGroup = parser.add_mutually_exclusive_group()
    modeGroup.required = True
    modeGroup.add_argument("--backup", action="store_const", dest="mode", const="backup")
    modeGroup.add_argument("--restore", action="store_const", dest="mode", const="restore")

    parser.add_argument("-i", dest="input", required=True)
    parser.add_argument("-o", dest="output", required=True)
    parser.add_argument("-q", dest="qrSize", type=int)
    parser.add_argument("-b", action="store_const", dest="makeBmp", const=True)
    parser.add_argument("-p", action="store_const", dest="plainChunk", const=True)

    args = parser.parse_args()

    if args.qrSize is not None and args.mode == "restore":
        parser.error("Argument -q in restore mode given, will be ignored")
    
    if args.makeBmp is not None and args.mode == "restore":
        parser.error("Argument -b in restore mode given, will be ignored")
    
    if args.plainChunk is not None and args.mode == "restore":
        parser.error("Argument -p in restore mode given, will be ignored")

    if not args.qrSize:
        args.qrSize = 80
    
    if not args.makeBmp:
        args.makeBmp = False

    if not args.plainChunk:
        args.plainChunk = False

    main()
