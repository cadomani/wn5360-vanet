import datetime
from typing import ClassVar
from pydantic import BaseModel, validator, ValidationError, root_validator, Field
from ipaddress import IPv4Address
import json


class Coordinates(BaseModel):
    """ Defines coordinate format and significant """
    longitude: float
    latitude: float

    @validator('longitude')
    def check_longitude_values(cls, v):
        if v > 180 or v < -180:
            raise ValidationError("Longitude values must be between [-180, 180].")
        return v.__round__(5)

    @validator('latitude')
    def check_latitude_values(cls, v):
        if v > 90 or v < -90:
            raise ValidationError("Latitude values must be between [-90, 90].")
        return v.__round__(5)

    def __str__(self):
        return f"[{self.longitude}, {self.latitude}]"

    def __repr__(self):
        return f"[{self.longitude}, {self.latitude}]"


class Packet(BaseModel):
    """
    Valid Values:
        SequenceNumber:     0           -> 9999
        SourceAddress:      0.0.0.0     -> 255.255.255.255
        GPSPosition:        [-180, -90] -> [180, 90]
        Velocity:           0.00        -> 300.00
        Acceleration:       -15 m/s^2   -> 15 m/s^2
        BrakeControl:       0           -> 100
        GasThrottle:        0           -> 100
    """
    timestamp: float = None
    sequence_number: int
    source_address: IPv4Address
    gps_position: Coordinates
    velocity: float
    acceleration: float
    brake_control: float
    gas_throttle: float

    # VALIDATORS

    @validator("sequence_number")
    def check_valid_sequence(cls, v, values):
        if v < 0 or v > 9999:
            raise ValidationError("Packet sequences should be between 0 and 9999.")
        return v

    @validator("velocity")
    def check_velocity_range(cls, v):
        if v < 0 or v > 300:
            raise ValidationError("Velocity should be between 0 and 300 kph.")
        return v

    @validator("acceleration")
    def check_acceleration_range(cls, v):
        if v < -15 or v > 15:
            raise ValidationError("Acceleration should be between -15 and 15 m/s^2.")
        return v

    @validator("brake_control", "gas_throttle")
    def check_pedal_ranges(cls, v):
        if v < 0 or v > 100:
            raise ValidationError("Pedal values should be between 0 and 100.")
        return v

    # GENERATORS

    @staticmethod
    def _calculate_checksum(data: str):
        checksum = 0
        for c in data:
            checksum += ord(c)
        return str(checksum)

    @staticmethod
    def interpret_packet(data: bytes):
        values = bytes.decode(data, 'utf-8').split('\n')
        pkt_dict = {}
        for item in values:
            k, _, v = item.partition(": ")
            if k == "GPS":
                v = json.loads(v)
            pkt_dict[k.lower()] = v
        try:
            new_packet = Packet(
                sequence_number=int(pkt_dict['seq']),
                source_address=IPv4Address(pkt_dict['src']),
                gps_position=Coordinates(longitude=float(pkt_dict['gps'][0]), latitude=float(pkt_dict['gps'][1])),
                velocity=pkt_dict['vel'],
                acceleration=pkt_dict['acc'],
                brake_control=pkt_dict['brk'],
                gas_throttle=pkt_dict['gas'],
                timestamp=pkt_dict['clk']
            )
        except Exception as e:
            print(f"Corrupted packet: {str(e)}")
            return None
        return new_packet

    def get_packet(self) -> bytes:
        # Timestamp packet
        self.timestamp = datetime.datetime.utcnow().timestamp()

        # Recreate all packet values
        unprocessed_packet = \
f'''VANET-V2V
SEQ: {self.sequence_number}
SRC: {self.source_address}
CHK: $SENTINEL$
CLK: {self.timestamp}
GPS: {self.gps_position}
BRK: {self.brake_control}
GAS: {self.gas_throttle}
ACC: {self.acceleration}
VEL: {self.velocity}'''

        # Calculate checksum and insert
        cleartext_packet_data = unprocessed_packet.replace('$SENTINEL$', self._calculate_checksum(unprocessed_packet))

        # Encode packet
        encoded_packet_data = bytes(cleartext_packet_data, 'utf-8')
        return encoded_packet_data

    class Config:
        validate_assignment = True
