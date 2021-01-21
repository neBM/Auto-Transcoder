import abc
import enum
import http.server
import json
import logging
import math
import os
import re
import shutil
import socketserver
import sqlite3
import subprocess
import tempfile
import threading
import time
import traceback
import urllib.parse
import uuid

PORT = 5252
files = {}

def _connect():
    return sqlite3.connect("/config/sqlite.db")

class Worker (abc.ABC):
    class File:
        def __init__(self, fid, file_details):
            self.fid = fid
            self.file_details = file_details

        @property
        def v_encoder(self):
            """
            Get the video encoder
            """
            with _connect() as conn:
                c = conn.cursor()
                return c.execute("SELECT `Directories`.`vencoder` FROM `Files` LEFT JOIN `Directories` ON `Files`.`parentDir` = `Directories`.`path` WHERE `uuid` = ? LIMIT 1", (str(self.fid),)).fetchone()[0]
                
        @property
        def a_encoder(self):
            """
            Get the audio encoder
            """
            with _connect() as conn:
                c = conn.cursor()
                return c.execute("SELECT `Directories`.`aencoder` FROM `Files` LEFT JOIN `Directories` ON `Files`.`parentDir` = `Directories`.`path` WHERE `uuid` = ? LIMIT 1", (str(self.fid),)).fetchone()[0]

        @property
        def s_encoder(self):
            """
            Get the audio encoder
            """
            with _connect() as conn:
                c = conn.cursor()
                return c.execute("SELECT `Directories`.`sencoder` FROM `Files` LEFT JOIN `Directories` ON `Files`.`parentDir` = `Directories`.`path` WHERE `uuid` = ? LIMIT 1", (str(self.fid),)).fetchone()[0]

        @property
        def streams(self):
            """
            Get the streams
            """
            with _connect() as conn:
                c = conn.cursor()
                return json.loads(c.execute("SELECT `streams` FROM `Files` WHERE `uuid` = ? LIMIT 1", (str(self.fid),)).fetchone()[0])

        @property
        def format(self):
            """
            Get the audio encoder
            """
            with _connect() as conn:
                c = conn.cursor()
                return json.loads(c.execute("SELECT `format` FROM `Files` WHERE `uuid` = ? LIMIT 1", (str(self.fid),)).fetchone()[0])

    class State (enum.Enum):
        WAITING = enum.auto()
        RUNNING = enum.auto()
        FAILED = enum.auto()

    def __init__(self, workder_id):
        self.worker_id = workder_id
        self.current_job = None

    @classmethod
    def has_next(cls):
        return len(cls.queue) > 1

    @classmethod
    def pop(cls):
        return cls.queue.pop(0)

    @classmethod
    def add(cls, job):
        cls.queue.append(job)
        logging.debug("1 new job added to {}".format(cls.__name__))
        with cls.c:
            cls.c.notify(1)

    @classmethod
    def add_all(cls, jobs):
        cls.queue.extend(jobs)
        logging.debug("{} new jobs added to {}".format(len(jobs), cls.__name__))
        with cls.c:
            cls.c.notify(len(jobs))

    def run(self):
        try:
            while True:
                with self.c:
                    while not self.has_next():
                        self.state = self.State.WAITING
                        logging.info("{} waiting for next job".format(threading.current_thread().name))
                        self.c.wait()
                self.state = self.State.RUNNING
                next_job = self.pop()
                try:
                    self.doWork(next_job)
                    with _connect() as conn:
                        c = conn.cursor()
                        c.execute("INSERT INTO `Events` (`fileId`, `level`, `message`) VALUES (?, ?, ?)", (str(next_job.fid), logging.INFO, "{} completed".format(threading.current_thread().name)))
                        conn.commit()
                except Exception:
                    exc = traceback.format_exc()
                    print(exc)
                    with _connect() as conn:
                        c = conn.cursor()
                        c.execute("INSERT INTO `Events` (`fileId`, `level`, `message`) VALUES (?, ?, ?)", (str(next_job.fid), logging.ERROR, exc))
        except Exception:
            self.state = self.State.FAILED

    @abc.abstractmethod
    def doWork(self, file_id):
        raise NotImplementedError()

    def getParts(self, parts):
        data = {}
        if "status" in parts:
            data["status"] = {"state": self.state.name, "type": type(self).__name__}
        if "id" in parts:
            data["id"] = str(self.worker_id)
        if "fileDetails" in parts:
            if self.current_job == None:
                data["fileDetails"] = None
            else:
                data["fileDetails"] = self.current_job.file_details
        if "contentDetails" in parts:
            if self.current_job == None:
                data["contentDetails"] = None
            else:
                data["contentDetails"] = {}
                data["contentDetails"]["streams"] = self.current_job.streams
                data["contentDetails"]["format"] = self.current_job.format
        return data

