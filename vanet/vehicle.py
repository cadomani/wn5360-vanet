from __future__ import annotations

import datetime
import math
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
    AIR_RESISTANCE_AND_FRICTION_FORCE = 10  # Combined countering forces in m/s^2
    BRAKING_FORCE_MULTIPLIER = 20  # Combined countering force constant from braking
    ACCELERATION_FORCE_MULTIPLIER = 15  # Combined contributing force constant from acceleration

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

            # Override if velocity is approaching outside bounds
            if self.velocity > 95:
                pedal_choice = 0
            elif self.velocity < 30:
                pedal_choice = 1

            # Randomly choose pedal to update where most updates are for acceleration
            if pedal_choice < 1:
                self.brake_control = pedal_value
                self.gas_throttle = 0

                # Update velocity from pedals and multiplier
                self.velocity -= VehicleSensor.BRAKING_FORCE_MULTIPLIER * (pedal_value / 100)
            else:
                self.gas_throttle = pedal_value
                self.brake_control = 0

                # Update velocity from pedals and multiplier
                self.velocity += VehicleSensor.ACCELERATION_FORCE_MULTIPLIER * (pedal_value / 100)

    def _determine_location(self):
        pass

    def _calculate(self):
        """ Use previous acceleration to calculate velocity and new instantaneous position """
        pass

    def update(self, time_delta: float, incoming_velocity: float = 0, incoming_acceleration: float = 0):
        # Gather a new velocity first if lead vehicle
        if incoming_velocity == 0:
            self._pedal_change()
        else:
            # Override velocity and acceleration if not a follower
            # Velocity is v_current + a_instantaneous * time_delta
            self.velocity += (self.velocity + (incoming_acceleration * time_delta))
            self.acceleration = (self.velocity - incoming_velocity) / time_delta
            self.gas_throttle = 0 if self.acceleration <= 0 else (100 * ((15 - self.acceleration) / 15))
            self.brake_control = 0 if self.acceleration >= 0 else (100 * ((15 - (1 / self.acceleration)) / 15))

        # Move ahead by calculating naive velocity "speed" times the time taken
        moved_ahead_pos = incoming_velocity * time_delta

        # Decompose identical vectors to simulate a 45 degree travel path northwest
        comp_decomp_x = math.sqrt((moved_ahead_pos ** 2 + moved_ahead_pos ** 2)) / 1000
        comp_decomp_y = math.sqrt((moved_ahead_pos ** 2 + moved_ahead_pos ** 2)) / 1000

        # Update coordinates using decomposition values
        self.gps_instant = Coordinates(
            longitude=self.gps_instant.longitude + comp_decomp_x,
            latitude=self.gps_instant.latitude + comp_decomp_y
        )


class Vehicle:
    def __init__(self, vehicle_type: str, vehicle_name: str, vehicle_address: tuple, follower_address: str, follower_name: str, transmission_range: float):
        # Define an AF_INET UDP socket for data transmission and reception
        self.socket = socket(AF_INET, SOCK_DGRAM)

        # Global fields
        self.name = vehicle_name
        self.address_pair = vehicle_address
        self.address, self.port = self.address_pair
        self.follower_name = follower_name if follower_name != "-" else self.name
        self.follower_address = follower_address if follower_address != "-" else self.address
        self.transmission_range = transmission_range

        # Vehicle sensor data and packet instance
        self.sensor = VehicleSensor()
        self.packet = Packet(
            sequence_number=0,
            source_address=IPv4Address(self.address),
            destination_address=IPv4Address(self.follower_address),
            source_name=self.name,
            destination_name=self.follower_name,
            gps_position=self.sensor.gps_instant,
            velocity=self.sensor.velocity,
            acceleration=self.sensor.acceleration,
            brake_control=self.sensor.brake_control,
            gas_throttle=self.sensor.gas_throttle,
            transmission_range=self.transmission_range
        )

        # Print parameters to console for a general vehicle until we specialize
        print("Initiating" if vehicle_type == "Lead" else "Joining", end=" ")
        print(f"VANET Fleet\nThis Vehicle:\t{self.name} ({self.address})")


