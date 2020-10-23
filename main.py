import http.server, urllib.parse, logging, threading, json, os, traceback, subprocess, tempfile, abc, sqlite3, shutil, re, email.utils, email.message, smtplib, time, http
from enum import Enum

def _conn():
    return sqlite3.connect("./sqlite.dev.db")

class Consumer:
    queue = []
    c = threading.Condition()

    class State(Enum):
        WAITING = 0
        RUNNING = 1

    def __init__(self):
        self.latestJob = self.state = self.totalWu = None

    @property
    def wu(self):
        return None

    @classmethod
    def extend(cls, files):
        cls.queue.extend(files)
        with cls.c:
            cls.c.notify(len(files))
        logging.info("Added {!s} items to {}'s queue".format(len(files), cls))

    @classmethod
    def pop(cls):
        try:
            return cls.queue.pop(0)
        except IndexError as e:
            return None

    @staticmethod
    def doWork(path): ...

    def run(self):
        logging.info("{} started.".format(threading.currentThread().name))
        while True:
            self.state = self.State.WAITING
            while True:
                data = self.pop()
                if data == None:
                    with self.c:
                        self.c.wait()
                else:
                    break
            self.latestJob = data
            self.state = self.State.RUNNING
            logging.debug("{} started work on {}".format(threading.currentThread().name, data))
            try:
                self.doWork(data)
                # time.sleep(20)
            except Exception as e:
                tb = traceback.format_exc()
                logging.error("Failed: " + data)
                msg = email.message.EmailMessage()
                msg.set_content("Data: {}\n\n{}".format(data, tb))
                msg["Subject"] = "An error has occured!"
                msg["From"] = "services@martinilink.co.uk"
                msg["Date"] = email.utils.formatdate()
                with smtplib.SMTP_SSL("mail.martinilink.co.uk") as smtp:
                    smtp.login("services@martinilink.co.uk", "1nfinate-Space")
                    smtp.send_message(msg, to_addrs=["ben@martinilink.co.uk"])


