from argparse import ArgumentParser

from pyzbar.pyzbar import decode as _QRdecode
from pyzbar.wrapper import ZBarSymbol
from qrcode import make as QRencode

from base64 import b64encode,b64decode
from PIL import Image
from gzip import compress,decompress

def QRdecode(file: str):
    decodedChunkBuffer = []

    for Decoded in _QRdecode(Image.open(file), symbols=[ZBarSymbol.QRCODE]):
        decodedChunkBuffer.append(Decoded.data)
    
    return decodedChunkBuffer

def main():
    chunksize = args.chunksize

    f = open(args.infilename,"rb")
    content = f.read()
    f.close()

    content = compress(content)
    b64Content = b64encode(content)

    b64contentSplit = [b64Content[i:i+chunksize] for i in range(0,len(b64Content),chunksize)]

    #TODO instead use pillow to create PDF
    for nr,chunk in enumerate(b64contentSplit):
        QRencode(str(nr) + "/" + str(len(b64contentSplit)) + ">" + chunk.decode("UTF-8")).save(str(nr) + ".bmp")

    b64contentRestored = ""
    b64chunkBuffer = []
    totalChunks = 0

    for nr in range(len(b64contentSplit)):
        print("Decoding " + str(nr) + " of " + str(len(b64contentSplit)-1) + "...")
        for decodedQRChunk in QRdecode(str(nr) + ".bmp"):
            decodedQRChunk = decodedQRChunk.decode("UTF-8")        
            chunkIndex = int(decodedQRChunk[:decodedQRChunk.index("/")])
            totalChunks = int(decodedQRChunk[decodedQRChunk.index("/")+1:decodedQRChunk.index(">")])
            b64chunkData = decodedQRChunk[decodedQRChunk.index(">")+1:]
            b64chunkBuffer.append((chunkIndex,b64chunkData))
    #TODO: check if enough codes were scanned, etc.

    b64chunkBuffer.sort(key = lambda x: x[0])

    for _, b64chunkData in b64chunkBuffer:
        b64contentRestored += b64chunkData

    restored = b64decode(b64contentRestored)
    restored = decompress(restored)

    g = open(args.outfilename,"wb")
    g.write(restored)
    g.close() 

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-i", "--infile", dest="infilename") #TODO allow user to give a list of files
    parser.add_argument("-o", "--outfile", dest="outfilename")
    parser.add_argument("-c", "--chunksize", dest="chunksize", type=int, default=2048)
    args = parser.parse_args()

    if not args.infilename:
        parser.error("Error, no input file given. Use -i to specify input file.")
        exit()
    if not args.outfilename:
        parser.error("Error, no output file given. Use -o to specify output file.")
        exit()

    main()
