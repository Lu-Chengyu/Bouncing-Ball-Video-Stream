# Bouncing Ball Video Stream
 
## Overview

This project demonstrates a simple server-client application that streams a video of a bouncing ball from the server to the client using WebRTC. The client tracks the position of the ball in real-time and sends the coordinates back to the server.

### Dependencies
- Linux(Ubuntu 20.04 recommended)
- Python3(3.9recommended)
- Python numpy(http://www.numpy.orgl)
- Python opencv(https://pypi.org/project/opencv-python/)
- Pythonaiortc(https://github.com/aiortc/aiortc)
- Python multiprocessing(https://docs.python.org/3.9/ibrary/multiprocessing.html)


## Features

* [x] Using `aiortc` built-in TCPSocketSignaling to setup server and client

* [x] The Server generates continuous 2D bouncing ball images

* [x] The Server transports these images by `MediaStreamTrack`

* [x] The Client receives images on the socket

* [x] The Client displays the images by `opencv`

* [x] The Client starts a new process to handle the recognition task

* [x] The Client transports data between process using `Queue`, `Value` in `multiprocessing`

* [x] The Client parses the image and gets the position of the bouncing ball Using `opencv`

* [x] The Client transports predicted position to the server using data channel.

* [x] The Server print the received coordinates and compute the error to the actual position

* [x] Docstrings


## Installation & Running

1. Install the required dependencies:
   ```bash
   pip install opencv-python numpy aiortc av asyncio argparse pytest
   ```

2. Run the Server and Client
   ```bash
   python server.py

   python client.py
   ```

The server generates the video stream with a bouncing ball and handles the signaling and communication with the client.

The client receives the video stream from the server, displays it, tracks the position of the ball, and sends the coordinates back to the server.

## Files
- \_\_init\_\_.py: module file
- client.py: client
- server.py: server
- README.md: README
