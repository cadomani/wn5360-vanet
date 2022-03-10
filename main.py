from vanet.vehicle import Vehicle, SensorData, Coordinates, MAX_TRAVEL_DELTA, MAX_ACCELERATION, MAX_VELOCITY
import random
from sys import argv
from urllib import request


def get_external_address():
    # Gather source address of lead vehicle using external service (without using requests module or upnp)
    req = request.Request("https://checkip.amazonaws.com/")
    res = request.urlopen(req)
    return str(res.read().decode('utf-8')).strip('\n')


def initialize_vehicle(*, vehicle_sequence: int = 1, lead_addr: str):
    # Initialize vehicle to provide starting point for other vehicles, values updated after first packet received
    unset_coordinates = Coordinates(
        longitude=0,
        latitude=0
    )
    data = SensorData(
        sequence_number=vehicle_sequence,
        source_address=get_external_address(),
        gps_position=unset_coordinates,
        velocity=random.betavariate(3, 8) * MAX_VELOCITY,
        acceleration=0,
        brake_control=0,
        gas_throttle=0
    )
    print(f"VANET Fleet\nVehicle: Fleet\nLead Address: {lead_addr}\nCoordinates:\n\tStart:\tAwaiting Transmission\n\tEnd:\tAwaiting Transmission\n")
    return Vehicle(data, destination_coordinates=unset_coordinates, vehicle_type="fleet", lead_address=lead_addr)


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

    # Generate ending position that is nofurther away than max travel delta
    ending_position = Coordinates(
        (initial_position.longitude + delta_long) % (180 if initial_position.longitude > 0 else -180),
        (initial_position.latitude + delta_lat) % (90 if initial_position.latitude > 0 else -90)
    )

    # Get external address
    lead_addr = get_external_address()

    # Brake and gas pedals determine acceleration, their values are mutually exclusive
    pedal_choice = random.uniform(-100, 100)
    brake_pedal, gas_pedal, acceleration = (0, 0, 0)
    if pedal_choice < 0:
        brake_pedal = abs(pedal_choice)
        acceleration = MAX_ACCELERATION * (brake_pedal / 100)
    else:
        gas_pedal = pedal_choice
        acceleration = MAX_ACCELERATION * (gas_pedal / 100)

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

    # Print parameters to console and back an initialized vehicle
    print(f"VANET Fleet\nVehicle: Lead\nIP Address: {lead_addr}\nCoordinates:\n\tStart:\t{initial_position}\n\tEnd:\t{ending_position}\n")
    return Vehicle(data, destination_coordinates=ending_position, vehicle_type="lead", lead_address=lead_addr)


def initialize_fleet(*, num_vehicles: int = 1, lead_addr: str):
    """ Allows us to create n-number of vehicles that follow behind lead vehicle. """
    vehicles = []
    for i in range(0, num_vehicles):
        vehicles.append(
            initialize_vehicle(
                vehicle_sequence=(i + 1),
                lead_addr=(lead_addr if len(vehicles) == 0 else vehicles[i - 1].lead_address)
            )
        )
    return vehicles


if __name__ == "__main__":
    """
    If vehicle is part of a fleet (params: fleet num_vehicles lead_addr port)
        main.py fleet 1 XXX.XXX.XXX.XXX XXXX
    Otherwise (lead)
        main.py lead
    """
    vals = argv[1:]
    if vals[0] == "lead":
        initialize_lead()
    else:
        initialize_fleet(num_vehicles=int(vals[1]), lead_addr=vals[2])
    print("\nVANET Transmission Ended")
