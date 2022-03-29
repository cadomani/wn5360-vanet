import datetime
import random
import threading
import time
from socket import socket, AF_INET, SOCK_DGRAM
from typing import List

from vanet.model.packet import Packet, Coordinates
from ipaddress import IPv4Address

MAX_TRAVEL_DELTA = 2.5      # Max number of coordinate points traveled in a single trip (variation)
MAX_VELOCITY     = 300      # Max velocity in Kilometers per hour, to facilitate equaltion calculations
MAX_ACCELERATION = 10       # Max acceleration in m/s^2, eases math calculations
SAMPLE_RATE      = 2        # Frequency of packet transmissions in Hertz


class VehicleSensor:
    """Valid Values:
        SequenceNumber:     0           -> 50
        SourceAddress:      0.0.0.0     -> 255.255.255.255
        GPSPosition:        [-180, -90] -> [180, 90]
        Velocity:           0.00        -> 300.00
        Acceleration:       -30 m/s^2   -> 30 m/s^2
        BrakeControl:       0           -> 100
        GasThrottle:        0           -> 100
    """
    def __init__(self):
        # Generate fleet starting coordinates
        self.gps_initial = Coordinates(
            longitude=random.uniform(-180, 180),
            latitude=random.uniform(-90, 90)
        )

        # Create a random value within max travel delta
        delta_long, delta_lat = (
            random.uniform(-MAX_TRAVEL_DELTA, MAX_TRAVEL_DELTA),
            random.uniform(-MAX_TRAVEL_DELTA, MAX_TRAVEL_DELTA)
        )

        # Generate ending position that is nofurther away than max travel delta
        self.gps_final = Coordinates(
            longitude=(self.gps_initial.longitude + delta_long) % (180 if self.gps_initial.longitude > 0 else -180),
            latitude=(self.gps_initial.latitude + delta_lat) % (90 if self.gps_initial.latitude > 0 else -90)
        )

        # Brake and gas pedals determine acceleration, their values are mutually exclusive
        pedal_choice = random.uniform(-100, 100)
        self.brake_control, self.gas_throttle, self.acceleration = (0, 0, 0)
        if pedal_choice < 0:
            self.brake_control = abs(pedal_choice)
            self.acceleration = MAX_ACCELERATION * (self.brake_control / 100)
        else:
            self.gas_throttle = pedal_choice
            self.acceleration = MAX_ACCELERATION * (self.gas_throttle / 100)

        # Generate a random starting velocity from a tightened statistical curve
        self.velocity = random.betavariate(3, 8) * MAX_VELOCITY

        # Copy instant gps location explicitly to avoid reference mutation
        self.gps_instant = Coordinates(
            longitude=self.gps_initial.longitude,
            latitude=self.gps_initial.latitude
        )

    def _pedal_change(self):
        # Decide if inputs should change in this iteration
        should_interact = random.choices([True, False], [0.15, 0.97])
        if should_interact:
            # Brake and gas pedals determine acceleration, their values are mutually exclusive
            pedal_value = random.uniform(0, 100)
            pedal_choice = random.uniform(0, 20)
            if pedal_choice < 1:
                self.brake_control = pedal_value
                self.gas_throttle = 0
            else:
                self.gas_throttle = pedal_value
                self.brake_control = 0

    def _determine_location(self):
        pass

    def _calculate(self):
        """ Use previous acceleration to calculate velocity and new instantaneous position """
        pass

    def update(self):
        self._pedal_change()


class Vehicle:
    def __init__(self, *, vehicle_type: str, address: str):
        # Define an AF_INET UDP socket for data transmission and reception
        self.socket = socket(AF_INET, SOCK_DGRAM)

        # Vehicle sensor data and packet instance
        self.data: VehicleSensor
        self.packet: Packet

        # Print parameters to console for a general vehicle until we specialize
        print(f"VANET Fleet\nVehicle: {vehicle_type}\nIP Address: {address}\n")


