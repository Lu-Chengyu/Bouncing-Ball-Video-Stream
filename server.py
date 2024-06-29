import numpy as np
import cv2
from av import VideoFrame
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.signaling import create_signaling
import math
import asyncio
import argparse

class BouncingBallVideoStreamTrack(VideoStreamTrack):
    """
    A video track that returns a frame with a bouncing ball.
    """

    def __init__(self):
        """
        Initialize the BouncingBallVideoStreamTrack.

        This constructor sets up the initial parameters for the video stream,
        including the dimensions of the video, the radius and initial position 
        of the ball, its color, and its movement speed and direction.
        """
        super().__init__()
        self.counter = 0
        self.height, self.width = 400, 800
        self.radius = 30

        # Random start point ensuring it doesn't overlap with the boundaries
        self.x = np.random.randint(self.radius, self.width - self.radius)
        self.y = np.random.randint(self.radius, self.height - self.radius)

        # White ball
        self.color = (255, 255, 255)

        # Move speed and direction
        self.speed = 20
        self.angle = np.random.uniform(0, 2 * np.pi)  # Random initial angle in radians
        self.position_history = {}

    async def recv(self):
        """
        Calculate the next frame.

        This method updates the ball's position and checks for collisions with the 
        boundaries of the video frame. It generates a new video frame with the updated 
        ball position and returns it.
        """
        pts, time_base = await self.next_timestamp()

        # Update position
        self.x += int(self.speed * math.cos(self.angle))
        self.y += int(self.speed * math.sin(self.angle))

        # Check for collisions and update angle
        if self.y >= self.height - self.radius or self.y <= self.radius:
            self.angle = -self.angle
        if self.x >= self.width - self.radius or self.x <= self.radius:
            self.angle = np.pi - self.angle

        # Create frame
        ball_frame = np.zeros((self.height, self.width, 3), dtype='uint8')
        cv2.circle(ball_frame, (self.x, self.y), self.radius, self.color, -1)
        frame = VideoFrame.from_ndarray(ball_frame, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        self.position_history[pts] = (self.x, self.y)

        return frame


async def handle_signaling_messages(peer_connection, signaling):
    """
    Handle signaling messages for the server side.

    Parameters:
    peer_connection (RTCPeerConnection): The peer connection.
    signaling (object): The signaling mechanism.
    """
    while True:
        message = await signaling.receive()
        if isinstance(message, RTCSessionDescription):
            await peer_connection.setRemoteDescription(message)
        elif isinstance(message, RTCIceCandidate):
            await peer_connection.addIceCandidate(message)
        else:
            break


async def server_side_handler(peer_connection, signaling):
    """
    Offer the video frames to the client.

    Parameters:
    peer_connection (RTCPeerConnection): The peer connection.
    signaling (object): The signaling mechanism.
    """
    ball_track = BouncingBallVideoStreamTrack()
    data_channel = peer_connection.createDataChannel('computation')

    @data_channel.on('message')
    def on_message(message):
        if isinstance(message, str) and message.startswith('Location'):
            message_values = message.strip().split(' ')
            predicted_x = float(message_values[1])
            predicted_y = float(message_values[2])
            timestamp = int(message_values[4])
            real_x, real_y = ball_track.position_history.get(timestamp, (None, None))
            position_error = (round(abs(predicted_x - real_x), 2), round(abs(predicted_y - real_y), 2))
            print(f'Determined Location: ({predicted_x}, {predicted_y}), Real Location: ({real_x}, {real_y}), Error: ({position_error[0]}, {position_error[1]})')
            response_message = f'result {message_values[4]} displayed'
            data_channel.send(response_message)

    # Send media track
    peer_connection.addTrack(ball_track)
    await peer_connection.setLocalDescription(await peer_connection.createOffer())
    await signaling.send(peer_connection.localDescription)
    await handle_signaling_messages(peer_connection, signaling)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Signaling parser')

    # Set default values for arguments, which are needed to set up TCP signaling
    parser.add_argument('--signaling', type=str, default='tcp-socket', help='Signaling mechanism')
    parser.add_argument('--signaling_host', type=str, default='127.0.0.1', help='Signaling host')
    parser.add_argument('--signaling_port', type=str, default='8080', help='Signaling port')

    args = parser.parse_args()

    # Create TCP socket signaling
    signaling_instance = create_signaling(args)
    # Create peer connection
    peer_connection_instance = RTCPeerConnection()

    server_task = server_side_handler(peer_connection_instance, signaling_instance)

    # Run event loop
    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(server_task)
    except KeyboardInterrupt:
        pass
    finally:
        event_loop.run_until_complete(peer_connection_instance.close())
        event_loop.run_until_complete(signaling_instance.close())
