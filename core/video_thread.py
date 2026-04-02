import av
import numpy as np
import time
from PyQt6.QtCore import QThread, pyqtSignal


class VideoThread(QThread):

    frame_ready = pyqtSignal(np.ndarray)
    position = pyqtSignal(float)

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.running = True
        self.seek_pos = None
        self.current_time = 0

    def run(self):

        while self.running:

            try:
                container = av.open(
                    self.path,
                    options={
                        "fflags": "discardcorrupt",
                        "err_detect": "ignore_err",
                        "analyzeduration": "1000000",
                        "probesize": "1000000",
                    },
                )
            except Exception as e:
                print("OPEN FAIL:", e)
                time.sleep(1)
                continue

            try:
                stream = container.streams.video[0]
            except:
                print("NO VIDEO STREAM")
                container.close()
                return

            fps = float(stream.average_rate) if stream.average_rate else 25
            delay = 1 / fps

            try:
                for frame in container.decode(video=0):

                    if not self.running:
                        break

                    if self.seek_pos is not None:
                        try:
                            container.seek(int(self.seek_pos * av.time_base))
                        except:
                            pass
                        self.seek_pos = None
                        break

                    try:
                        img = frame.to_ndarray(format="bgr24")
                    except:
                        continue

                    if frame.pts:
                        self.current_time = int(
                            frame.pts * frame.time_base * 1000
                        )
                        self.position.emit(
                            float(frame.pts * stream.time_base)
                        )

                    self.frame_ready.emit(img)

                    time.sleep(delay)

            except Exception as e:
                print("DECODE FAIL -> REOPEN:", e)

            container.close()
            time.sleep(0.5)

    def stop(self):
        self.running = False
        self.wait()

    def seek(self, sec):
        self.seek_pos = sec