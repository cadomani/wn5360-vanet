from sys import argv
from urllib import request
from vanet.vehicle import FleetVehicle, LeadVehicle


def get_external_address():
    # Gather source address of lead vehicle using external service (without using requests module or upnp)
    req = request.Request("https://checkip.amazonaws.com/")
    res = request.urlopen(req)
    return str(res.read().decode('utf-8')).strip('\n')


def initialize_fleet(*, num_vehicles: int = 1, port: int):
    """ Allows us to create n-number of vehicles that follow behind lead vehicle. """
    vehicles = []
    for i in range(0, num_vehicles):
        vehicles.append(
            FleetVehicle((get_external_address(), port))
        )
    return vehicles


if __name__ == "__main__":
    """
    If vehicle is part of a fleet (params: fleet num_vehicles lead_addr port)
        main.py fleet XXXX
    Otherwise (lead port)
        main.py lead XX.XX.XX.XX XXXX
    """
    vals = argv[1:]
    if vals[0] == "lead":
        lead = LeadVehicle(get_external_address(), [(str(vals[1]), int(vals[2]))])
    else:
        initialize_fleet(num_vehicles=1, port=int(vals[1]))
    print("\nVANET Transmission Ended")
