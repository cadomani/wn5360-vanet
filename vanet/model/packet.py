from socket import socket, AF_INET, SOCK_DGRAM
from dataclasses import dataclass
from typing import NamedTuple


class Coordinates(NamedTuple):
    longitude: float
    latitude: float


@dataclass
class PacketFields:
    """
    Valid Values:
        SequenceNumber:     0           -> 32768
        SourceAddress:      0.0.0.0     -> 255.255.255.255
        GPSPosition:        [-180, -90] -> [180, 90]
        Velocity:           0.00        -> 300.00
        Acceleration:       -30 m/s^2   -> 30 m/s^2
        BrakeControl:       0           -> 100
        GasThrottle:        0           -> 100
    """
    SequenceNumber: int
    SourceAddress: str
    GPSPosition: Coordinates
    Velocity: float
    Acceleration: float
    BrakeControl: float
    GasThrottle: float


class Packet:
    def __init__(self, fields: PacketFields):
        self.fields = fields
        self._validate_fields()

        # Define an AF_INET UDP socket for data transmission
        self.socket = socket(AF_INET, SOCK_DGRAM)

    def _validate_fields(self):
        vals = list(self.fields.__dict__.items())
        for k, v in vals:
            if v is None or v == "":
                raise ValueError("All packet fields must have non-null values.")
            elif k == "GPSPosition":
                if v.latitude is None or v.longitude is None:
                    raise ValueError("Latitude values must be between [-90, 90] and longitude values must be between [-180, 180].")
                elif v.latitude < -90 or v.latitude > 90:
                    raise ValueError("Latitude values must be between [-90, 90].")
                elif v.longitude < -180 or v.longitude > 180:
                    raise ValueError("Longitude values must be between [-180, 180].")
            else:
                # No invalid values, now validate ranges
                if k == "SequenceNumber" and (v < 0 or v > 32768):
                    raise ValueError("SequenceNumber values must be ")
                elif k == "SourceAddress":
                    oc1, oc2, oc3, oc4 = str(v).split(".", maxsplit=4)
                    if oc1 < 0 or oc2 < 0 or oc3 < 0 or oc4 < 0 or \
                        oc1 > 255 or oc2 > 255 or oc3 > 255 or oc4 > 255 or \
                            v == "0.0.0.0" or v == "255.255.255.255":
                        raise ValueError("SourceAddress must be a valid IP address.")
                elif k == "Velocity" and (v < 0 or v > 300):
                    raise ValueError("Velocity values must be between 0 and 300.")
                elif k == "Acceleration" and (v < -30 or v > 30):
                    raise ValueError("Acceleration values must be between -30 and 30.")
                elif (k == "BrakeControl" or k == "GasThrottle") and (v < 0 or v > 100):
                    raise ValueError(f"{k} values must be between 0 and 100.")

    def get_packet(self):
        pass
