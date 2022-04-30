from __future__ import annotations

import datetime
import random
import time
from socket import socket, AF_INET, SOCK_DGRAM
from typing import List, Tuple
from dataclasses import dataclass
from ipaddress import IPv4Address

from vanet.model.packet import Packet, Coordinates, Acknowledgement

MAX_TRAVEL_DELTA = 2.5      # Max number of coordinate points traveled in a single trip (variation)
MAX_VELOCITY     = 300      # Max velocity in Kilometers per hour, to facilitate equaltion calculations
MAX_ACCELERATION = 10       # Max acceleration in m/s^2, eases math calculations
SAMPLE_RATE      = 2        # Frequency of packet transmissions in Hertz


@dataclass
class Client:
    """ Representation of a client from which packets are sent and received. """
    name: str
    address: str
    port: int
    vehicle_ahead: Client
    vehicle_behind: Client
    order: int
    last_received: int = 0
    last_attempted: int = 1
    out_of_range: bool = False

    def get_address_pair(self) -> Tuple[str, int]:
        return self.address, self.port

    def get_simple_name(self) -> str:
        return self.name.split(" ")[-1]

    def __str__(self):
        return f"Fleet Vehicle {self.name}"

    def __eq__(self, other):
        return other == self.address


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
    def __init__(self, address: str, followers: List[Client]):
        super().__init__(vehicle_type="Lead", address=address)

        # Set socket to non-blocking to allow for sending without waiting for acknowledgement
        self.socket.settimeout(0.2)

        # Global flags
        self.destination_reached = False
        self.polls = 0
        self.followers = followers
        self.sequence = 1
        self.periodic_delay_ms = 200
        self.periodic_delay_s = self.periodic_delay_ms / 1000

        # Vehicle sensor data and packet instance
        self.sensor = VehicleSensor()
        self.packet = Packet(
            sequence_number=self.sequence,
            source_address=IPv4Address(address),
            destination_address=IPv4Address(address),
            source_name="Lead",
            destination_name="",
            gps_position=self.sensor.gps_instant,
            velocity=self.sensor.velocity,
            acceleration=self.sensor.acceleration,
            brake_control=self.sensor.brake_control,
            gas_throttle=self.sensor.gas_throttle,
            transmission_range=50.0
        )

        # Print parameters to console and back an initialized vehicle
        print(f"Coordinates:\n\tStart:\t{self.sensor.gps_initial}\n\tEnd:\t{self.sensor.gps_final}\n")

        self._drive(sample_rate=10)

    def _drive(self, *, sample_rate: int):
        # Log number of total acknowledgements
        total_acknowledgements = 0

        # Allow failures to direct leader only once in case the tail vehicle was busy processing other packets
        lead_tail_fails = False

        # Lead driver for n-cycles, start transmitting
        while not self.destination_reached:
            # Obtain new packet to show
            new_packet = self.packet.get_packet()
            packets_sent = 0
            acknowledgements_received = 0

            # Start broadcasting blindly to clients
            print("--------------")
            print(f"Broadcasted SEQ #{self.sequence} to client(s):")
            for follower in self.followers:
                # Skip follower if if 20 packets have been successfully sent to them
                if follower.last_received == 20:
                    continue

                # Log current attempt for this follower
                follower.last_attempted = follower.last_received + 1

                # Update destination address before sending
                self.packet.destination_address = IPv4Address(follower.address)
                self.packet.destination_name = follower.get_simple_name()
                self.packet.sequence_number = follower.last_attempted

                # Artificially add a 2ms delay to allow server program to process last packet and send a reply TODO: Could spend this time listening too
                time.sleep(0.002)

                # Send normally if not marked out of range
                print(f'\t{follower}')
                if not follower.out_of_range:
                    # Update address before sending
                    self.socket.sendto(self.packet.get_packet(), follower.get_address_pair())
                else:
                    # Find the first vehicle in the chain that we can tunnel through
                    forwarder = None
                    parent_vehicle = follower.vehicle_ahead
                    while forwarder is None:
                        # Assert that we're not trying to tunnel through and missed the first vehicle
                        if follower.order == 0 or parent_vehicle is None:
                            raise NotImplementedError("Shouldn't be finding the follower of the second vehicle...")

                        # Keep track of the current vehicle and find the first parent that is not out of bounds
                        print(f"\t\twill be forwarded by {parent_vehicle}")
                        if not parent_vehicle.out_of_range:
                            forwarder = parent_vehicle
                        parent_vehicle = parent_vehicle.vehicle_ahead

                    # Found the forwarder to tunnel through, now we can tunnel
                    self.socket.sendto(self.packet.get_packet(), forwarder.get_address_pair())
                packets_sent += 1
            print("Waiting 200ms before next retransmission.")

            # TODO: This shows a sample packet instead of all packets to avoid bloating screen, at the end replace it with all
            # print("\nDATA: \n\t" + bytes.decode(new_packet, 'utf-8').replace('\n', '\n\t'))
            print("\n")

            # Listen until timeout until all packages come in, unless there is a timeout
            timestamp_received = -1.0
            try:
                while packets_sent != acknowledgements_received:
                    # Receive 8 bytes from a single client
                    response_msg, server_address = self.socket.recvfrom(50)
                    acknowledgements_received += 1
                    incoming_acknowledgement = Acknowledgement().process_packet(data=response_msg)

                    # Verify server connection
                    try:
                        # Find client from packet address
                        client = self.followers[self.followers.index(incoming_acknowledgement.origin_address)]

                        # Reset failure flag for direct follower on retransmission
                        if lead_tail_fails and client.order == 0:
                            lead_tail_fails = False

                        # Update the last received packet sequence number for this client
                        client.last_received += 1
                        print(f"SEQ #{incoming_acknowledgement.sequence} ACK'ed by {incoming_acknowledgement.vehicle_name}", end=" ")
                        if client.address != incoming_acknowledgement.origin_address:
                            print(f"(forwarded by {client.name})")
                        else:
                            print("")
                    except ValueError:
                        raise NotImplementedError("\t[ERROR]\tClient was not found, is the IP address set correctly in the header?")

                    # Keep only the first timestamp as it is the one associated with retransmission
                    if timestamp_received == -1.0:
                        timestamp_received = datetime.datetime.utcnow().timestamp()
                    total_acknowledgements += 1
            except TimeoutError as e:
                # Find follower
                for follower in self.followers:
                    if follower.last_received != follower.last_attempted:
                        # If the follower order is for the next vehicle, end immediately for now TODO: simply try retransmission of new immediately (unstable connection)
                        if follower.order == 0:
                            print(f"Direct follower ({follower.name}) failed to acknowledge.")
                            if lead_tail_fails:
                                raise ValueError("Several fails detected for vehicle directly behind lead. Is there a transmission issue?")
                            print(f"\tRetry once more in case client was busy.")
                            lead_tail_fails = True
                            continue

                        # Mark client as one needing tunneling
                        print(f"{follower} never acknowledged SEQ #{follower.last_attempted}")
                        print(f"\t will attempt to tunnel through {self.followers[follower.order - 1]} next time")
                        follower.out_of_range = True

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
            if self.polls >= 25:
                self.destination_reached = True

            # Sleep for 2000 milliseconds
            transmission_delay = timestamp_received - self.packet.timestamp
            if transmission_delay < self.periodic_delay_ms and timestamp_received != -1:
                print(f"Initial ACK received {int(transmission_delay * 1000)}ms after broadcast.")
                print(f"Waiting an additional {self.periodic_delay_ms - int(transmission_delay * 1000)}ms to send next packet.")
                sleep_delay = self.periodic_delay_s - transmission_delay
                if sleep_delay > 0:
                    # Paused due to debugging, but should continue instead of crashing
                    time.sleep(sleep_delay)
            elif transmission_delay > self.periodic_delay_s:
                print(f"Acknowledgement received over 100ms after broadcast ({int(transmission_delay * 1000)}ms).\nSending next packet immediately.\n")
            print("--------------\n\n")


