# Carlos Domani
# Undergrad but completed graduate requirement
# Extra Credit:
#   Flooding Protocol: Completed
#   Platoon Dynamic Behavior: Completed

from sys import argv
from urllib import request
from vanet.vehicle import Client, FleetVehicle, LeadVehicle


def get_external_address():
    # Gather source address of lead vehicle using external service (without using requests module or upnp)
    req = request.Request("https://checkip.amazonaws.com/")
    res = request.urlopen(req)
    return str(res.read().decode('utf-8')).strip('\n')


if __name__ == "__main__":
    """
    If vehicle is part of a fleet (params: fleet follower_addr port)
        main.py fleet XX.XX.XX.XX XXXX
    Otherwise (lead port) with as many ip addresses as there are vehicles
        main.py lead XX.XX.XX.XX XXXX
          
    Sample test:
        # Run fleet on remote machine and listen on port 9999
        python3 main.py fleet 10.10.10.10 9999
        
        # Run lead on remote machine and broadcast on port 9999
        python3 lead <REMOTE_IP_ADDRESS> 9999
    """
    vals = argv[1:]
    vehicle_names = ['X', 'Y', 'Z', 'EC']
    if vals[0] == "lead":
        clients = []
        for i in range(1, len(vals) - 1):
            # noinspection PyTypeChecker
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

        # Reorganize based on order and provide direction, similar to a doubly-linked list
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
        address_pair = (get_external_address(), int(vals[4]))
        fleet = FleetVehicle(vehicle_name=str(vals[1]), vehicle_address=address_pair, follower_address=vals[2], follower_name=vals[3], transmission_range=float(vals[5]))
    print("\nVANET Transmission Ended")