class ProbeWorker (Worker):
    c = threading.Condition()
    queue = list()
    
    @staticmethod
    def getContentDetails(file_path):
        command = [
            "nice",
            "-n", "10",
            "ffprobe",
            "-show_format",
            "-show_streams",
            "-loglevel", "error",
            "-print_format", "json",
            file_path
        ]
        probe_process = subprocess.Popen(command, stdout=subprocess.PIPE)
        stdout, stderr = probe_process.communicate()
        reutrn_code = probe_process.wait()
        if reutrn_code != 0:
            raise RuntimeError("FFPROBE non-zero return code")

        return json.loads(stdout.decode())

    @classmethod
    def is_atTarget(cls, f):
        streams = {}
        for stream in f.streams:
            if "codec_type" not in stream.keys():
                continue
            if stream["codec_type"] in streams.keys():
                streams[stream["codec_type"]].append(stream)
            else:
                streams[stream["codec_type"]] = [stream]
        if len(streams["video"]) > 1:
            raise NotImplementedError("Multiple video streams not supported")
        if streams["video"][0]["codec_name"] != f.v_encoder:
            return False
        return True

    def doWork(self, f):
        self.current_job = f
        current_file = self.current_job.file_details
        content_details = self.getContentDetails(current_file["filePath"])
        with _connect() as conn:
            c = conn.cursor()
            c.execute("UPDATE `files` SET `streams` = ?, `format` = ? WHERE `uuid` = ?", (json.dumps(content_details["streams"]), json.dumps(content_details["format"]), str(f.fid)))
            conn.commit()
        if not self.is_atTarget(self.current_job):
            TranscoderWorker.add(f)
        self.current_job = None

    def getParts(self, parts):
        data = super().getParts(parts)
        if "processingDetails" in parts:
            data["processingDetails"] = None
        return data

