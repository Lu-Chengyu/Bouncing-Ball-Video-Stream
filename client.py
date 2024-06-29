import argparse
import asyncio
import cv2
import numpy as np
import multiprocessing as mp
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import create_signaling

class FrameDisplay:
    """
    A class to display frames using OpenCV.
    """
    def __init__(self, name, track):
        """
        Initialize the FrameDisplay with a name and a track.

        Args:
            name (str): The name for the display window.
            track (MediaStreamTrack): The media stream track to display.
        """
        self.name = name
        self.track = track
    
    async def show(self, frame_queue):
        """
        Display the frames using OpenCV.

        Args:
            frame_queue (Queue): The queue to put frames for display.
        """
        if self.track is None:
            return

        while True:
            frame = None
            try:
                frame = await self.track.recv()
            except Exception:
                break
            if frame is None:
                break

            ball_frame = frame.to_ndarray(format="bgr24")
            timestamp = frame.pts
            frame_queue.put((ball_frame, timestamp))
            cv2.imshow(self.name, ball_frame)
            key = cv2.waitKey(1) 
            if key == ord('q'):
                break

        cv2.destroyAllWindows()

def get_ball_contours(frame):
    """
    Recognize the position of the ball using cv2.findContours.

    Args:
        frame (ndarray): The frame to process.

    Returns:
        tuple: The coordinates of the ball center.
    """
    lower_bound = np.array([0, 0, 200])
    upper_bound = np.array([180, 55, 255])
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_frame, lower_bound, upper_bound)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    max_contour = max(contours, key=cv2.contourArea)
    contours_poly = cv2.approxPolyDP(max_contour, 3, True)
    center, _ = cv2.minEnclosingCircle(contours_poly)
    return center

async def track_ball_position(frame_queue, pos_x, pos_y, timestamp):
    """
    Coroutine to track the position of the ball and update shared values.

    Args:
        frame_queue (Queue): The queue to get frames for processing.
        pos_x (Value): The shared value for the X position of the ball.
        pos_y (Value): The shared value for the Y position of the ball.
        timestamp (Value): The shared value for the timestamp.
    """
    while True:
        frame, pts = frame_queue.get(True)
        pos = get_ball_contours(frame)
        if pos:
            pos_x.value = pos[0]
            pos_y.value = pos[1]
            timestamp.value = pts

def run_recognition_task(frame_queue, pos_x, pos_y, timestamp):
    """
    Main function to start the recognition task.

    Args:
        frame_queue (Queue): The queue to get frames for processing.
        pos_x (Value): The shared value for the X position of the ball.
        pos_y (Value): The shared value for the Y position of the ball.
        timestamp (Value): The shared value for the timestamp.
    """
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(track_ball_position(frame_queue, pos_x, pos_y, timestamp))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

async def handle_signaling(peer_connection, signaling):
    """
    Handle the signaling messages for the client side.

    Args:
        peer_connection (RTCPeerConnection): The peer connection.
        signaling (Signaling): The signaling method.
    """
    while True:
        obj = await signaling.receive()
        if isinstance(obj, RTCSessionDescription):
            await peer_connection.setRemoteDescription(obj)
            if obj.type == 'offer':
                await peer_connection.setLocalDescription(await peer_connection.createAnswer())
                await signaling.send(peer_connection.localDescription)
        elif isinstance(obj, RTCIceCandidate):
            await peer_connection.addIceCandidate(obj)
        else:
            break

async def send_position_on_change(channel, pos_x, pos_y, timestamp):
    """
    Send the ball position when it changes.

    Args:
        channel (RTCDataChannel): The data channel to send the position.
        pos_x (Value): The shared value for the X position of the ball.
        pos_y (Value): The shared value for the Y position of the ball.
        timestamp (Value): The shared value for the timestamp.
    """
    prev_pos_x = pos_x.value
    prev_pos_y = pos_y.value
    prev_timestamp = timestamp.value

    while True:
        if pos_x.value != prev_pos_x or pos_y.value != prev_pos_y or timestamp.value != prev_timestamp:
            msg = f'Location {round(pos_x.value, 2)} {round(pos_y.value, 2)} Timestamp {timestamp.value}'
            channel.send(msg)
            prev_pos_x = pos_x.value
            prev_pos_y = pos_y.value
            prev_timestamp = timestamp.value
        await asyncio.sleep(0.1)

async def handle_answer(peer_connection, signaling, frame_queue, pos_x, pos_y, timestamp):
    """
    Handle the answer from the server and respond.

    Args:
        peer_connection (RTCPeerConnection): The peer connection.
        signaling (Signaling): The signaling method.
        frame_queue (Queue): The queue to transfer the ball track.
        pos_x (Value): The shared value for the X position of the ball.
        pos_y (Value): The shared value for the Y position of the ball.
        timestamp (Value): The shared value for the timestamp.
    """
    @peer_connection.on('track')
    async def on_track(track):
        display = FrameDisplay('Ball Tracking', track)
        await display.show(frame_queue)

    @peer_connection.on('datachannel')
    def on_datachannel(channel):
        asyncio.create_task(send_position_on_change(channel, pos_x, pos_y, timestamp))

        @channel.on('message')
        def on_message(message):
            if isinstance(message, str) and message.startswith('result'):
                print(message)
    
    await handle_signaling(peer_connection, signaling)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Signaling parser for the ball tracking system.')
    parser.add_argument('--signaling', type=str, default='tcp-socket', help='Signaling method, default is TCP socket.')
    parser.add_argument('--signaling_host', type=str, default='127.0.0.1', help='Signaling host, default is 127.0.0.1.')
    parser.add_argument('--signaling_port', type=str, default='8080', help='Signaling port, default is 8080.')
    
    args = parser.parse_args()
    
    mp.set_start_method('spawn')
    frame_queue = mp.Queue(100)
    pos_x = mp.Value('d', 0.0)
    pos_y = mp.Value('d', 0.0)
    timestamp = mp.Value('i', 0)
    
    recognition_process = mp.Process(target=run_recognition_task, args=(frame_queue, pos_x, pos_y, timestamp))
    recognition_process.start()
    
    signaling = create_signaling(args)
    peer_connection = RTCPeerConnection()
    
    server_task = handle_answer(peer_connection, signaling, frame_queue, pos_x, pos_y, timestamp)
    main = asyncio.gather(server_task)
    
    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(main)
        recognition_process.join()
    except KeyboardInterrupt:
        pass
    finally:
        event_loop.run_until_complete(peer_connection.close())
        event_loop.run_until_complete(signaling.close())
        event_loop.close()
