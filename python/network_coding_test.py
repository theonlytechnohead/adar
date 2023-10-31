import random
from simplenc import BinaryCoder


def main(packets: int = 1, length: int = 8):
	packet_size = length
	seed = 1

	encoder = BinaryCoder(packets, packet_size, seed)
	decoder = BinaryCoder(packets, packet_size, seed)

	messages = 0
	coded_size = 0
	while not decoder.is_fully_decoded():
		# print(f"Processing message {messages}")
		if messages < packets:
			packet = random.getrandbits(encoder.num_bit_packet)
			packet = [packet >> i & 1 for i in range(encoder.num_bit_packet - 1, -1, -1)]
			coefficients = [0] * encoder.num_symbols
			coefficients[messages] = 1
			encoder.consume_packet(coefficients, packet)
		coefficient, packet = encoder.get_sys_coded_packet(messages)
		# https://stackoverflow.com/questions/32284940/python-bit-list-to-byte-list
		# print(int("".join(map(str, coefficient)), 2), int("".join(map(str, packet)), 2))
		coded_size += len(coefficient) + len(packet)
		decoder.consume_packet(coefficient, packet)
		messages += 1
	
	if decoder.packet_vector == encoder.packet_vector:
		efficiency = messages / packets
		# print(f"data packets: {packets}, transmitted packets: {messages} ({efficiency * 100:.0f}%), {messages - packets} overshoot")
		print(f"data size: {packets * packet_size}, coded size: {coded_size},  ({(coded_size / (packets * packet_size)) * 100:.0f}%)")
		# for packet in decoder.packet_vector:
			# print(packet)
		return efficiency, (coded_size / (packets * packet_size)) * 100
	else:
		print(f"whoops, decoded packets vectors are wrong")
		print(f"encoded:\n", encoder.packet_vector)
		print(f"decoded:\n", decoder.packet_vector)
		raise ValueError

if __name__ == "__main__":
	# main(4, 8)
	efficiencies = []
	data_efficiencies = []
	for n in range(8, 65, 8):
		efficiency, data_efficiency = main(n, 1024)
		efficiencies.append(efficiency)
		data_efficiencies.append(data_efficiency)
	# average = sum(efficiencies) / len(efficiencies)
	data_average = sum(data_efficiencies) / len(data_efficiencies)
	# print(f"packet efficiency: {average * 100:.0f}%")
	print(f"data efficiency: {data_average:.0f}%")
