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


    args = ["ffmpeg/ffmpeg", "-i", inputFileAbsDir, "-c:v", "libx265", "-crf", "28", "-c:a", "aac", "-b:a", "128k", "-preset", "medium", "-loglevel", "level+warning", "-y", exportDir if pathToTmp == False else tmpAbsDir]
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
        addProcessed(inputFileDir, relativePath, relMvOldPath, open(pathToProcessed, "a+"))
    else:
        addProcessed(inputFileDir, relativePath, open(pathToProcessed, "a+"))

    return True

def addProcessed(relInputPath, relOutputPath, relMvOldPath, processedFile):
    processedFile.seek(0, 2)
    if pathToMvOld != False and os.path.commonpath([pathToMvOld, pathToWatch]) == os.path.relpath(pathToWatch):
        print("Move old files path is a child of the watch folder. Adding moved file to processed to prevent loops.")
        processed.append(relMvOldPath)
        processedFile.write("\t" + relMvOldPath)
    addProcessed(relInputPath, relOutputPath, processedFile)
    return True

def addProcessed(relInputPath, relOutputPath, processedFile):
    processedFile.seek(0, 2)
    if os.path.commonpath([pathToExport, pathToWatch]) == os.path.relpath(pathToWatch):
        print("Export path is a child of the watch folder. Adding processed file to processed to prevent loops.")
        processed.append(relOutputPath)
        processedFile.write("\t" + relOutputPath)
    processedFile.write("\t" + relInputPath)
    processed.append(relInputPath)
    print("Processed " + relInputPath)
    processedFile.close()
    return True

def iterate():
    media = getMediaList(re.compile(r"\bmp4\b$"), before)
    for x in media:
        if not initFFMPEG(x): exit()
    if loop != False:
        time.sleep(loop * 60)
        iterate()
    exit()



autoYes = True if os.environ["autoYes"] == "True" else False
loop = int(os.environ["loop"]) if "loop" in os.environ.keys() and os.environ["loop"] != "False" else False
if "watch" in os.environ.keys():
    pathToWatch = os.environ["watch"]
else:
    print("Watch folder missing")
    exit()

pathToExport = os.environ["export"]
pathToProcessed = os.environ["processed"] if "processed" in os.environ.keys() else "/config/processed.tsv"
pathToMvOld = os.environ["mvold"] if "mvold" in os.environ.keys() and os.environ["mvold"] != "False" else False
pathToTmp = os.environ["tmp"] if "tmp" in os.environ.keys() and os.environ["tmp"] != "False" else False

if not os.path.exists(os.path.dirname(pathToProcessed)):
    os.makedirs(os.path.dirname(pathToProcessed))
processedFile = open(pathToProcessed, "a+")
processedFile.seek(0, 0)
processed = processedFile.read().split("\t")
processedFile.close()
iterate()
