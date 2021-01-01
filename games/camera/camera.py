# imports
import imutils
import time
import cv2
import imagezmq
import threading
import numpy as np
import multiprocessing as mp
from datetime import datetime
import os

VIDEO_DIR = "videos"

class Camera:
    def __init__(self, name=None, source=None, flip=False, *args, **kwargs):
        self.name = name
        self.source = source
        self.flip = flip
        self.recording = False
        self.writer = None
        self.h = None
        self.w = None
        self.initialized = False
        self.width = 600

        self.teams = "None-vs-None"

    def initialize(self):
        pass

    def get_frame(self):
        self.last_frame = self._get_frame()

    def _get_frame(self):
        pass

    def acquire_movie(self):
        while True:
            self.get_frame()
            if self.recording:
                if self.writer is None:
                    self.initialize_writer()
                elif self.writer is not None:
                    self.writer.write(self.last_frame)
                else:
                    continue

    def initialize_writer(self):
        self.fourcc = cv2.VideoWriter_fourcc(*"MJPG") # use with the .avi file extension
        (self.h, self.w) = self._get_frame().shape[:2]
        filename = self.name + "_" + self.teams + "_" \
                   + datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".avi"
        self.filepath = os.path.join(VIDEO_DIR, filename)
        self.writer = cv2.VideoWriter(self.filepath, self.fourcc, 18, (self.w, self.h), True)

    def start_recording(self):
        self.recording = True

    def stop_recording(self):
        if self.recording:
            self.recording = False
        if self.writer is not None:
            self.writer.release()
            print("File saved successfully: {}".format(self.filepath))
            self.writer = None

    def set_teams(self, teamHome, teamAway):
        self.teams = teamHome + "-vs-" + teamAway

    def __str__(self):
        return "{}: {}".format(self.__class__.__name__, self.name, self.source)

    def close_camera(self):
        self.stop_recording()
        self.teams = "None-vs-None"
        self.initialized = False
        self._close_camera()

    def _close_camera(self):
        pass


class USBCamera(Camera):
    def __init__(self, name=None, source=None, flip=False, *args, **kwargs):
        super(USBCamera, self).__init__(*args, **kwargs)
        self.source = int(source)

    def initialize(self):
        if not self.initialized:
            self.cap = cv2.VideoCapture(self.source)
            time.sleep(2)
            self.get_frame()
            self.initialized = True

    def _get_frame(self):
        ret, frame = self.cap.read()
        frame = imutils.resize(frame, width=self.width)
        if self.flip:
            frame = cv2.flip(frame, 1)
        return frame

    def _close_camera(self):
        self.cap.release()

class RTSPCamera(Camera):
    def __init__(self, name=None, source=None, flip=False, *args, **kwargs):
        super(RTSPCamera, self).__init__(*args, **kwargs)
        self.name = name
        self.source = str(source)
        self.flip = flip
        self.recording = False
        self.writer = None
        self.h = None
        self.w = None

        self.receiver = None
        self.width = 600
        self.last_frame = None
        self.initialized = False

    def initialize(self):
        if not self.initialized:
            # use multiprocessing
            self.parent_conn, child_conn = mp.Pipe()
            self.is_open = True
            self.p = mp.Process(target=self.rtsp_update, args=(child_conn, self.source, self.is_open))

            # start the process
            self.p.daemon = True
            self.p.start()
            self.get_frame()
            self.initialized = True

    def _get_frame(self):
        # request a frame and send ack
        self.parent_conn.send(1)
        frame = self.parent_conn.recv()
        self.parent_conn.send(0)

        # convert to RGB and resize
        #frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = imutils.resize(frame, width=self.width)
        if self.flip:
            frame = cv2.flip(frame, 1)
        return frame

    def rtsp_update(self, conn, rtsp, is_open):
        cap = cv2.VideoCapture(rtsp)  # ,cv2.CAP_FFMPEG)
        while is_open:
            # grab frames from the buffer
            cap.grab()

            # recieve input data
            rec_dat = conn.recv()
            if rec_dat == 1:
                # if frame requested
                ret, frame = cap.read()
                conn.send(frame)
            elif rec_dat == 2:
                # if close requested
                cap.release()
                break
        print("Camera Connection Closed")
        conn.close()

    def _close_camera(self):
        self.is_open = False

class ImageZMQCamera(Camera):
    def __init__(self, name, source, flip=False, *args, **kwargs):
        super(ImageZMQCamera, self).__init__(*args, **kwargs)
        self.name = name
        self.source = str(source).split(",")[0]
        self.port = str(source).split(",")[1]
        self.flip = flip
        self.recording = False
        self.writer = None
        self.h = None
        self.w = None
        self.width = 600

        self.image_hub = None
        self.last_frame = None
        self.initialized = False

    def initialize(self):
        if not self.initialized:
            self.image_hub = imagezmq.ImageHub('tcp://*:' + self.port)
            frame = cv2.imread('views/ui/oddball.png')
            self.last_frame = imutils.resize(frame, width=600)
            self.initialized = True

    def _get_frame(self):
        rpi_name, frame = self.image_hub.recv_image()
        #image = cv2.imdecode(np.frombuffer(jpg_buffer, dtype='uint8'), -1)
        self.image_hub.send_reply(b'OK')
        frame = imutils.resize(frame, width=self.width)
        if self.flip:
            frame = cv2.flip(frame, 1)
        return frame

    def _close_camera(self):
        self.image_hub = None

class PubSubImageZMQCamera(Camera):
    def __init__(self, name, source, flip=False, *args, **kwargs):
        super(PubSubImageZMQCamera, self).__init__(*args, **kwargs)
        self.name = name
        self.source = source
        self.flip = flip
        self.recording = False
        self.writer = None
        self.h = None
        self.w = None
        self.width = 600

        self.hostname = str(source)
        self.port = 5555
        self.receiver = None
        self.last_frame = None

        self.initialized = False

    def initialize(self):
        if not self.initialized:
            self.receiver = VideoStreamSubscriber(self.hostname, self.port)
            self.get_frame()
            self.initialized = True

    def _get_frame(self):
        msg, frame = self.receiver.receive()
        image = cv2.imdecode(np.frombuffer(frame, dtype='uint8'), -1)

        frame = imutils.resize(image, width=self.width)
        if self.flip:
            frame = cv2.flip(frame, 1)
        return frame

    def _close_camera(self):
        self.receiver.close()

class VideoStreamSubscriber:
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self._stop = False
        self._data_ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=())
        self._thread.daemon = True
        self._thread.start()

    def receive(self, timeout=15.0):
        flag = self._data_ready.wait(timeout=timeout)
        if not flag:
            raise TimeoutError(
                "Timeout while reading from subscriber tcp://{}:{}".format(self.hostname, self.port))
        self._data_ready.clear()
        return self._data

    def _run(self):
        receiver = imagezmq.ImageHub("tcp://{}:{}".format(self.hostname, self.port), REQ_REP=False)
        while not self._stop:
            self._data = receiver.recv_jpg()
            self._data_ready.set()
        receiver.close()

    def close(self):
        self._stop = True