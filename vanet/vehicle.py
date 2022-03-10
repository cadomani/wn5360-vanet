import random
import datetime
from dataclasses import dataclass
from socket import socket, AF_INET, SOCK_DGRAM
from vanet.model.packet import Packet, PacketFields, Coordinates

MAX_TRAVEL_DELTA = 2.5      # Max number of coordinate points traveled in a single trip (variation)
MAX_VELOCITY     = 300      # Max velocity in Kilometers per hour, to facilitate equaltion calculations
MAX_ACCELERATION = 10       # Max acceleration in m/s^2, eases math calculations
SAMPLE_RATE      = 2        # Frequency of packet transmissions in Hertz


@dataclass
class SensorData:
    """
    Valid Values:
        SequenceNumber:     0           -> 50
        SourceAddress:      0.0.0.0     -> 255.255.255.255
        GPSPosition:        [-180, -90] -> [180, 90]
        Velocity:           0.00        -> 300.00
        Acceleration:       -30 m/s^2   -> 30 m/s^2
        BrakeControl:       0           -> 100
        GasThrottle:        0           -> 100
    """
    sequence_number: int
    source_address: tuple
    gps_position: Coordinates
    velocity: float
    acceleration: float
    brake_control: float
    gas_throttle: float


class VehicleSensor:
    def __init__(self, previous_moment: SensorData, instant_coordinates: Coordinates):
        """ Generate new instantaneous sensor data based on initial inputs. """
        # Can probably be deepcopied a different way, or we can mutate values directly
        # self.data = SensorData(
        #     sequence_number=previous_moment.sequence_number,
        #     source_address=previous_moment.source_address,
        #     gps_position=previous_moment.gps_position,
        #     velocity=previous_moment.velocity,
        #     acceleration=previous_moment.acceleration,
        #     brake_control=previous_moment.brake_control,
        #     gas_throttle=previous_moment.gas_throttle
        # )

        # Pass by reference?
        self.data = previous_moment
        self.instant_coordinates = instant_coordinates

        # Decide if inputs should change in this iteration
        should_interact = random.choices([True, False], [0.15, 0.97])
        if should_interact:
            self._pedal_change()

    def _pedal_change(self):
        # Brake and gas pedals determine acceleration, their values are mutually exclusive
        pedal_value = random.uniform(0, 100)
        pedal_choice = random.uniform(0, 20)
        if pedal_choice < 1:
            self.data.brake_control = -pedal_value
        else:
            self.data.gas_throttle = pedal_value

    def _determine_location(self):
        # instant = self.instant_coordinates
        pass

    def _calculate(self):
        """ Use previous acceleration to calculate velocity and new instantaneous position """
        pass

    def update(self):
        pass


class Vehicle:
    def __init__(self, initialization_data: SensorData, destination_coordinates: Coordinates, vehicle_type: str = "lead", lead_address: tuple = None,):
        # Define an AF_INET UDP socket for data transmission and reception
        self.socket = socket(AF_INET, SOCK_DGRAM)

        # Vehicle sensor data and packet instance
        self.data: SensorData = initialization_data
        self.packet_handler: Packet

        # Global flags
        self.instant_coordinates = self.data.gps_position
        self.destination_coordinates = destination_coordinates
        self.destination_reached = False
        self.polls = 0

        # Define lead or follower based on provided address
        self.lead_address = lead_address
        if vehicle_type == "lead":
            # self.packet_handler = Packet(
            #     fields=initialization_data,
            # )
            self._drive(sample_rate=10)
        else:
            self._follow()

    def _drive(self, *, sample_rate: int):
        # Generate driving data if lead vehicle
        sleep_rate = sample_rate ^ -1

        # Bind to address for listening
        self.socket.bind(self.lead_address)

        # Lead driver for n-cycles, start transmitting
        while not self.destination_reached:
            # For testing, only perform a certain number of updates before ending transmissions
            self.polls += 1

            # Await connection from client to generate new sensor values
            incoming_data, client_address = self.socket.recvfrom(40)
            print(str(incoming_data))

            # Generate new values to use as a packet that can be transmitted
            VehicleSensor(self.data, self.instant_coordinates)

            # Reply to client with new sensor data
            self.socket.sendto(b"40-bytes of data to send to client after", client_address)

            # End ride after 30 sensor updates
            if self.polls >= 30:
                self.destination_reached = True

    def _follow(self):
        # React to lead vehicle driving data if follower, generate data to send to subscribed vehicles
        num_pkts = 0
        while not num_pkts >= 30:
            # For testing, only perform a certain number of updates before ending transmissions
            num_pkts += 1

            # Send initial message to server
            self.socket.sendto(b"40-bytes of data to send to server after", self.lead_address)
            response_msg = self.socket.recvfrom(40)
            print(response_msg[0])