class LeadVehicle(Vehicle):
    def __init__(self, vehicle_address: str, followers: List[Client], transmission_range: float = 90.0, transmission_delay_ms: float = 500):
        # Initialize a standard vehicle with sensors and packet object
        super().__init__(
            vehicle_type="Lead",
            vehicle_name="Lead",
            vehicle_address=(vehicle_address, 9885),
            follower_name=followers[0].name,
            follower_address=followers[0].address,
            transmission_range=transmission_range
        )

        # Set socket to non-blocking to allow for sending without waiting for acknowledgement
        self.socket.settimeout(transmission_delay_ms / 1000)

        # Global flags
        self.polls = 0
        self.sequence = 1
        self.followers = followers
        self.lead_fleet_failure = False
        self.destination_reached = False
        self.periodic_delay_ms = transmission_delay_ms

        # Print parameters to console and back an initialized vehicle
        print(f"Coordinates:\n\tStart:\t{self.sensor.gps_initial}\n\tEnd:\t{self.sensor.gps_final}\n")

        # Begin driving
        self._drive()

    def _drive(self):
        # Log number of total acknowledgements
        total_acknowledgements = 0

        # Lead driver for n-cycles, start transmitting
        while not self.destination_reached:
            # Obtain new packet to show
            new_packet = self.packet.get_packet()
            packets_sent = 0
            acknowledgements_received = 0

            # End immediately if all followers submitted 20 packets
            for follower in self.followers:
                if follower.last_received != 20:
                    break
            else:
                # If all of them were 20, then we should reach our destination
                self.destination_reached = True
                break

            # Start broadcasting blindly to clients
            print("--------------")
            print(f"Broadcasted SEQ #{self.sequence} to client(s):")
            for follower in self.followers:
                # Skip follower if 20 packets have been successfully sent to them
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
                            raise ValueError("The leading fleet vehicle shouldn't need tunneling.")

                        # Keep track of the current vehicle and find the first parent that is not out of bounds
                        print(f"\t └ will be forwarded by {parent_vehicle}")
                        if not parent_vehicle.out_of_range:
                            forwarder = parent_vehicle
                        parent_vehicle = parent_vehicle.vehicle_ahead

                    # Found the forwarder to tunnel through, now we can tunnel
                    self.socket.sendto(self.packet.get_packet(), forwarder.get_address_pair())
                packets_sent += 1
            # print("Waiting 200ms before next retransmission.")

            # TODO: This shows a sample packet instead of all packets to avoid bloating screen, at the end replace it with all
            # print("\nDATA: \n\t" + bytes.decode(new_packet, 'utf-8').replace('\n', '\n\t'))
            print("")

            # Listen until timeout until all packages come in, unless there is a timeout
            timestamp_received = -1.0
            try:
                print(f"Awaiting acknowledgement packages during {self.periodic_delay_ms}ms wait.")
                while packets_sent != acknowledgements_received:
                    # Receive up to 50 bytes from a single client
                    response_msg, server_address = self.socket.recvfrom(50)
                    acknowledgements_received += 1
                    incoming_acknowledgement = Acknowledgement().process_packet(data=response_msg)

                    # Verify server connection
                    try:
                        # Find client from packet address
                        client = self.followers[self.followers.index(incoming_acknowledgement.origin_address)]
                        forwarder = self.followers[self.followers.index(server_address[0])]

                        # Reset failure flag for direct follower on retransmission
                        if self.lead_fleet_failure and client.order == 0:
                            self.lead_fleet_failure = False

                        # Update the last received packet sequence number for this client
                        client.last_received += 1
                        print(f"\t└ SEQ #{incoming_acknowledgement.sequence} ACK'ed by {incoming_acknowledgement.vehicle_name}", end=" ")
                        print(f"(forwarded by {forwarder})" if server_address[0] != incoming_acknowledgement.origin_address else " ")
                    except ValueError:
                        raise NotImplementedError("\n\t[ ERROR ] - Client was not found, is the IP address set correctly in the header?\n")

                    # Keep only the first timestamp as it is the one associated with retransmission
                    if timestamp_received == -1.0:
                        timestamp_received = datetime.datetime.utcnow().timestamp()
                    total_acknowledgements += 1
            except TimeoutError:
                # Find failing followers from list of followers
                for follower in self.followers:
                    # Filter by followers where the last received package is not the last one that was attempted
                    if follower.last_received != follower.last_attempted:
                        # If the follower order is for the leading fleet vehicle, set a flag to allow for retransmission once more
                        if follower.order == 0:
                            # End program if this is the second run with an issue on le leading fleet vehicle
                            if self.lead_fleet_failure:
                                raise ValueError("\n\t[ ERROR ] Several fails detected for vehicle directly behind lead. Is there a transmission issue?\n")
                            self.lead_fleet_failure = True

                            # Notify of acknowledgement failure and expect
                            print(f"[ WARN ] Lead fleet vehicle ({follower.name}) failed to acknowledge.")
                            print(f"\t└ retry once more in case client was busy.")
                            continue

                        # Mark client as one needing tunneling
                        print(f"{follower} never acknowledged SEQ #{follower.last_attempted}")
                        print(f"\t└ tunnel through {self.followers[follower.order - 1]} next time")
                        follower.out_of_range = True

            # Mark a sensor poll even if transmission was unsuccessful to prevent infinite loops
            self.polls += 1
            self.sequence += 1

            # Update sensor by providing a time delta of 200 ms
            self.sensor.update(time_delta=0.2)

            # Generate new values to use as a packet that can be transmitted
            self.packet.acceleration = self.sensor.acceleration
            self.packet.velocity = self.sensor.velocity
            self.packet.gas_throttle = self.sensor.gas_throttle
            self.packet.brake_control = self.sensor.brake_control
            self.packet.gps_position = self.sensor.gps_instant

            # End ride after 30 sensor updates
            if self.polls >= 25:
                self.destination_reached = True

            # Sleep for the remaining amount of the transmission delay milliseconds
            transmission_delay = timestamp_received - self.packet.timestamp
            if transmission_delay < self.periodic_delay_ms and timestamp_received != -1:
                # Only log initial ACK received, not all of them
                print(f"Initial ACK received {int(transmission_delay * 1000)}ms after broadcast.")
                print(f"Waiting an additional {self.periodic_delay_ms - int(transmission_delay * 1000)}ms to send next packet.")

                # TODO: DEBUG - Paused due to debugging, but should continue instead of crashing
                sleep_delay = (self.periodic_delay_ms / 1000) - transmission_delay
                if sleep_delay > 0:
                    time.sleep(sleep_delay)
            elif transmission_delay > (self.periodic_delay_ms / 1000):
                print(f"Acknowledgement received over 100ms after broadcast ({int(transmission_delay * 1000)}ms).\nSending next packet immediately.\n")
            print("--------------\n\n")