class TranscoderWorker (Worker):
    c = threading.Condition()
    queue = list()

    class ProgressServer (socketserver.TCPServer):

        def __init__(self, server_address, request_handler_class, context, bind_and_activate=True):
            self.context = context
            super().__init__(server_address, request_handler_class, bind_and_activate)

        def setProgress(self, step):
            self.context.progress = step

    class ProgressHandler (socketserver.StreamRequestHandler):
        @classmethod
        def run(cls, context):
            with TranscoderWorker.ProgressServer(("127.0.0.1", 0), cls, context) as tcpd:
                context.setPort(tcpd.server_address[1])
                tcpd.serve_forever()

        def handle(self):
            print("{} wrote:".format(self.client_address[0]))
            step = {}
            while True:
                line = self.rfile.readline().strip().decode().split("=")
                step[line[0]] = line[1]
                if line[0] == "progress":
                    print(step)
                    self.server.setProgress(step)
                    if line[1] != "continue":
                        break
                    time.sleep(1)
                    step = {}
    
    @classmethod
    def stop(cls):
        cls.empty()
        for worker in workers:
            if type(worker) == TranscoderWorker and worker.transcode_process != None:
                worker.transcode_process.terminate()

    @classmethod
    def empty(cls):
        cls.queue.clear()

    def setPort(self, port):
        self.port = port
        with self.port_change_c:
            self.port_change_c.notifyAll()

    def __init__(self, worker_id):
        self.progress = None
        self.port = None
        self.port_change_c = threading.Condition()
        self.transcode_process = None
        super().__init__(worker_id)

    def doWork(self, f):
        file_id = f.fid
        self.current_job = f
        current_file = self.current_job.file_details
        parent_dir = current_file["parentDir"]
        file_path = current_file["filePath"]
        preseve_path = os.path.join(parent_dir, ".preserve", os.path.relpath(file_path, parent_dir))
        with _connect() as conn:
            c = conn.cursor()
            c.execute("UPDATE `Files` SET `preservePath` = ? WHERE `uuid` = ?", (preseve_path, str(file_id)))
            conn.commit()
        logging.info("{} started next job: {}".format(threading.current_thread().name, file_path))
        logging.debug("Preserve: {}".format(preseve_path))

        progress_handler = threading.Thread(target=self.ProgressHandler.run, args=(self,), name="{}.progress".format(threading.current_thread().name))
        progress_handler.start()

        while self.port == None:
            with self.port_change_c:
                self.port_change_c.wait()

        command = [
            "nice",
            "-n", "10",
            "ffmpeg",
            "-i", file_path,
            "-c:v", self.current_job.v_encoder,
            "-c:a", self.current_job.a_encoder,
            "-c:s", self.current_job.s_encoder,
            "-filter:v", "scale=-1:'min(720,ih)'",
            "-f", "matroska",
            "-y",
            "-loglevel", "error",
            "-progress", "tcp://127.0.0.1:{}".format(self.port),
            "-"
        ]
        self.progress = {}

        logging.debug("Executing '{}'".format(" ".join(command)))
        with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as tmp_file:
            self.transcode_process = subprocess.Popen(command, stdout=tmp_file)
        return_code = self.transcode_process.wait()
        if return_code != 0:
            raise RuntimeError("FFMPEG non-zero return code")

        self.progress = None

        os.makedirs(os.path.dirname(preseve_path), exist_ok=True)
        shutil.move(file_path, preseve_path)
        shutil.move(tmp_file.name, os.path.splitext(file_path)[0] + ".mkv")

        ProbeWorker.add(file_id)

        self.current_job = None
        self.port = None

    def getParts(self, parts):
        data = super().getParts(parts)
        if "processingDetails" in parts:
            data["processingDetails"] = self.progress
        return data
        

