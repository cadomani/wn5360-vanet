from sys import argv
from urllib import request
from vanet.vehicle import Client, FleetVehicle, LeadVehicle



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
          
    Sample test:
        # Run fleet on remote machine and listen on port 9999
        python3 main.py fleet 9999
        
        # Run lead on remote machine and broadcast on port 9999
        python3 lead <REMOTE_IP_ADDRESS> 9999
    """
    vals = argv[1:]
    vehicle_names = ['X', 'Y', 'Z', 'EC']
    if vals[0] == "lead":
        clients = []
        for i in range(1, len(vals) - 1):
            clients.append(
                Client(
                    name=vehicle_names[i],
                    address=str(vals[i]),
                    port=int(vals[-1]),
                    vehicle_ahead=None,
                    vehicle_behind=None,
                    order=i-1
                )
            )
        # Reorganize based on order
        for client in clients:
            if client.order == 0:
                # only behind
                client.vehicle_behind = clients[client.order + 1]
            elif client.order == len(clients) - 1:
                # only ahead
                client.vehicle_ahead = clients[client.order - 1]
            else:
                client.vehicle_ahead = clients[client.order - 1]
                client.vehicle_behind = clients[client.order + 1]
        lead = LeadVehicle(get_external_address(), clients)
    else:
        initialize_fleet(num_vehicles=1, port=int(vals[1]))
    print("\nVANET Transmission Ended")
