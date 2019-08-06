import os, time, re, subprocess, getopt, sys
from copy import deepcopy


pathToWatch = "../media/Movies"
#pathToExport = pathToWatch
pathToExport = "../media/Movies"
#pathToExport = "../torrent/compressed/movies"
pathToMvOld = False
before = []

def getMediaList(regex, prevBefore):
    files = []
    foldersToSearch = [pathToWatch]
    while len(foldersToSearch) > 0:
        selected = foldersToSearch.pop();
        if os.path.isdir(selected):
            for x in os.listdir(selected):
                foldersToSearch.append(selected + "/" + x)
        else:
            files.append(selected)

    global before
    before = deepcopy(files)

    newFiles = deepcopy(files)
    for x in files:
        if re.search(regex, x) == None or x in prevBefore or x in processed:
            newFiles.remove(x)

    return newFiles

def initFFMPEG(inputFileDir):
    # Generate Input Path
    inputFileAbsDir = os.path.abspath(inputFileDir)

    # Generate Output Path
    relativeDir = os.path.dirname(inputFileDir)[len(pathToWatch):]
    root = os.path.splitext(os.path.basename(inputFileDir))[0]
    if pathToTmp != False:
        tmpAbsDir = os.path.abspath(pathToTmp + "/" + hex(int(time.time())).split("x")[1] + ".mkv")
    relativePath = pathToExport + relativeDir + "/" + root + ".mkv"
    exportDir = os.path.abspath(relativePath)


    args = ["ffmpeg/ffmpeg", "-i", inputFileAbsDir, "-c:v", "libx265", "-crf", "28", "-c:a", "aac", "-b:a", "128k", "-preset", "medium", "-y", exportDir if pathToTmp == False else tmpAbsDir]
    if pathToMvOld != False:
        relMvOldPath = pathToMvOld + relativeDir + "/" + os.path.basename(inputFileDir) if pathToMvOld != False else False
        print("Move old: " + os.path.abspath(relMvOldPath))

    print("Input: " + inputFileAbsDir)
    print("Output: " + exportDir)
    if autoYes != True and input("Start? (y/n) ") != "y":
        return False

    if not os.path.exists(os.path.dirname(pathToExport + relativeDir)):
        os.makedirs(os.path.dirname(pathToExport + relativeDir))

    subprocess.Popen(args).wait()

    if pathToTmp != False:
        if not os.path.exists(os.path.dirname(exportDir)):
            os.makedirs(os.path.dirname(exportDir))
        os.rename(tmpAbsDir, exportDir)

    if pathToMvOld != False:
        if not os.path.exists(os.path.dirname(relMvOldPath)):
            os.makedirs(os.path.dirname(relMvOldPath))
        os.rename(inputFileDir, relMvOldPath)
        addProcessed(inputFileDir, relativePath, relMvOldPath)
    else:
        addProcessed(inputFileDir, relativePath)

    return True

def addProcessed(relInputPath, relOutputPath, relMvOldPath):
    if pathToMvOld != False and os.path.commonpath([pathToMvOld, pathToWatch]) == os.path.relpath(pathToWatch):
        print("Move old files path is a child of the watch folder. Adding moved file to processed to prevent loops.")
        processed.append(relMvOldPath)
        processedFile.write("\t" + relMvOldPath)
    addProcessed(relInputPath, relOutputPath)
    return True

def addProcessed(relInputPath, relOutputPath):
    processedFile.seek(0, 2)
    if os.path.commonpath([pathToExport, pathToWatch]) == os.path.relpath(pathToWatch):
        print("Export path is a child of the watch folder. Adding processed file to processed to prevent loops.")
        processed.append(relOutputPath)
        processedFile.write("\t" + relOutputPath)
    processedFile.write("\t" + relInputPath)
    processed.append(relInputPath)
    print("Processed " + relInputPath)
    return True

def iterate():
    media = getMediaList(re.compile(r"\bmp4\b$"), before)
    for x in media:
        if not initFFMPEG(x): exit()
    time.sleep(1 * 60)
    if loop:
        iterate()
    exitEvent()

def exitEvent():
    processedFile.close()
    exit()

processedFile = open("processed.tsv", "a+")
processedFile.seek(0, 0)
processed = processedFile.read().split("\t")

options, args = getopt.getopt(sys.argv[1:], "hy", ["watch=", "export=", "mvold="])

autoYes = False
for o, v in options:
    if o == "-h":
        helpFile = open("help.txt", "r")
        print(helpFile.read())
        helpFile.close()
        exit()
    elif o == "-y":
        autoYes = True
    elif o == "--watch":
        pathToWatch = v
    elif o == "--export":
        pathToExport = v
    elif o == "--mvold":
        pathToMvOld = v if v != "False" else False

autoYes = True if os.environ["autoYes"] == "True" else False
loop = True if "loop" in os.environ.keys() and os.environ["loop"] == "True" else False
if "watch" in os.environ.keys():
    pathToWatch = os.environ["watch"]
else:
    print("Watch folder missing")
    exit()

pathToExport = os.environ["export"]
pathToMvOld = os.environ["mvold"] if "mvold" in os.environ.keys() and os.environ["mvold"] != "False" else False
pathToTmp = os.environ["tmp"] if "tmp" in os.environ.keys() and os.environ["tmp"] != "False" else False
iterate()