class HttpHandler (http.server.SimpleHTTPRequestHandler):
    @classmethod
    def run(cls):
        with http.server.ThreadingHTTPServer(("", PORT), cls) as httpd:
            httpd.serve_forever()

    @classmethod
    def get_qs(cls, request, options):
        if request.command == "GET":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(request.path).query)
        elif request.command == "POST":
            content_length = int(request.headers.get("content-length"))
            qs = urllib.parse.parse_qs(request.rfile.read(content_length).decode())
        else:
            raise ValueError("Command '{}' not supported".format(request.command))
        return cls.parse_qs(qs, options)

    @classmethod
    def parse_qs(cls, qs, options):
        for q in qs:
            if not q in options:
                raise ValueError("Unrecognised option '{}'".format(q))
        return qs

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.split("/")[1] == "web":
            return super().do_GET()
        elif url.path.split("/")[1] == "api":
            self.handle_apiRequest()

        elif url.path == "/":
            self.send_response(http.HTTPStatus.MOVED_PERMANENTLY)
            self.send_header("Location", "/web/index.html")
            self.end_headers()
        else:
            self.send_response(http.HTTPStatus.NOT_FOUND)
            self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path.split("/")[1:]
        if path[0] != "api":
            raise ValueError()
        self.handle_apiRequest()

    def handle_apiRequest(self):
        try:
            response_code, headers, data = self.API.parse(self)(self)
            self.send_response(response_code)
            for header in headers:
                self.send_header(header, headers[header])
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(http.HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("content-type", "text/plain")
            self.end_headers()
            self.wfile.write(traceback.format_exc().encode())

    class API:
        @classmethod
        def parse(cls, request):
            url = urllib.parse.urlparse(request.path)
            path = url.path.split("/")[1:]
            print("{} Command: {}".format(request.command, path))
            try:
                return {
                    "POST": {
                        "dir": {
                            "add": cls.Dir.add
                        },
                        "worker": {
                            "stop": cls.Worker.stop,
                            "skip": cls.Worker.skip,
                            "clear": cls.Worker.empty
                        }
                    },
                    "GET": {
                        "server": {
                            "backup": cls.Server.backup,
                            "codecs": cls.Server.codecs
                        },
                        "file": {
                            "list": cls.File.list
                        },
                        "worker": {
                            "list": cls.Worker.list
                        }
                    }
                }[request.command][path[1]][path[2]]
            except KeyError:
                raise ValueError("Command not found")

        class Server:
            @classmethod
            def backup(cls, request):
                with open("/config/sqlite.db", "rb") as f:
                    return (http.HTTPStatus.OK, {"Content-Disposition": "attachment", "Content-Type": "application/octet-stream"}, f.read())

            @classmethod
            def codecs(cls, request):
                return (http.HTTPStatus.OK, {}, json.dumps({"status": "OK", "codecs": cls.get_codecs()}).encode())

            @staticmethod
            def get_codecs():
                p = subprocess.Popen(["ffmpeg", "-codecs", "-loglevel", "quiet"], stdout=subprocess.PIPE)
                return_code = p.wait()
                if return_code != 0:
                    raise RuntimeError("FFPROBE non-zero return code")
                stcout, stderr = p.communicate()
                codecs = []
                for row in stcout.decode().split("-------\n")[1].split("\n"):
                    if row.strip() == "":
                        continue
                    fields = re.split("\s+", row)
                    codecs.append({"decoder": fields[1][0] == "D", "encoder": fields[1][1] == "E", "type": fields[1][2], "intra_frame-only": fields[1][3] == "I", "lossy": fields[1][4] == "L", "lossless": fields[1][5] == "S", "id": fields[2], "name": " ".join(fields[3:])})
                return codecs


        class Worker:
            @classmethod
            def list(cls, request):
                part = HttpHandler.get_qs(request, ["part"])["part"][0]
                return (http.HTTPStatus.OK, {}, json.dumps({"status": "OK", "workers": [workers[x][0].getParts(part.split(",")) for x in workers]}).encode())

            @classmethod
            def stop(cls, request):
                worker_id = HttpHandler.get_qs(request, ["workerId"])["workerId"][0]
                workers[uuid.UUID(worker_id)].stop()
                return (http.HTTPStatus.OK, {}, json.dumps({"status": "OK"}))

            @classmethod
            def skip(cls, request):
                worker_id = HttpHandler.get_qs(request, ["workerId"])["workerId"][0]
                workers[uuid.UUID(worker_id)].skip()
                return (http.HTTPStatus.OK, {}, json.dumps({"status": "OK"}))

            @classmethod
            def empty(cls, request):
                worker_id = HttpHandler.get_qs(request, ["workerId"])["workerId"][0]
                workers[uuid.UUID(worker_id)].empty()
                return (http.HTTPStatus.OK, {}, json.dumps({"status": "OK"}))

        class File:
            @classmethod
            def list(cls, request):
                qs = HttpHandler.get_qs(request, ["page", "perPage", "parts"])
                if "page" in qs:
                    page = int(qs["page"][0])
                else:
                    page = 0
                if "perPage" in qs:
                    per_page = int(qs["perPage"][0])
                else:
                    per_page = 30

                parts = qs["parts"][0].split(",")

                with _connect() as conn:
                    c = conn.cursor()
                    files = []
                    for f_row in c.execute("SELECT `uuid`, `parentDir`, `filePath`, `streams`, `format` FROM `Files` LIMIT ?, ?", (page * per_page, per_page)):
                        f = {"uuid": f_row[0]}
                        for part in parts:
                            if part == "fileDetails":
                                f["fileDetails"] = {"parentDir": f_row[1], "filePath":  f_row[2]}
                            elif part == "contentDetails":
                                f["contentDetails"] = {"streams":  json.loads(f_row[3]), "format":  json.loads(f_row[4])}
                            elif part == "events":
                                f["events"] = [{"id": event[0], "timestamp": event[1], "level": event[2], "message": event[3]} for event in c.execute("SELECT `id`, `timestamp`, `level`, `message` FROM `Events` WHERE `fileId` = ?", f_row[0]).fetchall()]
                            else:
                                raise ValueError("Part '{}' not found".format(part))
                        files.append(f)

                return (http.HTTPStatus.OK, {}, json.dumps({"status": "OK", "pages": math.ceil(c.execute("SELECT COUNT(`uuid`) FROM `files`").fetchone()[0] / per_page), "files": files}).encode())

        class Dir:

            @classmethod
            def add(cls, request):
                qs = HttpHandler.get_qs(request, ["path", "vencoder", "aencoder", "sencoder"])
                path = qs["path"][0]
                new_files = []
                with _connect() as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO `Directories` (`path`, `vencoder`, `aencoder`, `sencoder`) VALUES (?, ?, ?, ?)", (path, qs["vencoder"][0], qs["aencoder"][0], qs["sencoder"][0]))
                    for dirpath, dirnames, filenames in os.walk(path, topdown=True):
                        dirnames[:] = [d for d in dirnames if d[0] != "."]
                        filenames = [f for f in filenames if f[0] != "."]
                        # TODO fix
                        for filename in filenames:
                            if not cls.is_media_file(filename):
                                continue
                            f = Worker.File(uuid.uuid4(), {"parentDir": path, "filePath": os.path.join(dirpath, filename)})
                            new_files.append(f)
                            c.execute("INSERT INTO `Files` (`uuid`, `parentDir`, `filePath`) VALUES (?, ?, ?)", (str(f.fid), f.file_details["parentDir"], f.file_details["filePath"]))
                    conn.commit()
                for f in new_files:
                    files[f.fid] = f
                    ProbeWorker.add(f)
                return (http.HTTPStatus.OK, {}, json.dumps({"status": "OK", "count": len(new_files)}).encode())

            @staticmethod
            def is_media_file(filename):
                return re.search("(.webm|.mkv|.flv|.flv|.vob|.ogv|.ogg|.drc|.gif|.gifv|.mng|.avi|.MTS|.M2TS|.TS|.mov|.qt|.wmv|.yuv|.rm|.rmvb|.asf|.amv|.mp4|.m4p|.m4v|.mpg|.mp2|.mpeg|.mpe|.mpv|.mpg|.mpeg|.m2v|.m4v|.svi|.3gp|.3g2|.mxf|.roq|.nsv|.flv|.f4v|.f4p|.f4a|.f4b)$", filename, re.IGNORECASE) != None

def load():
    with _connect() as c:
        for f in c.execute("SELECT `uuid`, `parentDir`, `filePath`, `streams` FROM `Files`").fetchall():
            try:
                fid = uuid.UUID(f[0])
                files[fid] = Worker.File(fid, {"parentDir": f[1], "filePath": f[2]})
                try:
                    if f[3] == None:
                        ProbeWorker.add(files[fid])
                    elif not ProbeWorker.is_atTarget(files[fid]):
                        TranscoderWorker.add(files[fid])
                except NotImplementedError as e:
                    traceback.print_exc()
            except Exception as e:
                logging.error("Failed to import file '{}'".format(f[0]))
                raise e

workers = {}

with _connect() as conn:
    c = conn.cursor()
    with open("setup.sql", "r") as f:
        c.executescript(f.read())
    conn.commit()

if __name__ == "__main__":
    load()

    TRANSCODE_WORKERS = int(os.getenv("TRANSCODE_WORKERS", 1))
    PROBE_WORKERS = int(os.getenv("PROBE_WORKERS", 1))

    logging.basicConfig(level=logging.DEBUG)
    httpServerThread = threading.Thread(target=HttpHandler.run)
    httpServerThread.start()

    for i in range(TRANSCODE_WORKERS):
        workerId = uuid.uuid4()
        transcoderWorker = TranscoderWorker(workerId)
        workers[workerId] = (transcoderWorker, threading.Thread(target=transcoderWorker.run, name="transcoderWorker{}".format(i)))
        workers[workerId][1].start()

    for i in range(PROBE_WORKERS):
        workerId = uuid.uuid4()
        probeWorker = ProbeWorker(workerId)
        workers[workerId] = (probeWorker, threading.Thread(target=probeWorker.run, name="probeWorker{}".format(i)))
        workers[workerId][1].start()