class FleetVehicle(Vehicle):
    def __init__(self, vehicle_name: str, address: tuple):
        super().__init__(vehicle_type="Fleet", address=address[0])
        # Bind to address for listening
        self.socket.bind(address)

        # Variables
        self.name = vehicle_name
        self.address = address[0]
        self.port = address[1]
        self.last_seq = 0
        self.lead_address_pair = ""
        self.last_seq_forwarded = 0

        # Temporarily set an arbitrary max dropoff range
        self.distance_away = 35.0
        if self.name == "Z":
            print("Setting distance for Z to 80m")
            self.distance_away = 80

        # Set to following mode
        self._follow()

    def _follow(self):
        # React to lead vehicle driving data if follower, generate data to send to subscribed vehicles
        num_pkts = 0
        while not num_pkts >= 25 and self.last_seq_forwarded != 20:
            # Await packet from client to generate new sensor values
            incoming_data, client_address = self.socket.recvfrom(300)

            # Capture lead address if this is the first run
            if not self.lead_address_pair:
                self.lead_address_pair = client_address

            # Attempt to parse incoming packet
            if len(incoming_data) < 50:
                # Assume this is an acknowledgement packet first if it's under a certain length
                incoming_packet = Acknowledgement().process_packet(data=incoming_data)

                # If processing does not fail, proceed to forward acknowledgement
                print(f"Forwarding ACK #{incoming_packet.sequence} from Fleet Vehicle {incoming_packet.vehicle_name} ({incoming_packet.origin_address}) to Lead {self.lead_address_pair[0]}")
                self.socket.sendto(incoming_data, self.lead_address_pair)

                # Set last sequence forwarded so we don't shut this vehicle down if it needs to continue to forward packets
                self.last_seq_forwarded = incoming_packet.sequence
                continue

            # Otherwise, try to process as a data packet
            incoming_packet = Packet.interpret_packet(incoming_data)

            # Process packet if it is not empty
            if incoming_packet:
                # If the packet address is the same as the sender (not being forwarded), it should not surpass the range boundary
                # print(client_address[0], incoming_packet.source_address)
                # print(incoming_packet.transmission_range, self.distance_away)
                print(f"Packet #{incoming_packet.sequence_number} received from {incoming_packet.source_name} ({incoming_packet.source_address})", end=" ")
                if client_address[0] == str(incoming_packet.source_address):
                    if incoming_packet.transmission_range < self.distance_away:
                        # Packet coming straight from source and exceeds range, drop it
                        self.lead_address_pair = None
                        print(f"Silently dropping packet from {incoming_packet.source_address} as it exceeds range.")
                        continue
                else:
                    # Different senders, so return packet to referer
                    print(f"(forwarded by {client_address[0]})", end="")

                # Notify receipt of packet and parse as a string
                packet_string = bytes.decode(incoming_data, 'utf-8').replace('\n', '\n\t')

                # Ensure that this packet was intended for us, if not, forward
                destination_address = str(incoming_packet.destination_address)
                if self.address == destination_address:
                    # Update last sequence from packet data
                    self.last_seq = incoming_packet.sequence_number

                    # Send acknowledgement
                    print(f"\nSending ACK #{incoming_packet.sequence_number} to {client_address}.")
                    self.socket.sendto(bytes(f"ACK {incoming_packet.sequence_number} {self.address} {self.name}", 'utf-8'), client_address)
                    num_pkts += 1

                    # Show data that was received
                    print(f"\t{packet_string}\n")
                else:
                    # Do not pass go, do not collect 200, immediately forward packet
                    print(f"\n\tForwarding packet to Fleet Vehicle {incoming_packet.destination_name} ({destination_address}:{self.port})...\n")
                    self.socket.sendto(incoming_data, (destination_address, self.port))
            else:
                print(f"Silently dropping packet from {incoming_packet.source_address} as it exceeds range.")