class LeadVehicle(Vehicle):
    def __init__(self, address: str, followers: List[tuple]):
        super().__init__(vehicle_type="Lead", address=address)

        # Set socket to non-blocking to allow for sending without waiting for acknowledgement
        self.socket.settimeout(1)

        # Global flags
        self.destination_reached = False
        self.polls = 0
        self.followers = followers
        self.sequence = 1

        # Vehicle sensor data and packet instance
        self.sensor = VehicleSensor()
        self.packet = Packet(
            sequence_number=self.sequence,
            source_address=IPv4Address(address),
            gps_position=self.sensor.gps_instant,
            velocity=self.sensor.velocity,
            acceleration=self.sensor.acceleration,
            brake_control=self.sensor.brake_control,
            gas_throttle=self.sensor.gas_throttle
        )

        # Print parameters to console and back an initialized vehicle
        print(f"Coordinates:\n\tStart:\t{self.sensor.gps_initial}\n\tEnd:\t{self.sensor.gps_final}\n")

        self._drive(sample_rate=10)

    def _drive(self, *, sample_rate: int):
        # Generate driving data if lead vehicle
        sleep_rate = sample_rate ^ -1

        # Assume only a single fleet vehicle for now
        follower = self.followers[0]
        acknowledgements = 0

        # Lead driver for n-cycles, start transmitting
        while not self.destination_reached:
            # Obtain new packet
            new_packet = self.packet.get_packet()

            # Start broadcasting blindly to clients
            print(f"Broadcasted Sequence #{self.sequence}. Waiting 100ms before next retransmission.")
            print(f"DATA: {bytes.decode(new_packet, 'utf-8')}")
            self.socket.sendto(new_packet, follower)
            response_msg, server_address = self.socket.recvfrom(8)
            decoded_data = bytes.decode(response_msg, 'utf-8')

            # Verify server connection
            timestamp_received = -1.0
            if "ACK" in decoded_data:
                print(f"Sequence #{decoded_data.split(' ')[1]} ACK'ed by {server_address[0]}")
                timestamp_received = datetime.datetime.utcnow().timestamp()
                acknowledgements += 1

            # For testing, only perform a certain number of updates before ending transmissions
            self.polls += 1
            self.sequence += 1

            # Generate new values to use as a packet that can be transmitted
            self.sensor.update()
            self.packet.sequence_number = self.sequence
            self.packet.acceleration = self.sensor.acceleration
            self.packet.velocity = self.sensor.velocity
            self.packet.gas_throttle = self.sensor.gas_throttle
            self.packet.brake_control = self.sensor.brake_control

            # End ride after 30 sensor updates
            if self.polls >= 30:
                self.destination_reached = True

            # Sleep for 100 milliseconds
            transmission_delay = timestamp_received - self.packet.timestamp
            if transmission_delay < 0.1 and timestamp_received != -1:
                print(f"Acknowledgment received {int(transmission_delay * 1000)}ms after broadcast. Waiting an additional {100 - int(transmission_delay * 1000)}ms to send another transmission.\n")
                time.sleep(0.1 - transmission_delay)
            elif transmission_delay > 0.1:
                print(f"Acknowledgement received over 100ms after broadcast ({int(transmission_delay * 1000)}ms). Sending next packet immediately.\n")


class FleetVehicle(Vehicle):
    def __init__(self, address: tuple):
        super().__init__(vehicle_type="Fleet", address=address[0])

        # Bind to address for listening
        self.socket.bind(address)

        # Set to following mode
        self._follow()

    def _follow(self):
        # React to lead vehicle driving data if follower, generate data to send to subscribed vehicles
        num_pkts = 0
        while not num_pkts >= 30:
            # Await packet from client to generate new sensor values
            incoming_data, client_address = self.socket.recvfrom(300)

            # Attempt to parse incoming packet
            new_packet = Packet.interpret_packet(incoming_data)
            if new_packet:
                print(f"Packet #{new_packet.sequence_number} received from {client_address[0]}. Sending ACK #{new_packet.sequence_number}.")
                print(f"{new_packet.dict()}\n")
                self.socket.sendto(bytes(f"ACK {new_packet.sequence_number}", 'utf-8'), client_address)
                num_pkts += 1
