import random
from simplenc import BinaryCoder


def main(n = 8):
    packets = n
    packet_size = 8
    seed = 1
    random.seed(seed)

    encoder = BinaryCoder(packets, packet_size, seed)
    decoder = BinaryCoder(packets, packet_size, seed)

    messages = 0
    while not decoder.is_fully_decoded():
        # print(f"Processing message {messages}")
        if messages < packets:
            packet = random.getrandbits(encoder.num_bit_packet)
            packet = [packet >> i & 1 for i in range(encoder.num_bit_packet - 1, -1, -1)]
            coefficients = [0] * encoder.num_symbols
            coefficients[messages] = 1
            encoder.consume_packet(coefficients, packet)
        coefficient, packet = encoder.get_new_coded_packet()
        # https://stackoverflow.com/questions/32284940/python-bit-list-to-byte-list
        print(int("".join(map(str, coefficient)), 2), int("".join(map(str, packet)), 2))
        decoder.consume_packet(coefficient, packet)
        messages += 1
    
    if decoder.packet_vector == encoder.packet_vector:
        efficiency = packets / messages
        print(f"took {messages} messages to transmit {packets} packets ({efficiency * 100:.0f}%), {messages - packets} redundant")
        # for packet in decoder.packet_vector:
            # print(packet)
        return efficiency
    else:
        print(f"whoops, decoded packets vectors are wrong")
        print(f"encoded:\n", encoder.packet_vector)
        print(f"decoded:\n", decoder.packet_vector)
        raise ValueError

if __name__ == "__main__":
    main(10)
    # efficiencies = []
    # for n in range(10, 500, 20):
        # efficiencies.append(main(n))
    # average = sum(efficiencies) / len(efficiencies)
    # print(f"average efficiency: {average * 100:.0f}%")