class FleetVehicle(Vehicle):
    def __init__(self, vehicle_name: str, following_address: str, following_name: str, vehicle_address: tuple, follower_address: str, follower_name: str, transmission_range: float):
        # Initialize a fleet vehicle type
        super().__init__(
            vehicle_type="Fleet",
            vehicle_name=vehicle_name,
            vehicle_address=vehicle_address,
            follower_address=follower_address,
            follower_name=follower_name,
            transmission_range=transmission_range
        )

        # Bind to address for listening
        self.socket.bind(self.address_pair)

        # Transmission variables
        self.last_seq = 0
        self.last_seq_forwarded = 0
        self.last_seq_sent = 1
        self.last_seq_received = 0
        self.last_pkt_recv_time = None
        self.following_address = (following_address, self.port) if following_name != "Lead" else None
        self.following_name = following_name

        # EXTRA CREDIT
        self.flooding_protocol_container = {}

        # Print out following vehicles
        if self.following_name != "Lead":
            print(f"Vehicle ahead:\t{self.following_name} ({self.following_address[0]})")
        if self.follower_name != self.name:
            print(f"Rear Vehicle:\t {self.follower_name} ({self.follower_address})")
        else:
            print("Last vehicle in fleet.")

        # Use transmission range differently here
        print(f"Vehicle is {self.transmission_range}m away from lead vehicle\n")

        # Set to following mode
        self._follow()

    def _follow(self):
        # React to lead vehicle driving data if follower, generate data to send to subscribed vehicles
        num_pkts = 0
        while not num_pkts >= 25 and self.last_seq_forwarded != 21:
            # Await packet from client to generate new sensor values
            incoming_data, client_address = self.socket.recvfrom(300)

            # Assume this is an acknowledgement packet first if it's under a certain length, and do not process ACK requests until we know what the lead address is
            if len(incoming_data) < 50:
                # Attempt to parse incoming packet
                incoming_packet = Acknowledgement().process_packet(data=incoming_data)

                # Dynamically set the IP address of the vehicle at the front of the line
                if not self.following_address:
                    self.following_address = client_address

                # See if the packet belongs to us and we can keep it instead of forwarding it
                if incoming_packet.destination_address == self.address:
                    print(f"Received ACK from {incoming_packet.vehicle_name}.")
                    print(f"\t└ SEQ #{incoming_packet.sequence}")
                    self.last_seq_sent += 1
                else:
                    print(f"Forwarding ACK #{incoming_packet.sequence}\n\t Fleet Vehicle {incoming_packet.vehicle_name} -> {self.following_name}")
                    if self.following_address is None:
                        print("Skipping because we cannot find a following address...")
                    self.socket.sendto(incoming_data, self.following_address)

                    # Set last sequence forwarded so we don't shut this vehicle down if it needs to continue to forward packets
                    self.last_seq_forwarded = incoming_packet.sequence

                    # Check flooding protocol container to see if we logged 21 packets
                    if self.flooding_protocol_container.get('DONE'):
                        break
                # Do not continue parsing, start listening for the next packet
                continue

            # Otherwise, try to process as a data packet
            incoming_packet = Packet.interpret_packet(incoming_data)

            # Process packet if it is not empty
            if incoming_packet:
                # If the packet address is the same as the sender (not being forwarded), it should not surpass the range boundary {' forwarded by' if client_address[0] != self.lead_address_pair[0] else ''}
                if client_address[0] == str(incoming_packet.source_address):
                    if incoming_packet.transmission_range < self.transmission_range and client_address[0] != self.following_address[0]:
                        # Packet coming straight from source and exceeds range, drop it
                        print(f"Silently dropping packet from {incoming_packet.source_name} as it exceeds range.")
                        continue
                    print(f"Packet #{incoming_packet.sequence_number} received from {incoming_packet.source_name}")
                else:
                    # Different senders, so return packet to referer
                    print(f"Packet #{incoming_packet.sequence_number} received from {incoming_packet.source_name}")
                    print(f"\t└ forwarded by ({self.following_name})")

                # Notify receipt of packet and parse as a string
                packet_string = bytes.decode(incoming_data, 'utf-8').replace('\n', '\n\t')

                # Ensure that this packet was intended for us, if not, forward
                destination_address = str(incoming_packet.destination_address)
                if self.address == destination_address:
                    # Update last sequence from packet data
                    self.last_pkt_recv_time = datetime.datetime.utcnow().timestamp()

                    # Show data that was received
                    print(f"Packet Data:\n\t{packet_string}\n")

                    # Send acknowledgement
                    # print("RECEIVED A PACKET THAT MATCHES OUR ADDRESS")
                    # print(incoming_packet)
                    print(f"\nSending ACK #{incoming_packet.sequence_number} to {self.following_name}{' intended for Lead' if incoming_packet.source_name != self.following_name else ''}.")
                    self.socket.sendto(bytes(f"ACK {incoming_packet.sequence_number} {self.address} {str(incoming_packet.source_address)} {self.name}", 'utf-8'), client_address)
                    if not self.following_address:
                        self.following_address = client_address

                    # Copy, but skip updates until we have values from lead vehicle
                    if incoming_packet.source_name != "Lead":
                        self.last_seq_received += 1
                        continue
                    else:
                        self.last_seq = incoming_packet.sequence_number
                    num_pkts += 1

                    # Update vehicle data based on location and current speed
                    time_delta = datetime.datetime.now().timestamp() - self.last_pkt_recv_time
                    self.sensor.update(
                        time_delta=time_delta,
                        incoming_velocity=incoming_packet.velocity,
                        incoming_acceleration=incoming_packet.acceleration
                    )

                    print("Updating navigation based on last transmission...")
                    print(f"\tMoved ahead {incoming_packet.velocity * time_delta} meters")
                    print(f"\tNew position: {self.sensor.gps_instant}")
                    print(f"\tNew acceleration: {self.sensor.acceleration}")
                    print(f"\tNew velocity: {self.sensor.velocity}")
                    print(f"\tNew gas pedal reading: {self.sensor.gas_throttle}")
                    print(f"\tNew brake pedal reading: {self.sensor.brake_control}")

                    # Use incoming packet opportunity to send own packet. Don't send packages if at the end of the line.
                    if self.follower_name != self.name:
                        # Use arrival of last packet to send out a packet on time
                        self.packet.sequence_number = self.last_seq_sent
                        # print(self.sensor.acceleration)
                        # self.packet.acceleration = self.sensor.acceleration
                        # # print(str(self.sensor.acceleration) + " failed")
                        # self.packet.velocity = self.sensor.velocity
                        # # print(str(self.sensor.gas_throttle) + " failed")
                        # # print(str(self.sensor.brake_control) + " failed")
                        # self.packet.gas_throttle = self.sensor.gas_throttle
                        # self.packet.brake_control = self.sensor.brake_control
                        # self.packet.gps_position = self.sensor.gps_instant
                        print(f"Broadcasted SEQ #{self.packet.sequence_number} to {str(self.packet.destination_address)}")
                        self.socket.sendto(self.packet.get_packet(), (str(self.packet.destination_address), self.port))

                else:
                    # Create array if there is none
                    if self.flooding_protocol_container.get(incoming_packet.sequence_number) is None:
                        self.flooding_protocol_container[incoming_packet.sequence_number] = []

                    # If the target address not yet in the flooding container, forward it
                    if str(incoming_packet.destination_address) not in self.flooding_protocol_container[incoming_packet.sequence_number]:
                        # Do not pass go, do not collect 200, immediately forward packet
                        print(f"\t└ forwarding packet to Follower Vehicle {incoming_packet.destination_name}...")
                        self.socket.sendto(incoming_data, (destination_address, self.port))

                        # Add to flooding protocol container so it does not get repeated
                        self.flooding_protocol_container[incoming_packet.sequence_number].append(str(incoming_packet.destination_address))
                    else:
                        print(f"[ FLOODING PROTOCOL ] Packet with SEQ# {incoming_packet.sequence_number} en route to {str(incoming_packet.destination_address)} has already been sent and will not be rebroadcasted.")

            else:
                raise ValueError("[ ERROR ] This is not a packet?")

            # Use flooding protocol to determine if we should exit
            if self.last_seq >= 20:
                vals = len(self.flooding_protocol_container)
                # Follower vehicle
                if vals == 0:
                    return None
                # If the last container had as many sources as the last, then we're done
                elif vals == 20 and len(self.flooding_protocol_container[20]) == len(self.flooding_protocol_container[1]):
                    if self.last_seq_forwarded == 20:
                        self.flooding_protocol_container['DONE'] = True
