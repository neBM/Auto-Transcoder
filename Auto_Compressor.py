import os, time, re, subprocess
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


    args = ["ffmpeg/ffmpeg", "-i", inputFileAbsDir, "-c:v", "libx265", "-crf", "28", "-c:a", "aac", "-b:a", "128k", "-preset", "medium", "-vf", "scale=-1:'min(" + resCap + ",ih)'", "-loglevel", "level+warning", "-y", exportDir if pathToTmp == False else tmpAbsDir]
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
        addToProcessedFile(relMvOldPath)
    addProcessed(relInputPath, relOutputPath)
    return True

def addProcessed(relInputPath, relOutputPath):
    if os.path.commonpath([pathToExport, pathToWatch]) == os.path.relpath(pathToWatch):
        print("Export path is a child of the watch folder. Adding processed file to processed to prevent loops.")
        addToProcessedFile(relOutputPath)
    addToProcessedFile(relInputPath)
    print("Processed " + relInputPath)
    processedFile.close()
    return True

def addToProcessedFile(fileDir):
    if os.environ["processed"] != "False":
        processedFile = open(pathToProcessed, "a+")
        processedFile.seek(0, 2)
        processedFile.write("\t" + fileDir)
    processed.append(processedFile)


def iterate():
    while True:
        media = getMediaList(re.compile(r"(.webm|.mkv|.flv|.flv|.vob|.ogv|.ogg|.drc|.gif|.gifv|.mng|.avi|.MTS|.M2TS|.TS|.mov|.qt|.wmv|.yuv|.rm|.rmvb|.asf|.amv|.mp4|.m4p|.m4v|.mpg|.mp2|.mpeg|.mpe|.mpv|.mpg|.mpeg|.m2v|.m4v|.svi|.3gp|.3g2|.mxf|.roq|.nsv|.flv|.f4v|.f4p|.f4a|.f4b)$", flags=re.IGNORECASE), before)
        for x in media:
            if not initFFMPEG(x): exit()
        if loop == False:
            exit()
        time.sleep(loop * 60)

autoYes = os.environ["autoYes"] == "True"
loop = int(os.environ["loop"]) if "loop" in os.environ.keys() and os.environ["loop"] != "False" else False
if "watch" in os.environ.keys():
    pathToWatch = os.environ["watch"]
else:
    print("Watch folder missing")
    exit()

pathToExport = os.environ["export"]
pathToMvOld = os.environ["mvold"] if "mvold" in os.environ.keys() and os.environ["mvold"] != "False" else False
pathToTmp = os.environ["tmp"] if "tmp" in os.environ.keys() and os.environ["tmp"] != "False" else False

resCap = os.environ["rescap"] if "rescap" in os.environ.keys() and os.environ["rescap"] != "False" else False

print(os.environ["processed"])
if "processed" in os.environ.keys() and os.environ["processed"] != "False":
    pathToProcessed = os.environ["processed"] if "processed" in os.environ.keys() else "/config/processed.tsv"
    if not os.path.exists(os.path.dirname(pathToProcessed)):
        os.makedirs(os.path.dirname(pathToProcessed))
    processedFile = open(pathToProcessed, "a+")
    processedFile.seek(0, 0)
    processed = processedFile.read().split("\t")
    processedFile.close()
else:
    os.environ["processed"] = "False"
    processed = []

iterate()