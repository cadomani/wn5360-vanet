import random
from dataclasses import dataclass
from socket import socket, AF_INET, SOCK_DGRAM
from vanet.model.packet import Packet, PacketFields, Coordinates

MAX_VEL = 300
MAX_ACCEL = 30


@dataclass
class VehicleProperties:
    address: str
    make: str
    model: str
    plate: str
    weight: int


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
    source_address: str
    gps_position: Coordinates
    velocity: float
    acceleration: float
    brake_control: float
    gas_throttle: float


class VehicleSensor:
    def __init__(self, current_coordinates: Coordinates, end_coordinates: Coordinates, sample_rate: int):
        """ Generate instantaneous sensor data based on initial inputs and a sample rate in Hertz. """
        self.acceleration = random.uniform(0.0, MAX_ACCEL)
        self.velocity     = random.betavariate(2, 10) * MAX_VEL

    def _calculate(self):
        """ Use previous acceleration to calculate velocity and new instantaneous position """
        pass

    def update(self):
        pass


class Vehicle:
    def __init__(self, vehicle_properties: VehicleProperties, lead_address: str = None):
        # Define an AF_INET UDP socket for data transmission and reception
        self.socket = socket(AF_INET, SOCK_DGRAM)

        # Vehicle data
        self.data: SensorData

        # Unique vehicle parameters
        self.properties = vehicle_properties

        # Global flags
        self.instant_coordinates: Coordinates
        self.destination_reached = False
        self.polls = 0

        # Define lead or follower based on provided address
        self.lead_address = lead_address
        if lead_address:
            self._drive(sample_rate=10)
        else:
            self._follow()

    def _drive(self, *, sample_rate: int):
        # Generate driving data if lead vehicle
        sleep_rate = sample_rate ^ -1

        while not self.destination_reached:
            # End ride after 30 sensor updates
            if self.polls >= 30:
                self.destination_reached = True

    def _follow(self):
        # React to lead vehicle driving data if follower, generate data to send to subscribed vehicles
        pass
