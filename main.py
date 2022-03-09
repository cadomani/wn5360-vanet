from vanet.vehicle import Vehicle, SensorData, Coordinates
import random
from sys import argv
from urllib import request
import socket

MAX_TRAVEL_DELTA = 2.5      # Max number of coordinate points traveled in a single trip (variation)
MAX_VELOCITY     = 300      # Max velocity in Kilometers per hour, to facilitate equaltion calculations
MAX_ACCELERATION = 30       # Max acceleration in m/s^2, eases math calculations


def initialize_vehicle(*, vehicle_sequence: int = 1, lead_addr: str):
    # Initialize vehicle to provide starting point for other vehicles, coordinates updated after first packet received
    data = SensorData(
        sequence_number=vehicle_sequence,
        source_address=lead_addr,
        gps_position=Coordinates(
            longitude=0,
            latitude=0
        ),
        velocity=random.betavariate(3, 8) * MAX_VELOCITY,
        acceleration=0,
        brake_control=0,
        gas_throttle=0
    )


def initialize_lead():
    # Generate fleet starting coordinates
    initial_position = Coordinates(
        random.uniform(-180, 180),
        random.uniform(-90, 90)
    )

    # Create a random value within max travel delta
    delta_long, delta_lat = (
        random.uniform(-MAX_TRAVEL_DELTA, MAX_TRAVEL_DELTA),
        random.uniform(-MAX_TRAVEL_DELTA, MAX_TRAVEL_DELTA)
    )

    # Generate ending position that is nofurther away than max travel delta, TODO: wrap values around
    ending_position = Coordinates(
        (initial_position.longitude + delta_long),  # % 180,
        (initial_position.latitude + delta_lat)  # % 90
    )

    # Gather source address of lead vehicle using external service (without using requests module or upnp)
    req = request.Request("https://checkip.amazonaws.com/")
    res = request.urlopen(req)
    lead_addr = str(res.read().decode('utf-8')).strip('\n')

    # Brake and gas pedals determine acceleration, their values are mutually exclusive
    pedal_choice = random.uniform(-100, 100)
    brake_pedal, gas_pedal, acceleration = (0, 0, 0)
    if pedal_choice < 0:
        brake_pedal = -pedal_choice
        acceleration = -(abs(random.normalvariate(0, 9)) % MAX_ACCELERATION)
    else:
        brake_pedal = pedal_choice
        acceleration = abs(random.normalvariate(0, 9)) % MAX_ACCELERATION

    # Create sensor data object with values above
    data = SensorData(
        sequence_number=0,
        source_address=lead_addr,
        gps_position=initial_position,
        velocity=random.betavariate(3, 8) * MAX_VELOCITY,
        acceleration=acceleration,
        brake_control=brake_pedal,
        gas_throttle=gas_pedal
    )

    # Print parameters to console
    print(f"VANET Fleet\nVehicle: Lead\nIP Address: {lead_addr}\nCoordinates:\n\tStart:\t{initial_position}\n\tEnd:\t{ending_position}\n")

    # lead = Vehicle(vehicle_properties=None)


def initialize_fleet(*, num_vehicles: int = 1, lead_addr: str):
    """ Allows us to create n-number of vehicles that follow behind lead vehicle. """

    vehicles = []
    for i in range(0, num_vehicles):
        vehicles.append(
            initialize_vehicle(
                vehicle_sequence=(i + 1),
                lead_addr=lead_addr
            )
        )


if __name__ == "__main__":
    """
    If vehicle is part of a fleet (params: fleet num_vehicles lead_addr)
        main.py fleet 1 XXX.XXX.XXX.XXX
    Otherwise (lead)
        main.py lead
    """
    vals = argv[1:]
    if vals[0] == "lead":
        initialize_lead()
    else:
        initialize_fleet(num_vehicles=1, lead_addr=vals[1])