class TranscoderWorker(Consumer):
    def doWork(self, job):
        path = job
        conn = _conn()
        c = conn.cursor()

        p = subprocess.Popen(["ffprobe", "-loglevel", "quiet", "-print_format", "json", "-show_format", path], stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        data = json.loads(stdout)
        self.totalWu = float(data["format"]["duration"]) * 1e+6
        progressFile = os.path.join(os.getcwd(), "progressFiles", format(hash(path), "x") + ".progress")
        c.execute("UPDATE `files` SET `progressFile` = ? WHERE `path` = ?", (progressFile, path))
        conn.commit()
        tmpPath = tempfile.mktemp(suffix=".mkv")
        p = subprocess.Popen([
            "ffmpeg",
            "-progress", progressFile,
            "-v", "quiet",
            # "-t", "10",
            "-i", path,
            "-c:v", "libx265",
            "-x265-params", "log-level=error",
            "-c:a", "aac",
            "-preset", "slow",
            # "-preset", "veryfast",
            "-y",
            tmpPath
        ])
        returnCode = p.wait()
        if returnCode != 0:
            raise Exception("Non zero return code!")
        ownerDir = c.execute("SELECT `dir`.`path` FROM `files`, `dirs` WHERE `dirs`.`id` = `files`.`id` AND `files`.`path` = ? LIMIT 1", (path,)).fetchone()[0]
        preserveLocation = os.path.join(ownerDir, ".preserved", os.path.relpath(path, ownerDir))
        os.makedirs(os.path.dirname(preserveLocation), exist_ok=True)
        os.rename(path, preserveLocation)
        shutil.move(tmpPath, os.path.splitext(path)[0] + ".mkv")
        logging.info("Transcode completed: " + path)
        c.execute("UPDATE `files` SET `state` = 'done' WHERE `path` = ?", (path,))
        conn.commit()

    @property
    def wu(self):
        if self.latestJob == None:
            return None
        conn = _conn()
        c = conn.cursor()
        url = c.execute("SELECT `progressFile` FROM `files` WHERE path = ? LIMIT 1", (self.latestJob,)).fetchone()[0]
        if url == None:
            return None
        data = []
        with open(url, "r") as f:
            probe = {}
            for line in f:
                line = line.strip()
                l = line.split("=")
                probe[l[0]] = l[1]
                if l[0] == "progress":
                    data.append(probe)
                    probe = {}

        return int(data.pop()["out_time_us"])


class FileQueryWorker(Consumer):

    @classmethod
    def doWork(cls, job):
        path = job
        p = subprocess.Popen(["ffprobe", "-loglevel", "quiet", "-print_format", "json", "-show_streams", "-select_streams", "v:0", path], stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        data = json.loads(stdout)
        streams = cls.sortStreams(data["streams"])
        needsTranscoding = streams["video"][0]["codec_name"] != "hevc"
        if needsTranscoding:
            TranscoderWorker.extend([job])
        logging.debug("Probe finished: " + path)
        conn = _conn()
        c = conn.cursor()
        c.execute("UPDATE `files` SET `state` = ? WHERE `path` = ?", ("queued" if needsTranscoding else "done", path))
        conn.commit()

    @staticmethod
    def sortStreams(streams):
        sortedStreams = {}
        for stream in streams:
            try:
                sortedStreams[stream["codec_type"]].append(stream)
            except KeyError as identifier:
                sortedStreams[stream["codec_type"]] = [stream]
        return sortedStreams

def _findMedia(path):
    mediaFilter = re.compile("(.webm|.mkv|.flv|.flv|.vob|.ogv|.ogg|.drc|.gif|.gifv|.mng|.avi|.MTS|.M2TS|.TS|.mov|.qt|.wmv|.yuv|.rm|.rmvb|.asf|.amv|.mp4|.m4p|.m4v|.mpg|.mp2|.mpeg|.mpe|.mpv|.mpg|.mpeg|.m2v|.m4v|.svi|.3gp|.3g2|.mxf|.roq|.nsv|.flv|.f4v|.f4p|.f4a|.f4b)$", flags=re.IGNORECASE)
    files = [
        os.path.join(dirpath, filename)
        for dirpath, dirnames, filenames in os.walk(path) if not os.path.relpath(dirpath, path).startswith(".preserved")
        for filename in filenames if mediaFilter.match(os.path.splitext(filename)[1]) != None
    ]
    return files

# TODO implement dir watch


class HttpServerWorker:

    class API:

        @classmethod
        def parseRequest(cls, method, path):
            if method == "GET":
                try:
                    return {
                        "ping": cls.ping,
                        "files/search": cls.Files.search,
                        "workers/list": cls.Workers.list,
                        "dirs/list": cls.Dirs.list
                    }["/".join(path)]
                except IndexError as e:
                    Exception("Command not found!")
            elif method == "POST":
                try:
                    return {
                        "dirs/insert": cls.Dirs.insert
                    }["/".join(path)]
                except IndexError as e:
                    Exception("Command not found!")
            else:
                Exception("Invalid method!")

        class Dirs:
            @staticmethod
            def list(qs):
                parts = ["`dirs`.`id`"]
                for qs_part in qs["part"]:
                    parts.extend({
                        "path": ["`dirs`.`path`"],
                        "id": ["`dirs`.`id`"],
                        "filesCount": ["COUNT(`files`.`id`)"]
                    }[qs_part])
                fields = ", ".join(parts)
                conn = _conn()
                c = conn.cursor()
                dirs = {
                    dir[0]: {
                        qs["part"][dirDataI]: dirData for dirDataI, dirData in enumerate(dir[1:])
                    } for diri, dir in enumerate(c.execute("SELECT {} FROM `dirs`, `files` WHERE `files`.`dirId` = `dirs`.`id` GROUP BY `dirs`.`id`".format(fields)).fetchall())
                }
                return (http.HTTPStatus.OK, "application/json", {"status": "OK", "data": dirs})

            @staticmethod
            def insert(qs):
                path = qs["path"][0]
                files = _findMedia(path)

                conn = _conn()
                c = conn.cursor()
                c.execute("INSERT INTO `dirs` (`path`) VALUES (?)", (path,))
                dirId = c.execute("SELECT `id` FROM `dirs` WHERE `path` = ? LIMIT 1", (path,)).fetchone()[0]
                c.executemany("INSERT INTO `files` (`path`, `dirId`) VALUES (?, ?) ON CONFLICT(`path`) DO NOTHING", [(f, dirId) for f in files])
                conn.commit()

                FileQueryWorker.extend(files)
                # TODO: create a dir watch
                logging.info("{} files found.".format(len(files)))
                return (http.HTTPStatus.OK, "application/json", {"status": "OK"})

        class Files:
            @staticmethod
            def get(qs):
                parts = ["`id`"]
                for qs_part in qs["part"]:
                    parts.extend({
                        "id": ["`id`"],
                        "path": ["`path`"],
                        "state": ["`state`"],
                        "dirId": ["`dirId`"]
                    }[qs_part])
                fields = ", ".join(parts)
                id = qs["id"][0]
                conn = _conn()
                c = conn.cursor()
                files = {
                    f[0]: {
                        qs["part"][fdi]: f[fdi] for fdi, fd in enumerate(parts[1:])
                    } for fi, f in enumerate(c.execute("SELECT {} FROM `files` WHERE `id` = ? LIMIT 1".format(fields), (id,)).fetchone())
                }
                return (http.HTTPStatus.OK, "application/json", files)

            @staticmethod
            def search(qs):
                parts = ["`id`"]
                for qs_part in qs["part"]:
                    parts.extend({
                        "id": ["`id`"],
                        "path": ["`path`"],
                        "state": ["`state`"]
                    }[qs_part])
                fields = ", ".join(parts)
                filters = []
                if list(qs.keys()).count("dirId") > 0:
                    filters.append(["`dirId`", qs["dirId"][0]])
                elif list(qs.keys()).count("state") > 0:
                    filters.append(["`state`", qs["state"][0]])
                else:
                    Exception("Missing filter")

                query = "SELECT {} FROM `files`".format(fields)
                params = []
                if len(filters) > 0:
                    query += " WHERE"
                    for filter in filters:
                        query += " {} = ?".format(filter[0])
                        params.append(filter[1])
                conn = _conn()
                c = conn.cursor()
                files = {
                    f[0]: {
                        qs["part"][fdi]: fd for fdi, fd in enumerate(f[1:])
                    } for fi, f in enumerate(c.execute(query, params).fetchall())
                }
                return (http.HTTPStatus.OK, "application/json", files)
        class Workers:
            @staticmethod
            def list(qs):
                workers = {format(id(worker), "x"): {"state": worker.state.name, "latestJob": worker.latestJob, "totalWu": worker.totalWu, "wu": worker.wu, "type": type(worker).__name__} for worker in list(transcoderWorkers.keys()) + list(fileQueryWorkers.keys())}
                return (http.HTTPStatus.OK, "application/json", workers)


        @staticmethod
        def ping(qs):
            return (http.HTTPStatus.OK, "application/json", {"status": "OK", "message": qs["message"][0]})

    class HttpServer(http.server.SimpleHTTPRequestHandler):

        def parseRequest(self, method):
            urlComp = urllib.parse.urlparse(self.path)
            if method == "GET":
                qs = urllib.parse.parse_qs(urlComp.query)
            elif method == "POST":
                contentLength = int(self.headers["Content-Length"])
                qs = urllib.parse.parse_qs(self.rfile.read(contentLength).decode())
            path = urlComp.path.split("/")[1:]
            l0 = path.pop(0)
            if l0 == "api":
                try:
                    deligate = HttpServerWorker.API.parseRequest(method, path)
                    returnCode, contentType, data = deligate(qs)
                    if contentType == "application/json":
                        data = json.dumps(data)
                except Exception as e:
                    returnCode = http.HTTPStatus.INTERNAL_SERVER_ERROR
                    contentType = "application/json"
                    data = json.dumps({"status": "error", "exception": traceback.format_exc()})
                self.send_response(returnCode)
                self.send_header("Content-Type", contentType)
                self.end_headers()
                self.wfile.write(data.encode())
            elif l0 == "web":
                super().do_GET()
            else:
                self.send_response(404)
                self.end_headers()

        def do_GET(self):
            self.parseRequest("GET")
        def do_POST(self):
            self.parseRequest("POST")

    def serve_forever(self):
        threading.currentThread().setName("HttpServerWorker")

        port = 6969
        server = http.server.ThreadingHTTPServer
        handler = self.HttpServer

        with server(("", port), handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt as e:
                httpd.socket.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    logging.info("Running setup")
    conn = _conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS `dirs` (
        `id` INTEGER PRIMARY KEY AUTOINCREMENT,
        `path` TEXT UNIQUE NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS `files` (
        `id` INTEGER PRIMARY KEY AUTOINCREMENT,
        `path` TEXT UNIQUE NOT NULL,
        `dirId` TEXT NOT NULL,
        `state` TEXT NULL DEFAULT "added",
        `progressFile` NULL DEFAULT NULL,
        `added` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(`dirId`) REFERENCES `dirs`(`id`)
    )''')
    conn.commit()
    logging.info("Setup complete")


    TranscoderWorker.extend([f[0] for f in c.execute("SELECT `path` FROM `files` WHERE `state` IS ? ORDER BY `added` ASC", ("queued",)).fetchall()])

    FileQueryWorker.extend([f[0] for f in c.execute("SELECT `path` FROM `files` WHERE `state` IS ? ORDER BY `added` ASC", ("added",)).fetchall()])

    httpServerWorker = threading.Thread(target=HttpServerWorker().serve_forever)
    httpServerWorker.start()

    fileQueryWorkers = {}
    for i in range(2):
        fileQueryWorker = FileQueryWorker()
        fileQueryWorkers[fileQueryWorker] = threading.Thread(target=fileQueryWorker.run, name="FileQueryWorker" + str(i))
    transcoderWorkers = {}
    for i in range(1):
        transcoderWorker = TranscoderWorker()
        transcoderWorkers[transcoderWorker] = threading.Thread(target=transcoderWorker.run, name="TranscoderWorker" + str(i))

    for x in fileQueryWorkers:
        fileQueryWorkers[x].start()
    for x in transcoderWorkers:
        transcoderWorkers[x].start()
