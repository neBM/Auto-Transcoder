import os, time, re, subprocess, sys
from copy import deepcopy

pathToWatch = "../media/Movies"
#pathToExport = pathToWatch
pathToExport = "../media/Movies"
#pathToExport = "../torrent/compressed/movies"
pathToMvOld = False
before = []
appNonce = hex(int(time.time())).split("x")[1]
nextTranscodeId = 0
compressionsToComplete = []
compressions = []

class transcoderController():
    process = None
    properties = {}
    def start(self):
        print(" ".join(self.properties["args"]))
        process = subprocess.Popen(self.properties["args"])
        return True

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
    pathName = os.path.splitext(os.path.basename(inputFileDir))
    if pathToTmp != False:
        if not os.path.exists(pathToTmp):
            os.makedirs(pathToTmp)
        tmpAbsDir = os.path.abspath(pathToTmp + "/" + appNonce + "_" + hex(nextTranscodeId).split("x")[1] + ".mkv")
    else:
        tmpAbsDir = False
    relativePath = pathToExport + relativeDir + "/" + pathName[0] + ".mkv"
    exportDir = os.path.abspath(relativePath)

    args = ["ffmpeg/ffmpeg", "-i", inputFileAbsDir, "-c:v", "libx265", "-crf", "28", "-c:a", "aac", "-b:a", "320k", "-ac", "2", "-preset", "medium", "-y"]

    switcher = {
        0: "quiet",
        1: "error",
        2: "warning",
        3: "info",
        4: "verbose"
    }

    args.extend(["-loglevel", "level+" + switcher[level]])
     
    if resCap != False:
        args.extend(["-vf", "scale=-1:'min(" + resCap + ",ih)'"])

    args.append(exportDir if pathToTmp == False else tmpAbsDir)

    if pathToMvOld != False:
        relMvOldPath = pathToMvOld + relativeDir + "/" + os.path.basename(inputFileDir)
        if level >= 4: print("Move old: " + os.path.abspath(relMvOldPath))
    else:
        relMvOldPath = False

    if level >= 4: print("Input: " + inputFileAbsDir)
    if level >= 4: print("Output: " + exportDir)
    if autoYes != True and input("Start? (y/n) ") != "y":
        exit()

    if not os.path.exists(os.path.dirname(pathToExport + relativeDir)):
        os.makedirs(os.path.dirname(pathToExport + relativeDir))

    if "runRules" not in os.environ or os.environ["runRules"] == "True":
        inputFileInfo = bytes(subprocess.check_output(["ffmpeg/ffprobe", "-of", "csv", "-v", "error", "-show_streams", inputFileAbsDir])).decode(sys.stdout.encoding)

        streams = [stream.split(",") for stream in inputFileInfo.split("\n")]
        streams.remove([""])

        videoStreams = []
        audioStreams = []
        otherStreams = []
        for stream in streams:
            if stream[0] != "stream":
                continue
            if stream[5] == "video":
                videoStreams.append(stream)
            elif stream[5] == "audio":
                audioStreams.append(stream)
            else:
                otherStreams.append(stream)

        needsCompression = False
        for stream in videoStreams:
            if stream[2] != "hevc" or stream[10] > resCap:
                needsCompression = True
                break
    else:
        needsCompression = True

    properties = {
        "args": args,
        "postProcessProperties": {
            "inputFileDir": inputFileDir,
            "relMvOldPath": relMvOldPath,
            "inputFileAbsDir": inputFileAbsDir,
            "relativeDir": relativeDir,
            "relativePath": relativePath,
            "pathName": pathName,
            "exportDir": exportDir,
            "tmpAbsDir": tmpAbsDir,
            "pathName": pathName,
            "neededCompression": needsCompression
        }
    }

    if needsCompression == True:
        return properties
    else:
        processOutput(properties["postProcessProperties"])

    return True

