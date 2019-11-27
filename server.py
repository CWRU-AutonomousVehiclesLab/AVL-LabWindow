import io
import picamera
import logging
import socketserver
from threading import Condition
from http import server
from os import curdir,sep

PORT_NUMBER = 8000

#! Refer to https://raw.githubusercontent.com/RuiSantosdotme/Random-Nerd-Tutorials/master/Projects/rpi_camera_surveillance_system.py

#! Spool up a threaded HTTPserver
class ThreadedHTTPServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        # * Multithreading handling:  A condition variable allows one or more threads to wait until they are notified by another thread.
        self.condition = Condition()

    def write(self, buf):
        # * New frame, copy the existing buffer's content and notify all clients it's available
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()  # * Move to the current position

            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class WebPageHandler(server.BaseHTTPRequestHandler):
    #! Happy HTML handeling
    #* Response code refer to: https://www.restapitutorial.com/httpstatuscodes.html
    def do_GET(self):
        #! Logic is Response -> header -> end header -> write content
        if self.path == '/':
            #* Accessing direct ip 
            self.send_response(308) #! Home page will be perminently redirected to index.html
            self.send_header('Location', '/index.html')
            self.end_headers()

        elif self.path.endswith(".html") :
            #! Handle all webpage access request
            with open('/home/pi/index.html', 'rb') as f:
                logging.info('HTML Pre-load successful')
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f.read())

        elif self.path == '/stream.mjpg':
            #! Handle direct stream request
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            while True:
                try:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    #* MJPG Streaming                        
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                except Exception as e:
                    logging.warning(
                        'Removed streaming client %s: %s',
                        self.client_address, str(e))
                    break
                except KeyboardInterrupt:
                    break
        else:
            #! I do not have the thing you need.
            self.send_error(404)
            self.end_headers()


with picamera.PiCamera(resolution='1280x720', framerate=30) as camera:
    print('PiCamera initialized successfully!')
    output = StreamingOutput()

    #! Get video Stream
    camera.start_recording(output, format='mjpeg')
    """
    If output is a string, it will be treated as a filename for a new file which the video will be written to. 
    Otherwise, output is assumed to be a file-like object and the video data is appended to it 
    (the implementation only assumes the object has a write() method - no other methods will be called).
    """

    try:
        address = ('', PORT_NUMBER)
        #! Start a streaming server
        #* Refer to: https://gist.github.com/n3wtron/4624820
        server = ThreadedHTTPServer(address, WebPageHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()



""" 
Main Logic:
start program -> Start server -> start frame looping

Get stream -> Write to buffer -> stream
"""