def processOutput(postProcessProperties):
    if pathToMvOld != False:
        if not os.path.exists(os.path.dirname(postProcessProperties["relMvOldPath"])):
            os.makedirs(os.path.dirname(postProcessProperties["relMvOldPath"]))
        os.rename(postProcessProperties["inputFileDir"], postProcessProperties["relMvOldPath"])

    if postProcessProperties["neededCompression"] == False:
        if level >= 2: print("Compression not needed for " + postProcessProperties["inputFileAbsDir"])
        postProcessProperties["relativePath"] = pathToExport + postProcessProperties["relativeDir"] + "/" + postProcessProperties["pathName"][0] + postProcessProperties["pathName"][1]
        if not os.path.exists(os.path.dirname(postProcessProperties["relativePath"])):
            os.makedirs(os.path.dirname(postProcessProperties["relativePath"]))
        os.link(postProcessProperties["relativePath"] if pathToMvOld == False else postProcessProperties["relMvOldPath"], postProcessProperties["inputFileDir"])
    elif pathToTmp != False:
        if not os.path.exists(os.path.dirname(postProcessProperties["exportDir"])):
            os.makedirs(os.path.dirname(postProcessProperties["exportDir"]))
        os.rename(postProcessProperties["tmpAbsDir"], postProcessProperties["exportDir"])

    if pathToMvOld != False:
        addProcessed(postProcessProperties["inputFileDir"], postProcessProperties["relativePath"], postProcessProperties["relMvOldPath"])
    else:
        addProcessed(postProcessProperties["inputFileDir"], postProcessProperties["relativePath"])

def addProcessed(relInputPath, relOutputPath, relMvOldPath=None):
    if relMvOldPath != None and pathToMvOld != False and os.path.commonpath([pathToMvOld, pathToWatch]) == os.path.relpath(pathToWatch):
        if level >= 2: print("Move old files path is a child of the watch folder. Adding moved file to processed to prevent loops.")
        addToProcessedFile(relMvOldPath)
    if os.path.commonpath([pathToExport, pathToWatch]) == os.path.relpath(pathToWatch):
        if level >= 2: print("Export path is a child of the watch folder. Adding processed file to processed to prevent loops.")
        addToProcessedFile(relOutputPath)
    addToProcessedFile(relInputPath)
    if level >= 3: print("Processed " + relInputPath)
    processedFile.close()
    return True

def addToProcessedFile(fileDir):
    if os.environ["processed"] != "False":
        processedFile = open(pathToProcessed, "a+")
        processedFile.seek(0, 2)
        processedFile.write("\t" + fileDir)
    processed.append(processedFile)

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
level = os.environ["level"] if "level" in os.environ.keys() else "warning"
concurrentCompressionsTarget = 3

class levels:
    disabled = 0
    error = 1
    warning = 2
    info = 3
    verbose = 4

level = getattr(levels, level)

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

while True:
    media = getMediaList(re.compile(r"(.webm|.mkv|.flv|.flv|.vob|.ogv|.ogg|.drc|.gif|.gifv|.mng|.avi|.MTS|.M2TS|.TS|.mov|.qt|.wmv|.yuv|.rm|.rmvb|.asf|.amv|.mp4|.m4p|.m4v|.mpg|.mp2|.mpeg|.mpe|.mpv|.mpg|.mpeg|.m2v|.m4v|.svi|.3gp|.3g2|.mxf|.roq|.nsv|.flv|.f4v|.f4p|.f4a|.f4b)$", flags=re.IGNORECASE), before)
    for x in media:
        try:
            properties = initFFMPEG(x)
            nextTranscodeId += 1
            if properties != False:
                compressionsToComplete.append(properties)
        except subprocess.CalledProcessError:
            if level >= 1: print("Transcoder Error! Failed to process: " + x)
            os.remove(x)
    while len(compressionsToComplete) > 0:
        for compression in compressions:
            if compression.process != None and compression.process.poll() == 0:
                compressions.remove(compression)
                processOutput(compression.properties["postProcessProperties"])
        while len(compressions) < concurrentCompressionsTarget and len(compressionsToComplete) > 0:
            newTranscoderController = transcoderController()
            newTranscoderController.properties = compressionsToComplete.pop(0)
            newTranscoderController.start()
            compressions.append(newTranscoderController)
        time.sleep(10)
    if loop == False:
        exit()
    time.sleep(loop * 60)